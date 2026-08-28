"""Chat blueprint — chat-channel and chat-video routes (page + API)."""

import json
import re
import uuid

import requests
from flask import (
    Blueprint,
    Response,
    jsonify,
    render_template,
    request,
    stream_with_context,
)
from markupsafe import escape as _html_escape
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text

from app_config import (
    DEFAULT_GEN_MODEL,
    VLLM_EMBED_MODEL,
    SessionLocal,
    chat_channel_sql_templates,
    chat_video_sql_templates,
    logger,
    md_safe,
    require_role,
    vllm_embed_chunk,
    vllm_generate_chunk,
)
from auth_utils import get_current_user
from db.models import (
    Conversation,
    ConversationMessage,
    Video,
    VideoFolder,
    utcnow,
)
from prompts import SYSTEM_PROMPT_RAG, build_chat_prompt
from services.model_registry import ModelRegistryService
from services.resource_admission import ResourceAdmission
from services.retrieval_service import RetrievalService

chat_bp = Blueprint("chat", __name__)


def _clean_answer_start(answer: str) -> str:
    """Clean leading stray checkmarks, status tags, or HTML paragraph wrappers from answer text."""
    if not answer:
        return ""
    cleaned = answer.strip()
    while True:
        prev = cleaned
        cleaned = re.sub(
            r"^(?:<p>\s*(?:[✅✓]|\[Response Text\]|\[Output\]|\[Done\.?\]|Proceeds\.?)\s*<\/p>|<br\s*\/?>|\s)*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        cleaned = re.sub(
            r"^(?:->|=>|-&gt;|[✅✓]|\"|'|\s)+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        if cleaned == prev:
            break
    return cleaned


def separate_thinking_and_answer(text: str) -> tuple[str | None, str]:
    """Separate reasoning/thinking content from main answer in model output text."""
    if not text:
        return None, ""

    # 1. <think> ... </think> XML tags
    think_match = re.search(r"<think>(.*?)</think>", text, re.DOTALL | re.IGNORECASE)
    if think_match:
        thinking = think_match.group(1).strip()
        raw_answer = (text[: think_match.start()] + text[think_match.end() :]).strip()
        answer = _clean_answer_start(raw_answer)
        return thinking or None, answer

    # Handle unclosed <think> tag cut off by max_tokens
    if "<think>" in text.lower() and "</think>" not in text.lower():
        idx = text.lower().find("<think>")
        thinking = text[idx + 7 :].strip()
        return thinking or None, ""

    # 2. "Here's a thinking process:" or "Thinking Process:" prefix
    prefix_match = re.match(
        r"^\s*(?:Here(?:'|&#39;|\u2019)?s a thinking process:|Thinking Process:|Thought Process:)",
        text,
        re.IGNORECASE,
    )
    if prefix_match:
        prefix_len = prefix_match.end()
        rest = text[prefix_len:]

        # Transition marker patterns ordered by specificity
        transition_patterns = [
            r"\(Done\.\)",
            r"\[Done\.\]",
            r"\(Done\)",
            r"\[Done\]",
            r"\(Finished\.\)",
            r"\[Finished\.\]",
            r"\[Output Generation\](?:\s*(?:-|&amp;|-&gt;|->)\s*Proceeds)?",
            r"\[Output\]",
            r"Final Answer:",
            r"Final Output:",
            r"(?:\[)?Proceeds?(?:\.|\s*\])?",
            r"✅ Output matches\.\s*(?:\[Proceeds\])?",
        ]
        combined_pattern = r"(?:" + "|".join(transition_patterns) + r")"
        matches = list(re.finditer(combined_pattern, rest, re.IGNORECASE))

        if matches:
            # Pick the last match that leaves non-empty answer text
            chosen_match = matches[-1]
            for m in reversed(matches):
                candidate_ans = rest[m.end() :].strip()
                if candidate_ans:
                    chosen_match = m
                    break

            thinking = rest[: chosen_match.end()].strip()
            raw_answer = rest[chosen_match.end() :].strip()
            answer = _clean_answer_start(raw_answer)
            if thinking and answer:
                return thinking, answer

        # Fallback: Split on double newline before final paragraph
        double_newline_match = re.search(
            r"\n\n(?=(?:This video|Here is|In this|The video|Answer:|[A-Z][a-z0-9\s]{2,30}:))",
            rest,
            re.IGNORECASE,
        )
        if double_newline_match:
            thinking = rest[: double_newline_match.start()].strip()
            raw_answer = rest[double_newline_match.end() :].strip()
            answer = _clean_answer_start(raw_answer)
            return thinking or None, answer or text

    return None, _clean_answer_start(text)


def format_youtube_citations_html(unique_videos: dict[str, str]) -> str:
    """Format unique YouTube videos as styled citation card markup with YouTube logo."""
    if not unique_videos:
        return ""

    yt_logo_svg = (
        '<svg class="w-4 h-4 text-red-600 inline-block shrink-0" viewBox="0 0 24 24" fill="currentColor">'
        '<path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 '
        "3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 "
        "9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 "
        '15.568V8.432L15.818 12l-6.273 3.568z"/>'
        "</svg>"
    )
    ext_icon_svg = (
        '<svg class="w-3.5 h-3.5 text-gray-400 group-hover:text-red-400 shrink-0 ml-1" fill="none" '
        'stroke="currentColor" viewBox="0 0 24 24">'
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 '
        '002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>'
        "</svg>"
    )

    html = (
        '<div class="youtube-citations mt-3 pt-2 border-t border-gray-200/40 dark:border-gray-700/40">\n'
        '  <div class="flex items-center gap-1.5 text-[10px] font-bold text-red-600 dark:text-red-400 mb-1 '
        'uppercase tracking-wider">\n'
        f"    {yt_logo_svg}\n"
        "    <span>Videos used in Context</span>\n"
        "  </div>\n"
        '  <div class="flex flex-wrap gap-1.5 mt-0.5">\n'
    )
    for vid_id, vid_title in unique_videos.items():
        safe_vid_id = _html_escape(vid_id)
        safe_vid_title = _html_escape(vid_title)
        html += (
            f'    <a href="https://www.youtube.com/watch?v={safe_vid_id}" target="_blank" rel="noopener noreferrer"\n'
            '       class="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-gray-900 text-white '
            "dark:bg-gray-800 dark:text-gray-100 border border-gray-700 hover:bg-gray-800 "
            'dark:hover:bg-gray-700 transition-all shadow-xs group">\n'
            f"      {yt_logo_svg}\n"
            f'      <span class="truncate max-w-sm text-xs font-semibold text-white dark:text-gray-100">'
            f"{safe_vid_title}</span>\n"
            f"      {ext_icon_svg}\n"
            "    </a>\n"
        )
    html += "  </div>\n</div>\n"
    return html


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@chat_bp.route("/chat-channel/<channel_name>", methods=["GET"])
@require_role(["admin", "member"])
def chat_channel_page(channel_name):
    """Render a page to chat with the entire channel."""
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

    return render_template("channel_chat.html", channel_name=channel_name, video_data=video_data)


@chat_bp.route("/chat-video/<video_id>", methods=["GET"])
@require_role(["admin", "member"])
def chat_video_page(video_id):
    """Renders a page that allows chatting with a single video's content."""
    session = SessionLocal()
    video_name = ""
    video_transcript = ""
    folder_list = []
    try:
        video = session.query(Video).filter_by(video_id=video_id).first()
        if not video:
            return f"Video with id '{video_id}' not found.", 404
        video_name = video.title
        video_transcript = video.transcript_no_ts
        folder_list = [vf.folder_name for vf in video.folders]
    finally:
        session.close()

    return render_template(
        "video_chat.html",
        video_id=video_id,
        video_name=video_name,
        video_transcript=video_transcript,
        folder_list=folder_list,
    )


# ---------------------------------------------------------------------------
# Non-streaming API endpoints
# ---------------------------------------------------------------------------


@chat_bp.route("/api/chat-channel/<channel_name>", methods=["POST"])
@require_role(["admin", "member"])
def api_chat_channel(channel_name):
    """AJAX endpoint to handle chat queries for a given channel."""
    data = request.json or {}
    user_query = data.get("query", "").strip()
    data_type = data.get("data_type", "comprehensive_notes")
    model_name = data.get("model_name") or data.get("model") or DEFAULT_GEN_MODEL

    if not user_query:
        return jsonify({"answer": "No query provided."}), 400

    # Validate model_name against registry
    with SessionLocal() as _sess:
        available = ModelRegistryService.list_available_models(_sess, endpoint_type="generation")
        valid_ids = {m["model_id"] for m in available} if available else set()
        if valid_ids and model_name not in valid_ids:
            model_name = DEFAULT_GEN_MODEL

    logger.info(
        "Chat-channel query for channel=%s, user_query=%r, data_type=%r, model=%r",
        channel_name,
        user_query,
        data_type,
        model_name,
    )

    valid_data_types = {
        "automatic",
        "all",
        "summary",
        "comprehensive_notes",
        "concise_summary",
        "key_topics",
        "important_takeaways",
        "transcript",
    }
    if data_type not in valid_data_types:
        return jsonify({"answer": f"Invalid data_type: {data_type}"}), 400

    embeddings_view_map = {
        "comprehensive_notes": "public.summaries_v2_comprehensive_notes_embedding",
        "concise_summary": "public.summaries_v2_concise_summary_embedding",
        "key_topics": "public.summaries_v2_key_topics_embedding",
        "important_takeaways": "public.summaries_v2_important_takeaways_embedding",
        "transcript": "public.videos_transcript_no_ts_embedding",
    }
    selected_view = embeddings_view_map.get(
        data_type,
        "public.videos_transcript_no_ts_embedding"
        if data_type == "transcript"
        else "public.summaries_v2_comprehensive_notes_embedding",
    )

    session = SessionLocal()
    final_answer = ""
    used_videos_html = ""
    try:
        user_query_emb = vllm_embed_chunk(user_query, model_name=VLLM_EMBED_MODEL, is_query=True)
        if not user_query_emb:
            return jsonify({"answer": "Failed to get embedding for user query."}), 500

        raw_sql = chat_channel_sql_templates[selected_view] % {"view": selected_view}
        emb_literal = "ARRAY[" + ",".join(str(float(x)) for x in user_query_emb) + "]::vector"
        raw_sql = raw_sql.replace(":q_emb", emb_literal)
        chunk_rows = session.execute(text(raw_sql), {"chan": channel_name}).fetchall()

        if not chunk_rows:
            if selected_view != "public.videos_transcript_no_ts_embedding":
                tmpl = chat_channel_sql_templates["public.videos_transcript_no_ts_embedding"]
                raw_sql = tmpl % {"view": "public.videos_transcript_no_ts_embedding"}
                raw_sql = raw_sql.replace(":q_emb", emb_literal)
                chunk_rows = session.execute(text(raw_sql), {"chan": channel_name}).fetchall()
            if not chunk_rows:
                final_answer = (
                    "No relevant content found for this channel and data type. "
                    "Try selecting 'Transcript' or generate summaries first."
                )

        if chunk_rows and not final_answer:
            context_pieces = []
            unique_videos = {}
            for row in chunk_rows:
                chunk_text = row[0]
                chunk_vid_id = row[1]
                chunk_vid_title = row[2]
                similarity = row[3]
                context_pieces.append(f"Chunk (similarity={similarity:.4f}): {chunk_text}")
                unique_videos[chunk_vid_id] = chunk_vid_title

            context_for_generation = "\n\n".join(context_pieces)
            prompt_str = build_chat_prompt(context_for_generation, user_query)

            final_answer = vllm_generate_chunk(model_name, prompt_str, system_prompt=SYSTEM_PROMPT_RAG)
            if not final_answer:
                final_answer = "No answer was returned by the model."

            if unique_videos:
                used_videos_html = format_youtube_citations_html(unique_videos)

    except (requests.exceptions.RequestException, SQLAlchemyError, ValueError, KeyError) as e:
        logger.exception("Error during chat-channel flow:")
        return jsonify({"answer": f"Error: {e!s}"}), 500
    finally:
        session.close()

    thinking, main_answer = separate_thinking_and_answer(final_answer)
    final_answer_html = md_safe(main_answer)
    if used_videos_html:
        final_answer_html += used_videos_html
    if thinking:
        safe_thinking = _html_escape(thinking)
        final_answer_html = f"<think>{safe_thinking}</think>\n\n{final_answer_html}"

    return jsonify({"answer": final_answer_html})


@chat_bp.route("/api/chat-video/<video_id>", methods=["POST"])
@require_role(["admin", "member"])
def api_chat_video(video_id):
    """AJAX endpoint for chatting with a single video's content."""
    data = request.json or {}
    user_query = data.get("query", "")
    if not user_query:
        return jsonify({"answer": "No query provided."}), 400

    data_type = data.get("data_type", "comprehensive_notes")
    model_name = data.get("model_name") or data.get("model") or DEFAULT_GEN_MODEL

    # Validate model_name against registry
    with SessionLocal() as _sess:
        available = ModelRegistryService.list_available_models(_sess, endpoint_type="generation")
        valid_ids = {m["model_id"] for m in available} if available else set()
        if valid_ids and model_name not in valid_ids:
            model_name = DEFAULT_GEN_MODEL

    logger.info(
        "Chat-video query for video_id=%s, user_query=%r, data_type=%r, model=%r",
        video_id,
        user_query,
        data_type,
        model_name,
    )

    valid_data_types = {
        "automatic",
        "all",
        "summary",
        "comprehensive_notes",
        "concise_summary",
        "key_topics",
        "important_takeaways",
        "transcript",
    }
    if data_type not in valid_data_types:
        return jsonify({"answer": f"Invalid data_type: {data_type}"}), 400

    embeddings_table_map = {
        "comprehensive_notes": "public.summaries_v2_comprehensive_notes_embedding",
        "concise_summary": "public.summaries_v2_concise_summary_embedding",
        "key_topics": "public.summaries_v2_key_topics_embedding",
        "important_takeaways": "public.summaries_v2_important_takeaways_embedding",
        "transcript": "public.videos_transcript_no_ts_embedding",
    }
    selected_table = embeddings_table_map.get(
        data_type,
        "public.videos_transcript_no_ts_embedding"
        if data_type == "transcript"
        else "public.summaries_v2_comprehensive_notes_embedding",
    )

    session = SessionLocal()
    final_answer = ""
    try:
        user_query_emb = vllm_embed_chunk(user_query, model_name=VLLM_EMBED_MODEL, is_query=True)
        if not user_query_emb:
            return jsonify({"answer": "Failed to get embedding for user query."}), 500

        emb_literal = "ARRAY[" + ",".join(str(float(x)) for x in user_query_emb) + "]::vector"
        raw_sql = chat_video_sql_templates[selected_table] % {"view": selected_table}
        raw_sql = raw_sql.replace(":q_emb", emb_literal)
        chunk_rows = session.execute(text(raw_sql), {"vid": video_id}).fetchall()

        if not chunk_rows and selected_table != "public.videos_transcript_no_ts_embedding":
            tmpl = chat_video_sql_templates["public.videos_transcript_no_ts_embedding"]
            raw_sql = tmpl % {"view": "public.videos_transcript_no_ts_embedding"}
            raw_sql = raw_sql.replace(":q_emb", emb_literal)
            chunk_rows = session.execute(text(raw_sql), {"vid": video_id}).fetchall()

        # Retrieve full video transcript to leverage 256K long context window
        video_obj = session.query(Video).filter_by(video_id=video_id).first()
        full_transcript: str = str(getattr(video_obj, "transcript_no_ts", "") or "") if video_obj is not None else ""
        video_title: str = (
            str(getattr(video_obj, "title", video_id) or video_id) if video_obj is not None else str(video_id)
        )
        has_context = bool(chunk_rows) or bool(full_transcript)

        if not has_context:
            final_answer = (
                "No relevant content found for this video and data type. "
                "Try selecting 'Transcript' or generate summaries first."
            )

        if has_context and not final_answer:
            context_pieces = [f"Retrieved Chunk (similarity={row[1]:.4f}): {row[0]}" for row in chunk_rows]
            if full_transcript:
                context_pieces.append(f"Full Video Transcript for '{video_title}':\n{full_transcript}")
            context_for_generation = "\n\n".join(context_pieces)
            prompt_text = build_chat_prompt(context_for_generation, user_query)
            final_answer = vllm_generate_chunk(model_name, prompt_text, system_prompt=SYSTEM_PROMPT_RAG)
            if not final_answer:
                final_answer = "No answer was returned by the model."
    except (requests.exceptions.RequestException, SQLAlchemyError, ValueError, KeyError) as e:
        logger.exception("Error while handling chat-video")
        return jsonify({"answer": f"Error: {e}"}), 500
    finally:
        session.close()

    thinking, main_answer = separate_thinking_and_answer(final_answer)
    final_answer_html = md_safe(main_answer)
    if thinking:
        safe_thinking = _html_escape(thinking)
        final_answer_html = f"<think>{safe_thinking}</think>\n\n{final_answer_html}"
    return jsonify({"answer": final_answer_html})


# ---------------------------------------------------------------------------
# Streaming API endpoints (SSE)
# ---------------------------------------------------------------------------


@chat_bp.route("/api/chat-channel/<channel_name>/stream", methods=["POST"])
@require_role(["admin", "member"])
def api_chat_channel_stream(channel_name):
    """SSE streaming endpoint for chat-channel queries."""
    data = request.json or {}
    user_query = data.get("query", "").strip()
    data_type = data.get("data_type", "automatic")
    user_info = get_current_user()
    user_email = str(user_info[0]) if isinstance(user_info, tuple) and user_info[0] else "dev@localhost"

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }

    if not user_query:

        def _err_chan_no_query():
            yield 'event: error\ndata: {"error":"No query provided."}\n\n'

        return Response(stream_with_context(_err_chan_no_query()), content_type="text/event-stream", headers=headers)

    valid_data_types = {
        "automatic",
        "all",
        "summary",
        "comprehensive_notes",
        "concise_summary",
        "key_topics",
        "important_takeaways",
        "transcript",
    }
    if data_type and data_type not in valid_data_types:

        def _err_chan_invalid():
            yield 'event: error\ndata: {"error":"Invalid data type."}\n\n'

        return Response(stream_with_context(_err_chan_invalid()), content_type="text/event-stream", headers=headers)

    session = SessionLocal()
    try:
        model_name, _ = ModelRegistryService.resolve_user_model(
            session=session,
            user_id=user_email,
            requested_model=data.get("model_name") or data.get("model"),
            requested_effort=data.get("reasoning_effort"),
        )

        # 1. Try unified hybrid retrieval first
        retrieved_chunks = RetrievalService.retrieve_context(
            session=session,
            query=user_query,
            scope_type="channel",
            scope_id=channel_name,
            top_k=10,
        )

        # Fallback to legacy SQL template if no unified chunks found yet
        chunk_rows = []
        if not retrieved_chunks:
            embeddings_view_map = {
                "comprehensive_notes": "public.summaries_v2_comprehensive_notes_embedding",
                "concise_summary": "public.summaries_v2_concise_summary_embedding",
                "key_topics": "public.summaries_v2_key_topics_embedding",
                "important_takeaways": "public.summaries_v2_important_takeaways_embedding",
                "transcript": "public.videos_transcript_no_ts_embedding",
            }
            selected_view = embeddings_view_map.get(
                data_type,
                "public.videos_transcript_no_ts_embedding"
                if data_type == "transcript"
                else "public.summaries_v2_comprehensive_notes_embedding",
            )
            if selected_view and selected_view in chat_channel_sql_templates:
                user_query_emb = vllm_embed_chunk(user_query, model_name=VLLM_EMBED_MODEL, is_query=True)
                if user_query_emb:
                    raw_sql = chat_channel_sql_templates[selected_view] % {"view": selected_view}
                    emb_literal = "ARRAY[" + ",".join(str(float(x)) for x in user_query_emb) + "]::vector"
                    raw_sql = raw_sql.replace(":q_emb", emb_literal)
                    chunk_rows = session.execute(text(raw_sql), {"chan": channel_name}).fetchall()
        channel_videos = []
        if not retrieved_chunks and not chunk_rows:
            v_stmt = (
                select(Video.video_id, Video.title, Video.transcript_no_ts)
                .join(VideoFolder, VideoFolder.video_id == Video.video_id)
                .where(
                    (VideoFolder.folder_name == channel_name) | (VideoFolder.original_playlist_id == channel_name),
                    Video.transcript_no_ts.isnot(None),
                    Video.transcript_no_ts != "",
                )
                .limit(5)
            )
            channel_videos = session.execute(v_stmt).fetchall()
            if not channel_videos:
                direct_v = session.execute(
                    select(Video.video_id, Video.title, Video.transcript_no_ts).where(
                        Video.video_id == channel_name,
                        Video.transcript_no_ts.isnot(None),
                        Video.transcript_no_ts != "",
                    )
                ).fetchall()
                if direct_v:
                    channel_videos = direct_v
    except Exception as e:
        err_msg = str(e)
        logger.exception("DB query error in chat-channel stream:")

        def _err_chan_db():
            yield f"event: error\ndata: {json.dumps({'error': err_msg})}\n\n"

        return Response(stream_with_context(_err_chan_db()), content_type="text/event-stream", headers=headers)
    finally:
        session.close()

    def generate():
        import sys

        from summarizer_v2 import vllm_generate_stream

        yield 'event: loading\ndata: {"status":"processing"}\n\n'
        sys.stdout.flush()

        # Emit structured sources event
        sources_payload = [
            {
                "video_id": c.get("video_id"),
                "chunk_type": c.get("chunk_type"),
                "start_seconds": c.get("start_seconds"),
                "end_seconds": c.get("end_seconds"),
                "speaker": c.get("speaker"),
                "excerpt": c.get("text", "")[:200],
                "score": c.get("score", 0.0),
                "youtube_url": (
                    f"https://www.youtube.com/watch?v={c.get('video_id')}&t={int(c.get('start_seconds', 0))}s"
                ),
            }
            for c in (retrieved_chunks or [])
        ]
        if sources_payload:
            yield f"event: sources\ndata: {json.dumps({'sources': sources_payload})}\n\n"
            sys.stdout.flush()

        has_content = bool(retrieved_chunks) or bool(chunk_rows) or bool(channel_videos)
        if not has_content:
            no_content = (
                "No relevant content found for this channel and data type. Try selecting 'Automatic' or 'Transcript'."
            )
            yield f"event: done\ndata: {json.dumps({'answer': no_content, 'done': True})}\n\n"
            return

        gen_session = SessionLocal()
        lease_id = None
        try:
            lease_id = ResourceAdmission.acquire_lease(
                session=gen_session,
                resource_class="generation_interactive",
                owner=f"chat-{user_email}",
                lease_seconds=60,
            )

            context_pieces = []
            unique_videos = {}

            if retrieved_chunks:
                for c in retrieved_chunks:
                    context_pieces.append(f"Retrieved Chunk: {c['text']}")
                    unique_videos[c["video_id"]] = c["video_id"]
            elif chunk_rows:
                for row in chunk_rows:
                    chunk_text = row[0]
                    chunk_vid_id = row[1]
                    chunk_vid_title = row[2]
                    context_pieces.append(f"Chunk (similarity={row[3]:.4f}): {chunk_text}")
                    unique_videos[chunk_vid_id] = chunk_vid_title
            elif channel_videos:
                for vid_row in channel_videos:
                    v_id = str(vid_row[0])
                    v_title = str(vid_row[1] or v_id)
                    v_trans = str(vid_row[2])
                    context_pieces.append(f"Transcript for '{v_title}' ({v_id}):\n{v_trans[:4000]}")
                    unique_videos[v_id] = v_title

            context_for_generation = "\n\n".join(context_pieces)
            prompt_str = build_chat_prompt(context_for_generation, user_query)

            full_answer = ""
            in_think = False
            for delta, _ in vllm_generate_stream(model_name, prompt_str, system_prompt=SYSTEM_PROMPT_RAG):
                if delta:
                    full_answer += delta
                    if "<think>" in delta:
                        in_think = True
                    if "</think>" in delta:
                        in_think = False

                    event_type = "reasoning_delta" if in_think else "answer_delta"
                    # Emit typed SSE frame
                    yield f"event: {event_type}\ndata: {json.dumps({'content': delta})}\n\n"
                    # Emit legacy backward-compatible delta
                    yield f"data: {json.dumps({'delta': delta})}\n\n"
                    sys.stdout.flush()

            thinking, main_answer = separate_thinking_and_answer(full_answer)
            answer_html = md_safe(main_answer)
            if unique_videos:
                answer_html += format_youtube_citations_html(unique_videos)

            if thinking:
                safe_thinking = _html_escape(thinking)
                answer_html = f"<think>{safe_thinking}</think>\n\n{answer_html}"

            # Persist conversation and messages
            conv_id = data.get("conversation_id")
            if not conv_id:
                conv = Conversation(
                    id=str(uuid.uuid4()),
                    user_id=user_email,
                    scope_type="channel",
                    scope_id=channel_name,
                    title=user_query[:50],
                    model_name=model_name,
                    reasoning_effort=data.get("reasoning_effort", "medium"),
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
                gen_session.add(conv)
                conv_id = conv.id
            else:
                conv = gen_session.get(Conversation, conv_id)
                if conv:
                    conv.updated_at = utcnow()

            user_msg = ConversationMessage(
                conversation_id=conv_id,
                role="user",
                content=user_query,
                created_at=utcnow(),
            )
            asst_msg = ConversationMessage(
                conversation_id=conv_id,
                role="assistant",
                content=main_answer,
                reasoning_content=thinking,
                sources=sources_payload if sources_payload else None,
                created_at=utcnow(),
            )
            gen_session.add_all([user_msg, asst_msg])
            gen_session.commit()

            done_payload = {
                "answer": answer_html,
                "conversation_id": conv_id,
                "thinking": thinking,
                "done": True,
            }
            yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
        except Exception as e:
            logger.exception("Error during chat-channel stream generation:")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if lease_id:
                ResourceAdmission.release_lease(session=gen_session, lease_id=lease_id, owner=f"chat-{user_email}")
            gen_session.close()

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers=headers,
    )


