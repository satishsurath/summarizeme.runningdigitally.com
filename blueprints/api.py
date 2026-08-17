"""API blueprint — channel, video, summarize, channels CRUD, vLLM, all-tasks."""

import datetime
import re
import threading
import uuid

import requests
from flask import Blueprint, jsonify, request

from app_config import (
    VLLM_EMBED_URL,
    VLLM_GEN_URL,
    SessionLocal,
    SQLAlchemyError,
    build_prompts_for_chunk,
    chunk_transcript,
    download_channel_transcripts,
    download_statuses,
    require_role,
    summarize_v2_statuses,
    vllm_generate_chunk,
)
from app_config import (
    shared_logger as logger,
)
from db.models import SummariesV2, Video, VideoFolder

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/channel/start", methods=["POST"])
@require_role(["admin"])  # Only allow admins to start channel downloads
def api_channel_start():
    """Start downloading transcripts for the entire channel."""
    data = request.get_json()
    if not data or "channel_url" not in data:
        return jsonify({"status": "error", "message": "No channel_url provided"}), 400

    channel_url = data["channel_url"].strip()
    task_id = f"dl_{uuid.uuid4().hex[:8]}"
    download_statuses[task_id] = {"status": "in_progress", "processed": 0, "total": 0, "errors": []}

    def run_download():
        try:
            download_channel_transcripts(channel_url, download_statuses[task_id])
            download_statuses[task_id]["status"] = "completed"
        except Exception as e:
            logger.error(f"Error in channel download: {e}")
            download_statuses[task_id]["status"] = "failed"
            download_statuses[task_id]["errors"].append(str(e))

    thread = threading.Thread(target=run_download, daemon=True)
    thread.start()

    return jsonify({"status": "initiated", "task_id": task_id})


@api_bp.route("/channel/status/<task_id>", methods=["GET"])
def api_channel_status(task_id):
    """Returns the status of an ongoing channel download process."""
    status = download_statuses.get(task_id)
    if not status:
        return jsonify({"status": "error", "message": "Invalid task ID"}), 404
    return jsonify(status)


@api_bp.route("/videos/<channel_name>", methods=["GET"])
def api_get_videos(channel_name):
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 5))
    sort_by = request.args.get("sort_by", "title")
    sort_order = request.args.get("sort_order", "asc").lower()
    filter_str = request.args.get("filter", "").strip().lower()

    session = SessionLocal()
    try:
        query = (
            session.query(Video)
            .join(VideoFolder, Video.video_id == VideoFolder.video_id)
            .filter(VideoFolder.folder_name == channel_name)
        )

        if filter_str:
            query = query.filter(Video.title.ilike(f"%{filter_str}%"))

        if sort_by == "title":
            query = query.order_by(Video.title.asc()) if sort_order == "asc" else query.order_by(Video.title.desc())
        elif sort_by == "date":
            query = (
                query.order_by(Video.upload_date.asc())
                if sort_order == "asc"
                else query.order_by(Video.upload_date.desc())
            )

        total = query.count()
        offset = (page - 1) * page_size
        video_rows = query.offset(offset).limit(page_size).all()

        videos_list = []
        for vid in video_rows:
            summaries_v2_data = [
                {
                    "id": s.id,
                    "model_name": s.model_name,
                    "date_generated": s.date_generated.isoformat() if s.date_generated else None,
                }
                for s in vid.summaries_v2
            ]

            videos_list.append(
                {
                    "video_id": vid.video_id,
                    "title": vid.title or "Untitled",
                    "upload_date": vid.upload_date or "UnknownDate",
                    "summaries_v2": summaries_v2_data,
                }
            )

        return jsonify({"total": total, "page": page, "page_size": page_size, "videos": videos_list})
    finally:
        session.close()


