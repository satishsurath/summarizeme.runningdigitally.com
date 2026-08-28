"""API blueprint — channel, video, summarize, channels CRUD, vLLM, all-tasks."""

import datetime
import re
import threading

import requests
from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app_config import (
    DEFAULT_GEN_MODEL,
    VLLM_EMBED_URL,
    VLLM_GEN_URL,
    SessionLocal,
    SQLAlchemyError,
    download_channel_transcripts,
    require_role,
    task_store,
)
from app_config import (
    shared_logger as logger,
)
from db.models import Job, SummariesV2, TranscriptSegment, Video, VideoFolder, WorkItem
from services.contracts import ReasoningEffort
from services.job_queue import JobQueue
from services.model_registry import ModelRegistryService

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/channel/start", methods=["POST"])
@require_role(["admin"])  # Only allow admins to start channel downloads
def api_channel_start():
    """Start downloading transcripts for the entire channel via durable JobQueue."""
    data = request.get_json()
    if not data or "channel_url" not in data:
        return jsonify({"status": "error", "message": "No channel_url provided"}), 400

    raw_channel_url = data["channel_url"]
    if not isinstance(raw_channel_url, str):
        return jsonify({"status": "error", "message": "channel_url must be a string"}), 400
    channel_url = raw_channel_url.strip()
    if not channel_url:
        return jsonify({"status": "error", "message": "No channel_url provided"}), 400

    idempotency_key = request.headers.get("Idempotency-Key")
    with SessionLocal() as session:
        job = JobQueue.create_job(
            session=session,
            job_type="channel_ingest",
            payload={"channel_url": channel_url},
            idempotency_key=idempotency_key,
            initial_work_items=[
                {
                    "stage": "discover",
                    "resource_class": "control",
                    "item_key": channel_url,
                    "payload": {"channel_url": channel_url},
                }
            ],
        )
        job_id = job.id

    return jsonify({"status": "initiated", "task_id": job_id})


@api_bp.route("/channel/status/<task_id>", methods=["GET"])
@require_role(["admin", "member"])
def api_channel_status(task_id):
    """Returns the status of an ongoing channel download process from durable PostgreSQL jobs."""
    with SessionLocal() as session:
        progress = JobQueue.get_job_progress(session, task_id)
        if progress:
            return jsonify(
                {
                    "task_id": progress["job_id"],
                    "status": progress["status"],
                    "processed": progress["completed_items"] + progress["failed_items"],
                    "total": progress["total_items"],
                    "errors": [],
                    "stages": progress.get("stages", {}),
                }
            )

    # Fallback check on legacy task_store if still in migration
    task = task_store.get_task(task_id)
    if task:
        return jsonify(task.to_dict())

    return jsonify({"status": "error", "message": "Invalid task ID"}), 404


@api_bp.route("/videos/<channel_name>", methods=["GET"])
def api_get_videos(channel_name):
    try:
        page = max(1, int(request.args.get("page", 1)))
        page_size = min(100, max(1, int(request.args.get("page_size", 5))))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid page or page_size"}), 400
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
@require_role(["admin", "member"])
def api_summarize_v2():
    """Generate a v2 summary for multiple videos."""
    data = request.get_json() or {}
    raw_channel_name = data.get("channel_name", "")
    channel_name = raw_channel_name.strip() if isinstance(raw_channel_name, str) else ""
    video_ids = data.get("video_ids", [])
    model_name = data.get("model_name") or data.get("model") or DEFAULT_GEN_MODEL
    reasoning_effort = data.get("reasoning_effort", ReasoningEffort.MEDIUM)

    if not channel_name or not isinstance(video_ids, list) or not video_ids:
        return jsonify({"status": "error", "message": "channel_id or video_ids missing"}), 400

    if len(video_ids) > 50:
        return jsonify({"status": "error", "message": "Maximum 50 videos per request"}), 400

    if not all(isinstance(video_id, str) and video_id.strip() for video_id in video_ids):
        return jsonify({"status": "error", "message": "video_ids must contain non-empty strings"}), 400
    if len(set(video_ids)) != len(video_ids):
        return jsonify({"status": "error", "message": "video_ids must be unique"}), 400
    if not isinstance(model_name, str) or not model_name.strip():
        return jsonify({"status": "error", "message": "model_name must be a non-empty string"}), 400

    if reasoning_effort not in {effort.value for effort in ReasoningEffort}:
        return jsonify({"status": "error", "message": "Unsupported reasoning_effort"}), 400

    idempotency_key = request.headers.get("Idempotency-Key")
    initial_work_items = [
        {
            "stage": "summarize",
            "resource_class": "generation",
            "item_key": video_id,
            "payload": {
                "video_id": video_id,
                "model_name": model_name,
                "reasoning_effort": reasoning_effort,
            },
        }
        for video_id in video_ids
    ]
    with SessionLocal() as session:
        # Also ensure folder associations exist
        now = datetime.datetime.now(datetime.timezone.utc)  # noqa: UP017
        for vid in video_ids:
            existing_folder = session.query(VideoFolder).filter_by(folder_name=channel_name, video_id=vid).first()
            if not existing_folder:
                session.add(VideoFolder(folder_name=channel_name, video_id=vid, last_modified=now))
        session.commit()

        job = JobQueue.create_job(
            session=session,
            job_type="summarize",
            payload={
                "channel_name": channel_name,
                "video_ids": video_ids,
                "model_name": model_name,
                "reasoning_effort": reasoning_effort,
            },
            idempotency_key=idempotency_key,
            initial_work_items=initial_work_items,
        )
        job_id = job.id

    return jsonify({"status": "initiated", "task_id": job_id})


