"""Main blueprint — index, status, health, videos, summaries, transcripts."""

from flask import Blueprint, jsonify, render_template

from app_config import SessionLocal, md_safe
from db.models import SummariesV2, Video, VideoFolder

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Main page: form to enter a channel URL (or a video from that channel).
    Also lists already downloaded channels as links.
    """
    session = SessionLocal()
    try:
        folder_rows = session.query(VideoFolder.folder_name).distinct().all()
        channel_list = [row.folder_name for row in folder_rows]
    finally:
        session.close()

    return render_template("index.html", channels=channel_list)


@main_bp.route("/status")
def status_page():
    """Basic page to show status progress."""
    return render_template("status.html")


@main_bp.route("/health")
def health_check():
    """Simple health check endpoint for Docker HEALTHCHECK."""
    return jsonify({"status": "healthy"}), 200


@main_bp.route("/videos/<channel_name>")
def videos_page(channel_name):
    """Render a page to chat with the entire channel.
    Also show all videos that belong to this channel.
    """
    session = SessionLocal()
    try:
        videos = (
            session.query(Video)
            .join(VideoFolder, Video.video_id == VideoFolder.video_id)
            .filter(VideoFolder.folder_name == channel_name)
            .all()
        )
        video_data = [{"video": vid} for vid in videos]
    finally:
        session.close()

    return render_template("videos.html", channel_name=channel_name, video_data=video_data)


@main_bp.route("/summaries_v2/<int:summary_id>", methods=["GET"])
def view_summary_v2(summary_id):
    """Fetch SummariesV2 by ID, join its Video, convert MD to HTML, render template."""
    session = SessionLocal()
    try:
        summary_obj = session.query(SummariesV2).get(summary_id)
        if not summary_obj:
            return f"SummariesV2 with ID {summary_id} not found.", 404

        video = summary_obj.video

        concise_html = md_safe(summary_obj.concise_summary or "")
        topics_html = md_safe(summary_obj.key_topics or "")
        takeaways_html = md_safe(summary_obj.important_takeaways or "")
        notes_html = md_safe(summary_obj.comprehensive_notes or "")

        return render_template(
            "summary_v2.html",
            summary=summary_obj,
            video=video,
            concise_html=concise_html,
            topics_html=topics_html,
            takeaways_html=takeaways_html,
            notes_html=notes_html,
        )
    finally:
        session.close()


@main_bp.route("/transcript/<video_id>")
def view_transcript_v2(video_id):
    """Fetch Video Transcript by ID and render template."""
    session = SessionLocal()
    try:
        video_obj = session.query(Video).get(video_id)
        if not video_obj:
            return f"Video with ID {video_id} not found.", 404

        return render_template("transcript_v2.html", video=video_obj)
    finally:
        session.close()