@api_bp.route("/summarize_v2", methods=["POST"])
def api_summarize_v2():
    """Generate a v2 summary for multiple videos."""
    data = request.get_json() or {}
    channel_name = data.get("channel_name", "").strip()
    video_ids = data.get("video_ids", [])
    model_name = data.get("model", "nemo-qwen3.6-35b-a3b-nvfp4")

    if not channel_name or not video_ids:
        return jsonify({"status": "error", "message": "channel_id or video_ids missing"}), 400

    task_id = f"summ_v2_{uuid.uuid4().hex[:8]}"
    summarize_v2_statuses[task_id] = {"status": "in_progress", "processed": 0, "total": len(video_ids), "errors": []}

    def run_summarize_v2():
        session = SessionLocal()
        processed_count = 0
        try:
            for vid in video_ids:
                existing_folder = session.query(VideoFolder).filter_by(folder_name=channel_name, video_id=vid).first()
                if not existing_folder:
                    folder_assoc = VideoFolder(
                        folder_name=channel_name,
                        video_id=vid,
                        last_modified=datetime.datetime.now(datetime.timezone.utc),  # noqa: UP017
                    )
                    session.add(folder_assoc)
                    session.commit()

                existing_summary = session.query(SummariesV2).filter_by(video_id=vid, model_name=model_name).first()
                if existing_summary:
                    logger.info(f"[SummariesV2] Skipping {vid}, summary already exists for model='{model_name}'.")
                    processed_count += 1
                    summarize_v2_statuses[task_id]["processed"] = processed_count
                    continue

                video_obj = session.query(Video).filter_by(video_id=vid).first()
                if not video_obj:
                    msg = f"Video {vid} not found in DB."
                    logger.error(msg)
                    summarize_v2_statuses[task_id]["errors"].append(msg)
                    processed_count += 1
                    summarize_v2_statuses[task_id]["processed"] = processed_count
                    continue

                transcript = video_obj.transcript_no_ts or ""
                tokens_no_ts = int(video_obj.tokens_no_ts) if video_obj.tokens_no_ts else 0  # type: ignore[union-attr]
                if tokens_no_ts <= 0:
                    tokens_no_ts = len(transcript.split())

                chunked_texts = (
                    [transcript] if tokens_no_ts <= 4000 else chunk_transcript(transcript, max_words_per_chunk=4000)
                )

                all_concise, all_topics, all_takeaways, all_comprehensive = [], [], [], []

                for chunk_str in chunked_texts:
                    prompts = build_prompts_for_chunk(chunk_str)
                    all_concise.append(vllm_generate_chunk(model_name, prompts["concise"]))
                    all_topics.append(vllm_generate_chunk(model_name, prompts["key_topics"]))
                    all_takeaways.append(vllm_generate_chunk(model_name, prompts["takeaways"]))
                    all_comprehensive.append(vllm_generate_chunk(model_name, prompts["comprehensive"]))

                new_summary = SummariesV2(
                    video_id=vid,
                    video_title=video_obj.title,
                    model_name=model_name,
                    date_generated=datetime.datetime.now(datetime.timezone.utc),  # noqa: UP017
                    concise_summary="\n".join(all_concise).strip(),
                    key_topics="\n".join(all_topics).strip(),
                    important_takeaways="\n".join(all_takeaways).strip(),
                    comprehensive_notes="\n".join(all_comprehensive).strip(),
                )
                session.add(new_summary)
                session.commit()

                logger.info(f"[SummariesV2] Inserted for video={vid}, model={model_name}")
                processed_count += 1
                summarize_v2_statuses[task_id]["processed"] = processed_count

            summarize_v2_statuses[task_id]["status"] = "completed"
        except Exception as e:
            logger.error(f"[SummariesV2] Error: {e}")
            summarize_v2_statuses[task_id]["status"] = "failed"
            summarize_v2_statuses[task_id]["errors"].append(str(e))
        finally:
            session.close()

    thread = threading.Thread(target=run_summarize_v2, daemon=True)
    thread.start()

    return jsonify({"status": "initiated", "task_id": task_id})


@api_bp.route("/summarize_v2/status/<task_id>", methods=["GET"])
def api_summarize_v2_status(task_id):
    """Returns progress for the SummariesV2 generation task."""
    status = summarize_v2_statuses.get(task_id)
    if not status:
        return jsonify({"status": "error", "message": "Invalid task ID"}), 404
    return jsonify(status)


@api_bp.route("/active-tasks", methods=["GET"])
def api_active_tasks():
    """Return list of active (pending/running) tasks for the notification dropdown."""
    active = []
    for task_id, status in download_statuses.items():
        if status.get("status") in ("pending", "in_progress"):
            active.append(
                {
                    "task_id": task_id,
                    "name": f"Download: {task_id}",
                    "status": status["status"],
                    "processed": status.get("processed", 0),
                    "total": status.get("total", 0),
                }
            )
    for task_id, status in summarize_v2_statuses.items():
        if status.get("status") in ("pending", "in_progress"):
            active.append(
                {
                    "task_id": task_id,
                    "name": f"Summarize: {task_id}",
                    "status": status["status"],
                    "processed": status.get("processed", 0),
                    "total": status.get("total", 0),
                }
            )
    return jsonify(active)


@api_bp.route("/channels", methods=["GET"])
def api_list_channels():
    session = SessionLocal()
    try:
        folders = session.query(VideoFolder.folder_name, VideoFolder.original_playlist_id).distinct().all()
        folder_list = [{"folder_name": f.folder_name, "original_playlist_id": f.original_playlist_id} for f in folders]
    finally:
        session.close()

    return jsonify(folder_list)