@api_bp.route("/summarize_v2/status/<task_id>", methods=["GET"])
@require_role(["admin", "member"])
def api_summarize_v2_status(task_id):
    """Returns progress for the SummariesV2 generation task."""
    with SessionLocal() as session:
        progress = JobQueue.get_job_progress(session, task_id)
        if progress:
            return jsonify(
                {
                    "task_id": progress["job_id"],
                    "status": progress["status"],
                    "processed": progress["completed_items"] + progress["failed_items"],
                    "total": progress["total_items"],
                    "errors": [],
                    "stages": progress.get("stages", {}),
                }
            )

    # Fallback check on legacy task_store if still in migration
    task = task_store.get_task(task_id)
    if task:
        return jsonify(task.to_dict())

    return jsonify({"status": "error", "message": "Invalid task ID"}), 404


@api_bp.route("/active-tasks", methods=["GET"])
@require_role(["admin", "member"])
def api_active_tasks():
    """Return list of active (pending/running) tasks for the notification dropdown."""
    active = []
    with SessionLocal() as session:
        jobs = session.scalars(
            select(Job)
            .where(Job.status.in_(["pending", "running", "paused"]))
            .order_by(Job.created_at.desc())
            .limit(50)
        ).all()
        for job in jobs:
            name_map = {"channel_ingest": "Channel Ingest", "summarize": "Summarize"}
            active.append(
                {
                    "task_id": job.id,
                    "task_type": job.job_type,
                    "name": f"{name_map.get(job.job_type, job.job_type)}: {job.id[:8]}",
                    "status": job.status,
                    "processed": job.completed_items + job.failed_items,
                    "total": job.total_items,
                    "errors": [],
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                }
            )
    return jsonify(active)


@api_bp.route("/channels", methods=["GET"])
@require_role(["admin", "member"])
def api_list_channels():
    session = SessionLocal()
    try:
        folders = session.query(VideoFolder.folder_name, VideoFolder.original_playlist_id).distinct().all()
        folder_list = [{"folder_name": f.folder_name, "original_playlist_id": f.original_playlist_id} for f in folders]
    finally:
        session.close()

    return jsonify(folder_list)


@api_bp.route("/transcript/<video_id>", methods=["GET"])
@require_role(["admin", "member"])
def api_get_transcript(video_id):
    """Returns the full transcript and timestamped segments for a specific video."""
    session = SessionLocal()
    try:
        video = session.query(Video).filter_by(video_id=video_id).first()
        if not video:
            return jsonify({"status": "error", "message": "Video not found"}), 404

        segments = session.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.video_id == video_id)
            .order_by(TranscriptSegment.segment_index.asc())
        ).all()

        segments_data = [
            {
                "segment_index": s.segment_index,
                "start_seconds": s.start_seconds,
                "end_seconds": s.end_seconds,
                "speaker": s.speaker,
                "text": s.text,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}&t={int(s.start_seconds)}s",
            }
            for s in segments
        ]

        transcript = video.transcript_no_ts or ""
        return jsonify(
            {
                "status": "ok",
                "video_id": video_id,
                "title": video.title or "",
                "transcript": transcript,
                "segments": segments_data,
            }
        )
    finally:
        session.close()


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
        logger.error("Error renaming channel in DB: %s", e)
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
        logger.debug("folder_obj: %s", folder_obj)
        if not folder_obj:
            logger.warning("Channel not found")
            return jsonify({"status": "error", "message": "Channel not found"}), 404

        human_playlist_name = folder_obj.folder_name
        original_playlist_id = folder_obj.original_playlist_id or human_playlist_name
        content_type = str(getattr(folder_obj, "content_type", "playlist") or "playlist")
        if content_type == "video":
            channel_url = f"https://www.youtube.com/watch?v={original_playlist_id}"
        else:
            channel_url = f"https://www.youtube.com/playlist?list={original_playlist_id}"
        task_id = task_store.create_task("download", {"channel_name": channel_name_input})

        def run_refresh():
            try:
                download_channel_transcripts(channel_url, task_store, task_id)
                task_store.update_task(task_id, status="completed")
            except Exception as e:
                logger.error("Error in channel refresh: %s", e)
                task_store.update_task(task_id, status="failed", errors=[str(e)])

        thread = threading.Thread(target=run_refresh, daemon=True)
        thread.start()

        return jsonify({"status": "initiated", "task_id": task_id})
    finally:
        session.close()


