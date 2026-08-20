"""Chat blueprint — chat-channel and chat-video routes (page + API)."""

import json
import re

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
from db.models import Video, VideoFolder
from prompts import SYSTEM_PROMPT_RAG, build_chat_prompt

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

    logger.info(
        "Chat-channel query for channel=%s, user_query=%r, data_type=%r, model=%r",
        channel_name,
        user_query,
        data_type,
        model_name,
    )

    embeddings_view_map = {
        "comprehensive_notes": "public.summaries_v2_comprehensive_notes_embedding",
        "concise_summary": "public.summaries_v2_concise_summary_embedding",
        "key_topics": "public.summaries_v2_key_topics_embedding",
        "important_takeaways": "public.summaries_v2_important_takeaways_embedding",
        "transcript": "public.videos_transcript_no_ts_embedding",
    }
    selected_view = embeddings_view_map.get(data_type)
    if selected_view not in chat_channel_sql_templates:
        return jsonify({"answer": f"Invalid data_type: {data_type}"}), 400

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

    logger.info(
        "Chat-video query for video_id=%s, user_query=%r, data_type=%r, model=%r",
        video_id,
        user_query,
        data_type,
        model_name,
    )

    embeddings_table_map = {
        "comprehensive_notes": "public.summaries_v2_comprehensive_notes_embedding",
        "concise_summary": "public.summaries_v2_concise_summary_embedding",
        "key_topics": "public.summaries_v2_key_topics_embedding",
        "important_takeaways": "public.summaries_v2_important_takeaways_embedding",
        "transcript": "public.videos_transcript_no_ts_embedding",
    }
    selected_table = embeddings_table_map.get(data_type)
    if selected_table not in chat_video_sql_templates:
        return jsonify({"answer": f"Invalid data_type: {data_type}"}), 400

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
    data_type = data.get("data_type", "comprehensive_notes")
    model_name = data.get("model_name") or data.get("model") or DEFAULT_GEN_MODEL
    headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }

    if not user_query:

        def _err_chan_no_query():
            yield 'event: error\ndata: {"error":"No query provided."}\n\n'

        return Response(stream_with_context(_err_chan_no_query()), content_type="text/event-stream", headers=headers)

    embeddings_view_map = {
        "comprehensive_notes": "public.summaries_v2_comprehensive_notes_embedding",
        "concise_summary": "public.summaries_v2_concise_summary_embedding",
        "key_topics": "public.summaries_v2_key_topics_embedding",
        "important_takeaways": "public.summaries_v2_important_takeaways_embedding",
        "transcript": "public.videos_transcript_no_ts_embedding",
    }
    selected_view = embeddings_view_map.get(data_type)
    if selected_view not in chat_channel_sql_templates:

        def _err_chan_invalid():
            yield 'event: error\ndata: {"error":"Invalid data type."}\n\n'

        return Response(stream_with_context(_err_chan_invalid()), content_type="text/event-stream", headers=headers)

    session = SessionLocal()
    try:
        user_query_emb = vllm_embed_chunk(user_query, model_name=VLLM_EMBED_MODEL, is_query=True)
        if not user_query_emb:

            def _err_chan_no_emb():
                yield 'event: error\ndata: {"error":"Failed to get embedding for user query."}\n\n'

            return Response(stream_with_context(_err_chan_no_emb()), content_type="text/event-stream", headers=headers)

        raw_sql = chat_channel_sql_templates[selected_view] % {"view": selected_view}
        emb_literal = "ARRAY[" + ",".join(str(float(x)) for x in user_query_emb) + "]::vector"
        raw_sql = raw_sql.replace(":q_emb", emb_literal)
        chunk_rows = session.execute(text(raw_sql), {"chan": channel_name}).fetchall()

        if not chunk_rows and selected_view != "public.videos_transcript_no_ts_embedding":
            tmpl = chat_channel_sql_templates["public.videos_transcript_no_ts_embedding"]
            raw_sql = tmpl % {"view": "public.videos_transcript_no_ts_embedding"}
            raw_sql = raw_sql.replace(":q_emb", emb_literal)
            chunk_rows = session.execute(text(raw_sql), {"chan": channel_name}).fetchall()
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

        if not chunk_rows:
            no_content = (
                "No relevant content found for this channel and data type. "
                "Try selecting 'Transcript' or generate summaries first."
            )
            yield f"event: done\ndata: {json.dumps({'answer': no_content, 'done': True})}\n\n"
            return

        try:
            context_pieces = []
            unique_videos = {}
            for row in chunk_rows:
                chunk_text = row[0]
                chunk_vid_id = row[1]
                chunk_vid_title = row[2]
                context_pieces.append(f"Chunk (similarity={row[3]:.4f}): {chunk_text}")
                unique_videos[chunk_vid_id] = chunk_vid_title

            context_for_generation = "\n\n".join(context_pieces)
            prompt_str = build_chat_prompt(context_for_generation, user_query)

            full_answer = ""
            for delta, _ in vllm_generate_stream(model_name, prompt_str, system_prompt=SYSTEM_PROMPT_RAG):
                if delta:
                    full_answer += delta
                    yield f"data: {json.dumps({'delta': delta})}\n\n"
                    sys.stdout.flush()

            thinking, main_answer = separate_thinking_and_answer(full_answer)
            answer_html = md_safe(main_answer)
            if unique_videos:
                answer_html += format_youtube_citations_html(unique_videos)

            if thinking:
                safe_thinking = _html_escape(thinking)
                answer_html = f"<think>{safe_thinking}</think>\n\n{answer_html}"
            yield f"data: {json.dumps({'answer': answer_html, 'done': True})}\n\n"
        except Exception as e:
            logger.exception("Error during chat-channel stream generation:")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

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
    user_query = data.get("query", "")
    headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    if not user_query:

        def _err_vid_no_query():
            yield 'event: error\ndata: {"error":"No query provided."}\n\n'

        return Response(stream_with_context(_err_vid_no_query()), content_type="text/event-stream", headers=headers)

    data_type = data.get("data_type", "comprehensive_notes")
    model_name = data.get("model_name") or data.get("model") or DEFAULT_GEN_MODEL

    logger.info("Chat-video stream query for video_id=%s, user_query=%r", video_id, user_query)

    embeddings_table_map = {
        "comprehensive_notes": "public.summaries_v2_comprehensive_notes_embedding",
        "concise_summary": "public.summaries_v2_concise_summary_embedding",
        "key_topics": "public.summaries_v2_key_topics_embedding",
        "important_takeaways": "public.summaries_v2_important_takeaways_embedding",
        "transcript": "public.videos_transcript_no_ts_embedding",
    }
    selected_table = embeddings_table_map.get(data_type)
    if selected_table not in chat_video_sql_templates:

        def _err_vid_invalid():
            yield 'event: error\ndata: {"error":"Invalid data type."}\n\n'

        return Response(stream_with_context(_err_vid_invalid()), content_type="text/event-stream", headers=headers)

    session = SessionLocal()
    chunk_rows = []
    full_transcript = ""
    video_title = str(video_id)
    try:
        user_query_emb = vllm_embed_chunk(user_query, model_name=VLLM_EMBED_MODEL, is_query=True)
        if not user_query_emb:

            def _err_vid_no_emb():
                yield 'event: error\ndata: {"error":"Failed to get embedding for user query."}\n\n'

            return Response(stream_with_context(_err_vid_no_emb()), content_type="text/event-stream", headers=headers)

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

        # Immediate SSE acknowledgment so the browser doesn't hang
        yield 'event: loading\ndata: {"status":"processing"}\n\n'
        sys.stdout.flush()

        has_context = bool(chunk_rows) or bool(full_transcript)
        if not has_context:
            no_content = (
                "No relevant content found for this video and data type. "
                "Try selecting 'Transcript' or generate summaries first."
            )
            yield f"event: done\ndata: {json.dumps({'answer': no_content, 'done': True})}\n\n"
            return

        try:
            context_pieces = [f"Retrieved Chunk (similarity={row[1]:.4f}): {row[0]}" for row in chunk_rows]
            if full_transcript:
                context_pieces.append(f"Full Video Transcript for '{video_title}':\n{full_transcript}")
            context_for_generation = "\n\n".join(context_pieces)
            prompt_text = build_chat_prompt(context_for_generation, user_query)

            full_answer = ""
            for delta, _ in vllm_generate_stream(model_name, prompt_text, system_prompt=SYSTEM_PROMPT_RAG):
                if delta:
                    full_answer += delta
                    yield f"data: {json.dumps({'delta': delta})}\n\n"
                    sys.stdout.flush()

            thinking, main_answer = separate_thinking_and_answer(full_answer)
            answer_html = md_safe(main_answer)
            if thinking:
                safe_thinking = _html_escape(thinking)
                answer_html = f"<think>{safe_thinking}</think>\n\n{answer_html}"
            yield f"data: {json.dumps({'answer': answer_html, 'done': True})}\n\n"
        except Exception as e:
            logger.exception("Error during chat-video stream generation:")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