@chat_bp.route("/api/chat-video/<video_id>/stream", methods=["POST"])
@require_role(["admin", "member"])
def api_chat_video_stream(video_id):
    """SSE streaming endpoint for chat-video queries."""
    data = request.json or {}
    user_query = data.get("query", "").strip()
    data_type = data.get("data_type", "automatic")
    user_info = get_current_user()
    user_email = str(user_info[0]) if isinstance(user_info, tuple) and user_info[0] else "dev@localhost"

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }

    if not user_query:

        def _err_vid_no_query():
            yield 'event: error\ndata: {"error":"No query provided."}\n\n'

        return Response(stream_with_context(_err_vid_no_query()), content_type="text/event-stream", headers=headers)

    valid_data_types = {
        "automatic",
        "all",
        "summary",
        "comprehensive_notes",
        "concise_summary",
        "key_topics",
        "important_takeaways",
        "transcript",
    }
    if data_type and data_type not in valid_data_types:

        def _err_vid_invalid():
            yield 'event: error\ndata: {"error":"Invalid data type."}\n\n'

        return Response(stream_with_context(_err_vid_invalid()), content_type="text/event-stream", headers=headers)

    session = SessionLocal()
    chunk_rows = []
    retrieved_chunks = []
    full_transcript = ""
    video_title = str(video_id)
    try:
        model_name, _ = ModelRegistryService.resolve_user_model(
            session=session,
            user_id=user_email,
            requested_model=data.get("model_name") or data.get("model"),
            requested_effort=data.get("reasoning_effort"),
        )

        retrieved_chunks = RetrievalService.retrieve_context(
            session=session,
            query=user_query,
            scope_type="video",
            scope_id=video_id,
            top_k=10,
        )

        if not retrieved_chunks:
            embeddings_table_map = {
                "comprehensive_notes": "public.summaries_v2_comprehensive_notes_embedding",
                "concise_summary": "public.summaries_v2_concise_summary_embedding",
                "key_topics": "public.summaries_v2_key_topics_embedding",
                "important_takeaways": "public.summaries_v2_important_takeaways_embedding",
                "transcript": "public.videos_transcript_no_ts_embedding",
            }
            selected_table = embeddings_table_map.get(
                data_type,
                "public.videos_transcript_no_ts_embedding"
                if data_type == "transcript"
                else "public.summaries_v2_comprehensive_notes_embedding",
            )
            if selected_table and selected_table in chat_video_sql_templates:
                user_query_emb = vllm_embed_chunk(user_query, model_name=VLLM_EMBED_MODEL, is_query=True)
                if user_query_emb:
                    emb_literal = "ARRAY[" + ",".join(str(float(x)) for x in user_query_emb) + "]::vector"
                    raw_sql = chat_video_sql_templates[selected_table] % {"view": selected_table}
                    raw_sql = raw_sql.replace(":q_emb", emb_literal)
                    chunk_rows = session.execute(text(raw_sql), {"vid": video_id}).fetchall()

        # Retrieve full video transcript
        video_obj = session.query(Video).filter_by(video_id=video_id).first()
        if video_obj is not None:
            full_transcript = str(getattr(video_obj, "transcript_no_ts", "") or "")
            video_title = str(getattr(video_obj, "title", video_id) or video_id)
    except Exception as e:
        err_msg = str(e)
        logger.exception("DB query error in chat-video stream:")

        def _err_vid_db():
            yield f"event: error\ndata: {json.dumps({'error': err_msg})}\n\n"

        return Response(stream_with_context(_err_vid_db()), content_type="text/event-stream", headers=headers)
    finally:
        session.close()

    def generate():
        import sys

        from summarizer_v2 import vllm_generate_stream

        yield 'event: loading\ndata: {"status":"processing"}\n\n'
        sys.stdout.flush()

        # Emit structured sources event
        sources_payload = [
            {
                "video_id": c.get("video_id"),
                "chunk_type": c.get("chunk_type"),
                "start_seconds": c.get("start_seconds"),
                "end_seconds": c.get("end_seconds"),
                "speaker": c.get("speaker"),
                "excerpt": c.get("text", "")[:200],
                "score": c.get("score", 0.0),
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}&t={int(c.get('start_seconds', 0))}s",
            }
            for c in (retrieved_chunks or [])
        ]
        if sources_payload:
            yield f"event: sources\ndata: {json.dumps({'sources': sources_payload})}\n\n"
            sys.stdout.flush()

        has_context = bool(retrieved_chunks) or bool(chunk_rows) or bool(full_transcript)
        if not has_context:
            no_content = (
                "No relevant content found for this video and data type. Try selecting 'Automatic' or 'Transcript'."
            )
            yield f"event: done\ndata: {json.dumps({'answer': no_content, 'done': True})}\n\n"
            return

        gen_session = SessionLocal()
        lease_id = None
        try:
            lease_id = ResourceAdmission.acquire_lease(
                session=gen_session,
                resource_class="generation_interactive",
                owner=f"chat-{user_email}",
                lease_seconds=60,
            )

            context_pieces = []
            if retrieved_chunks:
                for c in retrieved_chunks:
                    context_pieces.append(f"Retrieved Chunk: {c['text']}")
            else:
                for row in chunk_rows:
                    context_pieces.append(f"Retrieved Chunk (similarity={row[1]:.4f}): {row[0]}")

            if full_transcript:
                context_pieces.append(f"Full Video Transcript for '{video_title}':\n{full_transcript}")

            context_for_generation = "\n\n".join(context_pieces)
            prompt_text = build_chat_prompt(context_for_generation, user_query)

            full_answer = ""
            in_think = False
            for delta, _ in vllm_generate_stream(model_name, prompt_text, system_prompt=SYSTEM_PROMPT_RAG):
                if delta:
                    full_answer += delta
                    if "<think>" in delta:
                        in_think = True
                    if "</think>" in delta:
                        in_think = False

                    event_type = "reasoning_delta" if in_think else "answer_delta"
                    yield f"event: {event_type}\ndata: {json.dumps({'content': delta})}\n\n"
                    yield f"data: {json.dumps({'delta': delta})}\n\n"
                    sys.stdout.flush()

            thinking, main_answer = separate_thinking_and_answer(full_answer)
            answer_html = md_safe(main_answer)
            if thinking:
                safe_thinking = _html_escape(thinking)
                answer_html = f"<think>{safe_thinking}</think>\n\n{answer_html}"

            # Persist conversation
            conv_id = data.get("conversation_id")
            if not conv_id:
                conv = Conversation(
                    id=str(uuid.uuid4()),
                    user_id=user_email,
                    scope_type="video",
                    scope_id=video_id,
                    title=user_query[:50],
                    model_name=model_name,
                    reasoning_effort=data.get("reasoning_effort", "medium"),
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
                gen_session.add(conv)
                conv_id = conv.id
            else:
                conv = gen_session.get(Conversation, conv_id)
                if conv:
                    conv.updated_at = utcnow()

            user_msg = ConversationMessage(
                conversation_id=conv_id,
                role="user",
                content=user_query,
                created_at=utcnow(),
            )
            asst_msg = ConversationMessage(
                conversation_id=conv_id,
                role="assistant",
                content=main_answer,
                reasoning_content=thinking,
                sources=sources_payload if sources_payload else None,
                created_at=utcnow(),
            )
            gen_session.add_all([user_msg, asst_msg])
            gen_session.commit()

            done_payload = {
                "answer": answer_html,
                "conversation_id": conv_id,
                "thinking": thinking,
                "done": True,
            }
            yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
        except Exception as e:
            logger.exception("Error during chat-video stream generation:")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if lease_id:
                ResourceAdmission.release_lease(session=gen_session, lease_id=lease_id, owner=f"chat-{user_email}")
            gen_session.close()

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers=headers,
    )


