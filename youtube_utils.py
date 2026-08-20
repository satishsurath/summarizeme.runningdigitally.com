# youtube_utils.py
import json
import logging
import os
import subprocess
import urllib.request
from datetime import UTC, datetime
from urllib.parse import quote

from pytube import YouTube
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Video, VideoFolder

logger = logging.getLogger(__name__)

# DB_URL and SessionLocal are imported from app module to avoid duplication.
# If this file is used standalone, define them:
# DB_URL and SessionLocal are imported from app_config to avoid circular imports.
try:
    from app_config import SessionLocal, engine
except ImportError:
    from sqlalchemy import create_engine

    DB_URL = os.environ["DATABASE_URL"]
    engine = create_engine(DB_URL, echo=False, pool_pre_ping=True, pool_recycle=1800)
    SessionLocal = sessionmaker(bind=engine)


def download_channel_transcripts(channel_url, task_store, task_id):
    """
    Download transcripts for all videos in a channel/playlist.

    Args:
        channel_url (str): YouTube channel or playlist URL.
        task_store (TaskStore): Task store instance for updating progress.
        task_id (str): Task ID to update.
    """
    session = SessionLocal()
    errors: list[str] = []
    try:
        # Get the immutable channel/playlist id and video list from YouTube
        channel_id, videos = get_channel_and_videos(channel_url)

        total_videos = len(videos)
        task_store.update_task(task_id, total=total_videos)
        processed_count = 0

        # Use existing folder name if exists, else use channel_id
        existing_folder = session.query(VideoFolder).filter_by(original_playlist_id=channel_id).first()

        # Determine content type based on URL and resolved entries count
        url_types = ["youtube.com/watch", "youtu.be/", "youtube.com/shorts/", "youtube.com/live/"]
        is_video_url = any(k in channel_url for k in url_types)
        content_type = "video" if (is_video_url and len(videos) == 1) else "playlist"

        human_playlist_name = existing_folder.folder_name if existing_folder else channel_id

        # Set content_type on existing folder or use default
        if existing_folder:
            existing_folder.content_type = content_type

        processed_count = 0
        new_count = 0

        for i, video in enumerate(videos):
            if not isinstance(video, dict):
                logger.error(f"Skipping malformed video entry at index {i}: {video!r}")
                errors.append(f"Malformed entry at index {i}")
                processed_count += 1
                continue
            try:
                video_id = video.get("video_id")
                video_title = video.get("title") or "Untitled (no title)"
                logger.info(f"[{i + 1}/{len(videos)}] Processing: {video_id} - {video_title[:30]}")
                if not video_id:
                    logger.error(f"Skipping video with None video_id: {video}")
                    errors.append(f"None video_id at index {i}")
                    processed_count += 1
                    continue

                # Check if already downloaded
                existing_video = session.query(Video).filter_by(video_id=video_id).first()

                if existing_video:
                    ensure_folder_association(session, video_id, channel_id, human_playlist_name, content_type)
                    processed_count += 1
                    continue

                # Download transcript via yt-dlp wrapper (more reliable)
                logger.info(f"  Downloading transcript for {video_id}")
                parsed = get_transcript_for_video(video_id)
                logger.info(f"  Got {len(parsed)} transcript entries for {video_id}")

                if not parsed:
                    errors.append(f"Failed to get transcript for {video_id} ({video_title[:30]}...)")
                    processed_count += 1
                    continue

                # Save video record
                video_obj = Video(
                    video_id=video_id,
                    title=video_title,
                    upload_date=video.get("upload_date"),
                    transcript_with_ts=None,
                    transcript_no_ts=None,
                )
                session.add(video_obj)
                session.flush()

                # Save transcript
                srt_lines = []
                for t in parsed:
                    txt = t.get("text", "")
                    if txt:
                        srt_lines.append(f"[{t['start']:.1f}s] " + txt)
                srt_text = "\n".join(srt_lines)
                video_obj.transcript_with_ts = srt_text
                video_obj.transcript_no_ts = " ".join(t.get("text", "") for t in parsed if t.get("text"))

                # Ensure folder association
                ensure_folder_association(session, video_id, channel_id, human_playlist_name, content_type)

                new_count += 1
                processed_count += 1

                # Update progress
                task_store.update_task(task_id, processed=processed_count)

                logger.info(f"[{processed_count}/{total_videos}] Downloaded: {video_title[:50]}...")
            except Exception as e:
                import traceback

                session.rollback()
                logger.error(f"Error processing video {video_id}: {e} - {traceback.format_exc()}")
                errors.append(f"{video_id}: {e}")
                processed_count += 1

        session.commit()
        task_store.update_task(task_id, processed=processed_count, errors=errors)

        # Update folder last_modified
        existing_folder = session.query(VideoFolder).filter_by(original_playlist_id=channel_id).first()
        if existing_folder:
            existing_folder.last_modified = datetime.now(UTC)
            session.commit()

    except Exception as e:
        import traceback

        session.rollback()
        errors.append(str(e))
        logger.error(f"Error downloading channel: {e} - {traceback.format_exc()}")
        task_store.update_task(task_id, errors=errors)
        raise
    finally:
        session.close()