@api_bp.route("/channels/delete", methods=["POST"])
@require_role(["admin"])
def api_delete_channel():
    """Deletes a channel (folder_name) from the database."""
    session = SessionLocal()
    try:
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
    finally:
        session.close()


@api_bp.route("/all-tasks", methods=["GET"])
@require_role(["admin", "member"])
def api_all_tasks():
    """Return recent jobs with detailed item progress and failure reasons from PostgreSQL."""
    all_tasks = []
    with SessionLocal() as session:
        jobs = session.scalars(select(Job).order_by(Job.created_at.desc()).limit(100)).all()
        for job in jobs:
            # Query work items to compile stage breakdowns and errors
            items = session.scalars(select(WorkItem).where(WorkItem.job_id == job.id)).all()
            errors = [f"Item {item.item_key} ({item.stage}): {item.last_error}" for item in items if item.last_error]
            all_tasks.append(
                {
                    "task_id": job.id,
                    "task_type": job.job_type,
                    "status": job.status,
                    "processed": job.completed_items + job.failed_items,
                    "total": job.total_items,
                    "errors": errors,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                }
            )
    return jsonify(all_tasks)


@api_bp.route("/jobs/<job_id>/cancel", methods=["POST"])
@require_role(["admin"])
def api_cancel_job(job_id: str):
    """Cancel an active or pending pipeline job."""
    with SessionLocal() as session:
        cancelled = JobQueue.cancel_job(session, job_id)
        if not cancelled:
            return jsonify({"status": "error", "message": "Job not found or already terminal"}), 400
        return jsonify({"status": "ok", "job_id": job_id, "message": "Job cancelled successfully"})


@api_bp.route("/jobs/<job_id>/retry", methods=["POST"])
@require_role(["admin"])
def api_retry_job(job_id: str):
    """Retry failed work items in a job."""
    with SessionLocal() as session:
        retried_count = JobQueue.retry_failed_job(session, job_id)
        return jsonify({"status": "ok", "job_id": job_id, "retried_items": retried_count})


@api_bp.route("/admin/endpoints", methods=["GET"])
@require_role(["admin"])
def api_admin_list_endpoints():
    """List registered AI inference endpoints."""
    with SessionLocal() as session:
        ModelRegistryService.bootstrap_from_env(session)
        endpoints = ModelRegistryService.list_endpoints(session)
        return jsonify({"endpoints": endpoints})


@api_bp.route("/admin/models/probe", methods=["POST"])
@require_role(["admin"])
def api_admin_probe_models():
    """Probe an endpoint URL to discover served model IDs."""
    data = request.get_json() or {}
    endpoint_url = data.get("endpoint_url")
    if not endpoint_url:
        return jsonify({"status": "error", "message": "endpoint_url required"}), 400
    model_ids = ModelRegistryService.probe_endpoint_models(endpoint_url)
    return jsonify({"status": "ok", "models": model_ids})


@api_bp.route("/admin/models/qualify", methods=["POST"])
@require_role(["admin"])
def api_admin_qualify_model():
    """Run real qualification capability probe for a model."""
    data = request.get_json() or {}
    model_id = data.get("model_id")
    if not model_id:
        return jsonify({"status": "error", "message": "model_id required"}), 400
    with SessionLocal() as session:
        try:
            result = ModelRegistryService.run_qualification_test(session, model_id)
            return jsonify({"status": "ok", "result": result})
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400


@api_bp.route("/vllm/models", methods=["GET"])
@require_role(["admin", "member"])
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
            logger.warning("Failed to list models from %s: %s", url, e)
    return jsonify({"models": models})


@api_bp.route("/models", methods=["GET"])
@require_role(["admin", "member"])
def api_models():
    """Return active qualified models from ModelRegistryService."""
    with SessionLocal() as session:
        ModelRegistryService.bootstrap_from_env(session)
        models = ModelRegistryService.list_available_models(session, endpoint_type="generation")
        return jsonify({"models": models})


@api_bp.route("/user/preference", methods=["GET", "POST"])
@require_role(["admin", "member"])
def api_user_preference():
    """Get or update current user's preferred model and reasoning effort."""
    from auth_utils import get_current_user

    user_info = get_current_user()
    user_email = user_info[0] if isinstance(user_info, tuple) and user_info[0] else "dev@localhost"
    with SessionLocal() as session:
        if request.method == "POST":
            data = request.get_json() or {}
            pref = ModelRegistryService.set_user_preference(
                session=session,
                user_id=str(user_email),
                preferred_gen_model=data.get("model_name"),
                preferred_reasoning_effort=data.get("reasoning_effort"),
            )
            return jsonify(
                {
                    "user_id": pref.user_id,
                    "preferred_gen_model": pref.preferred_gen_model,
                    "preferred_reasoning_effort": pref.preferred_reasoning_effort,
                }
            )
        else:
            model_name, effort = ModelRegistryService.resolve_user_model(session, str(user_email))
            return jsonify(
                {
                    "user_id": str(user_email),
                    "preferred_gen_model": model_name,
                    "preferred_reasoning_effort": effort,
                }
            )