@api_bp.route("/channels/rename", methods=["POST"])
@require_role(["admin"])  # Only allow admins to rename channels
def api_rename_channel():
    """Renames a channel in the database."""
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    old_name = data.get("old_name", "").strip()
    new_name = data.get("new_name", "").strip()

    if not old_name or not new_name:
        return jsonify({"status": "error", "message": "old_name and new_name are required"}), 400

    safe_new_name = re.sub(r"[^a-zA-Z0-9_\-\s]", "", new_name)
    if not safe_new_name:
        return jsonify({"status": "error", "message": "Invalid characters in new_name"}), 400

    session = SessionLocal()
    try:
        count_old = session.query(VideoFolder).filter_by(folder_name=old_name).count()
        if count_old == 0:
            return jsonify({"status": "error", "message": f"Channel '{old_name}' not found in database."}), 404

        count_new = session.query(VideoFolder).filter_by(folder_name=safe_new_name).count()
        if count_new > 0:
            return jsonify({"status": "error", "message": f"Channel '{safe_new_name}' already exists."}), 400

        session.query(VideoFolder).filter_by(folder_name=old_name).update({"folder_name": safe_new_name})
        session.commit()

        return jsonify({"status": "ok", "old_name": old_name, "new_name": safe_new_name})

    except SQLAlchemyError as e:
        logger.error(f"Error renaming channel in DB: {e}")
        session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()


@api_bp.route("/channels/refresh", methods=["POST"])
@require_role(["admin", "member"])  # Only allow admins and members to refresh channels
def api_refresh_channel():
    """Refresh the channel using the immutable original_playlist_id."""
    data = request.get_json() or {}
    channel_name_input = data.get("channel_name", "").strip()
    if not channel_name_input:
        return jsonify({"status": "error", "message": "Channel name missing"}), 400

    session = SessionLocal()
    try:
        folder_obj = (
            session.query(VideoFolder)
            .filter(
                (VideoFolder.folder_name == channel_name_input)
                | (VideoFolder.original_playlist_id == channel_name_input)
            )
            .first()
        )
        logger.debug(f"folder_obj: {folder_obj}")
        if not folder_obj:
            logger.warning("Channel not found")
            return jsonify({"status": "error", "message": "Channel not found"}), 404

        human_playlist_name = folder_obj.folder_name
        original_playlist_id = folder_obj.original_playlist_id or human_playlist_name
        channel_url = f"https://www.youtube.com/playlist?list={original_playlist_id}"

        task_id = f"refresh_{uuid.uuid4().hex[:8]}"
        download_statuses[task_id] = {"status": "in_progress", "processed": 0, "total": 0, "errors": []}

        def run_refresh():
            try:
                download_channel_transcripts(channel_url, download_statuses[task_id])
                download_statuses[task_id]["status"] = "completed"
            except Exception as e:
                logger.error(f"Error in channel refresh: {e}")
                download_statuses[task_id]["status"] = "failed"
                download_statuses[task_id]["errors"].append(str(e))

        thread = threading.Thread(target=run_refresh, daemon=True)
        thread.start()

        return jsonify({"status": "initiated", "task_id": task_id})
    finally:
        session.close()


@api_bp.route("/channels/delete", methods=["POST"])
@require_role(["admin"])  # Only allow admins to delete channels
def api_delete_channel():
    """Deletes a channel (folder_name) from the database."""
    session = SessionLocal()

    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"status": "error", "message": "No channel name provided"}), 400

    folder_name = data["name"].strip()
    if not folder_name:
        return jsonify({"status": "error", "message": "Channel name is empty."}), 400

    folders_to_delete = session.query(VideoFolder).filter_by(folder_name=folder_name).all()

    if not folders_to_delete:
        return jsonify({"status": "error", "message": "Channel not found."}), 404

    video_ids = [f.video_id for f in folders_to_delete]

    for f in folders_to_delete:
        session.delete(f)

    session.flush()

    unique_video_ids = set(video_ids)
    for vid in unique_video_ids:
        usage_count = session.query(VideoFolder).filter_by(video_id=vid).count()
        if usage_count == 0:
            session.query(SummariesV2).filter_by(video_id=vid).delete()
            session.query(Video).filter_by(video_id=vid).delete()

    session.commit()

    return jsonify({"status": "ok", "deleted_folder": folder_name})


@api_bp.route("/all-tasks", methods=["GET"])
def api_all_tasks():
    """Return a list of all tasks (downloads and summaries) in a single JSON array."""
    all_tasks = []

    for task_id, stat in download_statuses.items():
        all_tasks.append(
            {
                "task_id": task_id,
                "type": "download",
                "status": stat["status"],
                "processed": stat["processed"],
                "total": stat["total"],
                "errors": stat["errors"],
            }
        )

    for task_id, stat in summarize_v2_statuses.items():
        all_tasks.append(
            {
                "task_id": task_id,
                "type": "summarize",
                "status": stat["status"],
                "processed": stat["processed"],
                "total": stat["total"],
                "errors": stat["errors"],
            }
        )

    return jsonify(all_tasks)


@api_bp.route("/vllm/models", methods=["GET"])
def api_vllm_models():
    """Returns model lists from both vLLM instances (if configured)."""
    models = []
    for url in [VLLM_EMBED_URL, VLLM_GEN_URL]:
        try:
            resp = requests.get(f"{url}/v1/models", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if "data" in data:
                models.extend(data["data"])
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to list models from {url}: {e}")
    return jsonify({"models": models})