@chat_bp.route("/api/conversations", methods=["GET", "POST"])
@require_role(["admin", "member"])
def api_conversations():
    """List or create conversation sessions."""
    user_info = get_current_user()
    user_email = str(user_info[0]) if isinstance(user_info, tuple) and user_info[0] else "dev@localhost"
    with SessionLocal() as session:
        if request.method == "POST":
            data = request.get_json() or {}
            scope_type = data.get("scope_type", "global")
            scope_id = data.get("scope_id", "global")
            title = data.get("title", "New Conversation")
            model_name, effort = ModelRegistryService.resolve_user_model(session, user_email)

            conv = Conversation(
                id=str(uuid.uuid4()),
                user_id=user_email,
                scope_type=scope_type,
                scope_id=scope_id,
                title=title,
                model_name=model_name,
                reasoning_effort=effort,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            session.add(conv)
            session.commit()
            return jsonify(
                {"id": conv.id, "title": conv.title, "scope_type": conv.scope_type, "scope_id": conv.scope_id}
            )

        convs = session.scalars(
            select(Conversation).where(Conversation.user_id == user_email).order_by(Conversation.updated_at.desc())
        ).all()
        return jsonify(
            [{"id": c.id, "title": c.title, "scope_type": c.scope_type, "scope_id": c.scope_id} for c in convs]
        )


@chat_bp.route("/api/conversations/<conversation_id>", methods=["GET", "DELETE"])
@require_role(["admin", "member"])
def api_conversation_detail(conversation_id: str):
    """Fetch messages in a conversation or delete the conversation session."""
    user_info = get_current_user()
    user_email = str(user_info[0]) if isinstance(user_info, tuple) and user_info[0] else "dev@localhost"

    with SessionLocal() as session:
        conv = session.get(Conversation, conversation_id)
        if not conv or conv.user_id != user_email:
            return jsonify({"status": "error", "message": "Conversation not found"}), 404

        if request.method == "DELETE":
            session.delete(conv)
            session.commit()
            return jsonify({"status": "ok", "message": "Conversation deleted"})

        messages = session.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.asc())
        ).all()

        return jsonify(
            {
                "id": conv.id,
                "title": conv.title,
                "scope_type": conv.scope_type,
                "scope_id": conv.scope_id,
                "model_name": conv.model_name,
                "reasoning_effort": conv.reasoning_effort,
                "messages": [
                    {
                        "id": m.id,
                        "role": m.role,
                        "content": m.content,
                        "reasoning_content": m.reasoning_content,
                        "sources": m.sources,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in messages
                ],
            }
        )
