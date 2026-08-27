"""API blueprint — channel, video, summarize, channels CRUD, vLLM, all-tasks."""

import datetime
import re
import threading

import requests
from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from app_config import (
    ASYNC_PIPELINE_ENABLED,
    DEFAULT_GEN_MODEL,
    VLLM_EMBED_URL,
    VLLM_GEN_URL,
    SessionLocal,
    SQLAlchemyError,
    build_prompts_for_chunk,
    chunk_transcript,
    download_channel_transcripts,
    require_role,
    task_store,
    vllm_generate_chunk,
)
from app_config import (
    shared_logger as logger,
)
from db.models import SummariesV2, Video, VideoFolder
from prompts import SYSTEM_PROMPT_SUMMARIZER
from services.contracts import ReasoningEffort
from services.job_queue import JobQueue
from services.model_registry import ModelRegistryService

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/channel/start", methods=["POST"])
@require_role(["admin"])  # Only allow admins to start channel downloads
def api_channel_start():
    """Start downloading transcripts for the entire channel."""
    data = request.get_json()
    if not data or "channel_url" not in data:
        return jsonify({"status": "error", "message": "No channel_url provided"}), 400

    raw_channel_url = data["channel_url"]
    if not isinstance(raw_channel_url, str):
        return jsonify({"status": "error", "message": "channel_url must be a string"}), 400
    channel_url = raw_channel_url.strip()
    if not channel_url:
        return jsonify({"status": "error", "message": "No channel_url provided"}), 400

    if ASYNC_PIPELINE_ENABLED:
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

    task_id = task_store.create_task("download", {"channel_url": channel_url})

    def run_download():
        try:
            download_channel_transcripts(channel_url, task_store, task_id)
            task_store.update_task(task_id, status="completed")
        except Exception as e:
            logger.error("Error in channel download: %s", e)
            task_store.update_task(task_id, status="failed", errors=[str(e)])

    thread = threading.Thread(target=run_download, daemon=True)
    thread.start()

    return jsonify({"status": "initiated", "task_id": task_id})


@api_bp.route("/channel/status/<task_id>", methods=["GET"])
@require_role(["admin", "member"])
def api_channel_status(task_id):
    """Returns the status of an ongoing channel download process."""
    task = task_store.get_task(task_id)
    if task:
        return jsonify(task.to_dict())

    # Fallback / Pipeline adapter: check JobQueue
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

    if ASYNC_PIPELINE_ENABLED:
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

    task_id = task_store.create_task(
        "summarize",
        {"channel_name": channel_name, "model": model_name},
        total=len(video_ids),
    )

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
                    logger.info("[SummariesV2] Skipping %s, summary already exists for model=%r.", vid, model_name)
                    processed_count += 1
                    task_store.update_task(task_id, processed=processed_count)
                    continue

                video_obj = session.query(Video).filter_by(video_id=vid).first()
                if not video_obj:
                    msg = f"Video {vid} not found in DB."
                    logger.error(msg)
                    task = task_store.get_task(task_id)
                    err_list = ([*task.errors, msg]) if task else [msg]
                    task_store.update_task(task_id, errors=err_list)
                    processed_count += 1
                    task_store.update_task(task_id, processed=processed_count)
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
                    prompts = build_prompts_for_chunk(str(chunk_str))
                    all_concise.append(
                        vllm_generate_chunk(model_name, prompts["concise"], system_prompt=SYSTEM_PROMPT_SUMMARIZER)
                    )
                    all_topics.append(
                        vllm_generate_chunk(model_name, prompts["key_topics"], system_prompt=SYSTEM_PROMPT_SUMMARIZER)
                    )
                    all_takeaways.append(
                        vllm_generate_chunk(model_name, prompts["takeaways"], system_prompt=SYSTEM_PROMPT_SUMMARIZER)
                    )
                    all_comprehensive.append(
                        vllm_generate_chunk(
                            model_name, prompts["comprehensive"], system_prompt=SYSTEM_PROMPT_SUMMARIZER
                        )
                    )

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
                try:
                    session.add(new_summary)
                    session.commit()
                except IntegrityError:
                    # A concurrent request inserted the same (video_id, model_name)
                    # between our check and insert; the unique constraint caught it.
                    session.rollback()
                    logger.info(
                        "[SummariesV2] Skipping %s, summary inserted concurrently for model=%r.",
                        vid,
                        model_name,
                    )
                    processed_count += 1
                    task_store.update_task(task_id, processed=processed_count)
                    continue

                logger.info("[SummariesV2] Inserted for video=%s, model=%s", vid, model_name)
                processed_count += 1
                task_store.update_task(task_id, processed=processed_count)

            task_store.update_task(task_id, status="completed")
        except Exception as e:
            logger.error("[SummariesV2] Error: %s", e)
            task_store.update_task(task_id, status="failed", errors=[str(e)])
        finally:
            session.close()

    thread = threading.Thread(target=run_summarize_v2, daemon=True)
    thread.start()

    return jsonify({"status": "initiated", "task_id": task_id})


@api_bp.route("/summarize_v2/status/<task_id>", methods=["GET"])
@require_role(["admin", "member"])
def api_summarize_v2_status(task_id):
    """Returns progress for the SummariesV2 generation task."""
    task = task_store.get_task(task_id)
    if task:
        return jsonify(task.to_dict())

    # Fallback / Pipeline adapter: check JobQueue
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

    return jsonify({"status": "error", "message": "Invalid task ID"}), 404


@api_bp.route("/active-tasks", methods=["GET"])
@require_role(["admin", "member"])
def api_active_tasks():
    """Return list of active (pending/running) tasks for the notification dropdown."""
    active = []
    for task in task_store.list_tasks():
        if task.status in ("pending", "in_progress"):
            name_map = {"download": "Download", "summarize": "Summarize"}
            active.append(
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "name": f"{name_map.get(task.task_type, task.task_type)}: {task.task_id}",
                    "status": task.status,
                    "processed": task.processed,
                    "total": task.total,
                    "errors": task.errors,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at,
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
    """Returns the transcript for a specific video."""
    session = SessionLocal()
    try:
        video = session.query(Video).filter_by(video_id=video_id).first()
        if not video:
            return jsonify({"status": "error", "message": "Video not found"}), 404
        transcript = video.transcript_no_ts or ""
        return jsonify({"status": "ok", "video_id": video_id, "title": video.title or "", "transcript": transcript})
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
def api_all_tasks():
    all_tasks = []
    for task in task_store.list_tasks():
        all_tasks.append(
            {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "status": task.status,
                "processed": task.processed,
                "total": task.total,
                "errors": task.errors,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
            }
        )
    return jsonify(all_tasks)


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