def ensure_folder_association(session, video_id, channel_id, folder_name, content_type="playlist"):
    """
    Helper to ensure there's a row in video_folders linking this video_id
    to the channel/playlist (folder_name + original_playlist_id).
    """
    folder_assoc = session.query(VideoFolder).filter_by(original_playlist_id=channel_id, video_id=video_id).first()
    if not folder_assoc:
        folder_assoc = VideoFolder(
            folder_name=folder_name,
            original_playlist_id=channel_id,
            video_id=video_id,
            content_type=content_type,
            last_modified=datetime.now(UTC),
        )
        session.add(folder_assoc)


def get_channel_and_videos(channel_url):
    """
    Use yt-dlp to list all videos from the channel or playlist (fast).
    Tries HTTP wrapper on host first, falls back to subprocess.
    Return:
      channel_id (str)
      videos (list of dict): { "video_id", "title", "upload_date" }
    """
    data = None

    # Try HTTP wrapper on host (more reliable on macOS)
    wrapper_url = os.getenv("YTDLP_WRAPPER_URL", "http://host.docker.internal:9876")
    try:
        req = urllib.request.Request(f"{wrapper_url}/playlist?url={quote(channel_url)}")
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
    except Exception:
        pass

    # Fallback to subprocess (works on Linux)
    if data is None:
        cmd = ["yt-dlp", "--flat-playlist", "--dump-single-json", channel_url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise Exception(f"yt-dlp failed: {result.stderr}")
        data = json.loads(result.stdout)

    channel_id = data.get("id", "unknown_channel_id")
    entries = data.get("entries", [])

    # Handle single video URL (no entries array, metadata at top level)
    is_single_video = (
        not entries
        and data.get("id")
        and any(
            k in channel_url for k in ["youtube.com/watch", "youtu.be/", "youtube.com/shorts/", "youtube.com/live/"]
        )
    )
    if is_single_video:
        vid_id = data.get("video_id") or data.get("id")
        vid_title = data.get("title", "Untitled")
        upload_date = data.get("upload_date", "UnknownDate")
        videos = [{"video_id": vid_id, "title": vid_title, "upload_date": upload_date}]
    else:
        videos = []
        for entry in entries:
            if entry is None:
                continue
            vid_id = entry.get("video_id") or entry.get("id")
            vid_title = entry.get("title", "Untitled")
            upload_date = entry.get("upload_date", "UnknownDate")
            videos.append({"video_id": vid_id, "title": vid_title, "upload_date": upload_date})

    logger.info(f"Found {len(videos)} videos for '{channel_id}' using {channel_url}")
    return channel_id, videos


def get_upload_date_for_video(video_id):
    """
    Attempt to get a real upload date in 'YYYY-MM-DD' via:
      1) yt-dlp --dump-single-json https://www.youtube.com/watch?v=VIDEO_ID
      2) fallback to pytube

    Return date string or None.
    """
    # Try a single-video metadata query via yt-dlp
    cmd = ["yt-dlp", "--dump-single-json", f"https://www.youtube.com/watch?v={video_id}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            upload_date = data.get("upload_date")  # format: YYYYMMDD
            if upload_date and len(upload_date) == 8:
                return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    except Exception:
        pass

    # Fallback to pytube
    try:
        yt = YouTube(video_id)
        return yt.publish_date.strftime("%Y-%m-%d") if yt.publish_date else None
    except Exception:
        return None


def get_transcript_for_video(video_id):
    """
    Download video transcript via host's yt-dlp transcript wrapper.
    Returns list of {start, duration, text} dicts or empty list on failure.
    """
    wrapper_url = os.getenv("YTDLP_TRANSCRIPT_URL", "http://host.docker.internal:9877")
    try:
        data = json.dumps({"video_id": video_id}).encode()
        req = urllib.request.Request(
            f"{wrapper_url}/transcript",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 200:
                result = json.loads(resp.read().decode())
                srt = result.get("transcript", "")
                if srt:
                    return parse_srt(srt)
    except Exception as e:
        logger.warning(f"Transcript wrapper failed for {video_id}: {e}")
    return []


def parse_srt(srt_text):
    """
    Parse an SRT/VTT transcript into a list of {start, duration, text} dicts.
    """
    if not srt_text:
        return []
    entries = []
    import re

    srt_text = re.sub(r"\r\n", "\n", srt_text)
    blocks = srt_text.strip().split("\n\n")
    for block in blocks:
        lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
        if not lines:
            continue
        time_idx = next((i for i, line_str in enumerate(lines) if "-->" in line_str), None)
        if time_idx is None:
            continue
        try:
            start_str, end_str = lines[time_idx].split("-->")
            start = srt_time_to_seconds(start_str)
            duration = srt_time_to_seconds(end_str) - start
            raw_text = " ".join(lines[time_idx + 1 :]).strip()
            clean_text = re.sub(r"<[^>]+>", "", raw_text).strip()
            if clean_text:
                entries.append({"start": start, "duration": max(0.0, duration), "text": clean_text})
        except Exception:
            continue
    return entries


def srt_time_to_seconds(t_str):
    """
    Convert 'HH:MM:SS,mmm', 'MM:SS.mmm', or 'HH:MM:SS' to seconds (float).
    """
    t_str = t_str.strip().split()[0]
    t_str = t_str.replace(",", ".")
    parts = t_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


def build_transcript_variants(transcript_entries):
    """
    Given a list of {start, duration, text} dicts, build two variants:
    - with_timestamps: include timestamps in the transcript text
    - no_timestamps: plain text only (no timestamps)

    Returns (with_timestamps, no_timestamps) strings.
    """
    transcript_with_ts = ""
    transcript_no_ts = ""
    for entry in transcript_entries:
        ts = f"[{entry['start']:.1f}s]"
        transcript_with_ts += f"{ts} {entry['text']}\n"
        transcript_no_ts += f"{entry['text']}\n"
    return transcript_with_ts, transcript_no_ts


def list_downloaded_videos(channel_id):
    """
    List all videos that have been downloaded for a given channel/playlist.
    """
    session = SessionLocal()
    try:
        folder = session.query(VideoFolder).filter_by(original_playlist_id=channel_id).first()
        if not folder:
            return []

        video_ids = [
            row[0] for row in session.query(VideoFolder.video_id).filter_by(original_playlist_id=channel_id).all()
        ]
        videos = session.query(Video).filter(Video.video_id.in_(video_ids)).all()
        return [
            {
                "video_id": v.video_id,
                "title": v.title,
                "duration_seconds": getattr(v, "duration_seconds", 0) or 0,
                "has_transcript": bool(v.transcript_no_ts),
            }
            for v in videos
        ]
    finally:
        session.close()
