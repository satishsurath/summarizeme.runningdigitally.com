"""Main blueprint — index, status, health, videos, summaries, transcripts."""

from flask import Blueprint, jsonify, render_template
from sqlalchemy import select

from app_config import SessionLocal, md_safe, require_role
from db.models import SummariesV2, SummaryRun, Video, VideoFolder

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
        summary_obj = session.get(SummariesV2, summary_id)
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


@main_bp.route("/api/summaries/<summary_id>", methods=["GET"])
@require_role(["admin", "member"])
def api_get_summary(summary_id):
    """Fetch SummariesV2 and latest StructuredSummaryV3 JSON for the Next.js frontend."""
    session = SessionLocal()
    try:
        summary_obj = None
        # Try numeric ID first
        if str(summary_id).isdigit():
            summary_obj = session.get(SummariesV2, int(summary_id))

        if not summary_obj:
            # Fallback: check if summary_id is a SummaryRun UUID
            srun = session.get(SummaryRun, str(summary_id))
            if srun:
                video = session.get(Video, srun.video_id)
                return jsonify(
                    {
                        "id": srun.id,
                        "video_id": srun.video_id,
                        "video_title": video.title if video else srun.video_id,
                        "model_name": srun.model_name,
                        "date_generated": srun.created_at.isoformat() if srun.created_at else None,
                        "structured_summary": srun.structured_summary,
                        "reasoning_output": srun.reasoning_output,
                        "concise_summary": "",
                        "key_topics": "",
                        "important_takeaways": "",
                        "comprehensive_notes": "",
                    }
                )
            return jsonify({"error": f"Summary with ID {summary_id} not found."}), 404

        # Query corresponding SummaryRun for rich 9-section JSON
        latest_run = session.scalar(
            select(SummaryRun)
            .where(
                SummaryRun.video_id == summary_obj.video_id,
                SummaryRun.model_name == summary_obj.model_name,
            )
            .order_by(SummaryRun.created_at.desc())
            .limit(1)
        )

        return jsonify(
            {
                "id": summary_obj.id,
                "video_id": summary_obj.video_id,
                "video_title": summary_obj.video_title,
                "model_name": summary_obj.model_name,
                "date_generated": summary_obj.date_generated.isoformat() if summary_obj.date_generated else None,
                "concise_summary": summary_obj.concise_summary or "",
                "key_topics": summary_obj.key_topics or "",
                "important_takeaways": summary_obj.important_takeaways or "",
                "comprehensive_notes": summary_obj.comprehensive_notes or "",
                "structured_summary": latest_run.structured_summary if latest_run else None,
                "reasoning_output": latest_run.reasoning_output if latest_run else None,
            }
        )
    finally:
        session.close()


@main_bp.route("/transcript/<video_id>")
def view_transcript_v2(video_id):
    """Fetch Video Transcript by ID and render template."""
    session = SessionLocal()
    try:
        video_obj = session.get(Video, video_id)
        if not video_obj:
            return f"Video with ID {video_id} not found.", 404

        return render_template("transcript_v2.html", video=video_obj)
    finally:
        session.close()
