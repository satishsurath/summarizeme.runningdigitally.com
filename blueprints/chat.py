"""Chat blueprint — chat-channel and chat-video routes (page + API)."""

import json

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
    VLLM_EMBED_MODEL,
    SessionLocal,
    chat_channel_sql_templates,
    chat_video_sql_templates,
    logger,
    md_safe,
    vllm_embed_chunk,
    vllm_generate_chunk,
)
from db.models import Video, VideoFolder

chat_bp = Blueprint("chat", __name__)


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
def api_chat_channel(channel_name):
    """AJAX endpoint to handle chat queries for a given channel."""
    data = request.json or {}
    user_query = data.get("query", "").strip()
    data_type = data.get("data_type", "comprehensive_notes")
    model_name = data.get("model_name", "nemo-qwen3.6-35b-nvfp4")

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
    selected_view = embeddings_view_map.get(data_type, embeddings_view_map["comprehensive_notes"])
    if selected_view not in chat_channel_sql_templates:
        return jsonify({"answer": "Invalid data type."}), 400

    session = SessionLocal()
    final_answer = ""
    used_videos_html = ""
    try:
        user_query_emb = vllm_embed_chunk(user_query, model_name=VLLM_EMBED_MODEL)
        if not user_query_emb:
            return jsonify({"answer": "Failed to get embedding for user query."}), 500

        raw_sql = chat_channel_sql_templates[selected_view] % {"view": selected_view}
        emb_literal = "ARRAY[" + ",".join(str(x) for x in user_query_emb) + "]::vector"
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
            prompt_str = (
                f"\nContext:\n{context_for_generation}"
                f"\n\nUser Query:\n{user_query}"
                f"\n\nPlease provide a concise answer:\n"
            )

            final_answer = vllm_generate_chunk(model_name, prompt_str)
            if not final_answer:
                final_answer = "No answer was returned by the model."

            if unique_videos:
                used_videos_html = "<h4>Videos used in Context:</h4>\n<ul>\n"
                for vid_id, vid_title in unique_videos.items():
                    safe_vid_id = _html_escape(vid_id)
                    safe_vid_title = _html_escape(vid_title)
                    used_videos_html += (
                        f'<li><a href="https://www.youtube.com/watch?v={safe_vid_id}"'
                        f' target="_blank">{safe_vid_title}</a></li>\n'
                    )
                used_videos_html += "</ul>\n"

    except (requests.exceptions.RequestException, SQLAlchemyError, ValueError, KeyError) as e:
        logger.exception("Error during chat-channel flow:")
        return jsonify({"answer": f"Error: {e!s}"}), 500
    finally:
        session.close()

    final_answer_html = md_safe(final_answer)
    if used_videos_html:
        final_answer_html += used_videos_html

    return jsonify({"answer": final_answer_html})


@chat_bp.route("/api/chat-video/<video_id>", methods=["POST"])
def api_chat_video(video_id):
    """AJAX endpoint for chatting with a single video's content."""
    data = request.json or {}
    user_query = data.get("query", "")
    if not user_query:
        return jsonify({"answer": "No query provided."}), 400

    data_type = data.get("data_type", "comprehensive_notes")
    model_name = data.get("model_name", "nemo-qwen3.6-35b-nvfp4")

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
    selected_table = embeddings_table_map.get(data_type, embeddings_table_map["comprehensive_notes"])

    session = SessionLocal()
    final_answer = ""
    try:
        user_query_emb = vllm_embed_chunk(user_query, model_name=VLLM_EMBED_MODEL)
        if not user_query_emb:
            return jsonify({"answer": "Failed to get embedding for user query."}), 500

        emb_literal = "ARRAY[" + ",".join(str(x) for x in user_query_emb) + "]::vector"
        raw_sql = chat_video_sql_templates[selected_table] % {"view": selected_table}
        raw_sql = raw_sql.replace(":q_emb", emb_literal)
        chunk_rows = session.execute(text(raw_sql), {"vid": video_id}).fetchall()

        if not chunk_rows:
            if selected_table != "public.videos_transcript_no_ts_embedding":
                tmpl = chat_video_sql_templates["public.videos_transcript_no_ts_embedding"]
                raw_sql = tmpl % {"view": "public.videos_transcript_no_ts_embedding"}
                raw_sql = raw_sql.replace(":q_emb", emb_literal)
                chunk_rows = session.execute(text(raw_sql), {"vid": video_id}).fetchall()
            if not chunk_rows:
                final_answer = (
                    "No relevant content found for this video and data type. "
                    "Try selecting 'Transcript' or generate summaries first."
                )

        if chunk_rows and not final_answer:
            context_pieces = [f"Chunk: {row[0]}" for row in chunk_rows]
            context_for_generation = "\n\n".join(context_pieces)
            prompt_text = f"Query: {user_query}\nContext:\n{context_for_generation}"
            final_answer = vllm_generate_chunk(model_name, prompt_text)
            if not final_answer:
                final_answer = "No answer was returned by the model."
    except (requests.exceptions.RequestException, SQLAlchemyError, ValueError, KeyError) as e:
        logger.exception("Error while handling chat-video")
        return jsonify({"answer": f"Error: {e}"}), 500
    finally:
        session.close()

    final_answer_html = md_safe(final_answer)
    return jsonify({"answer": final_answer_html})


# ---------------------------------------------------------------------------
# Streaming API endpoints (SSE)
# ---------------------------------------------------------------------------


@chat_bp.route("/api/chat-channel/<channel_name>/stream", methods=["POST"])
def api_chat_channel_stream(channel_name):
    """SSE streaming endpoint for chat-channel queries."""

    def generate():
        from summarizer_v2 import vllm_generate_stream

        data = request.json or {}
        user_query = data.get("query", "").strip()
        data_type = data.get("data_type", "comprehensive_notes")
        model_name = data.get("model_name", "nemo-qwen3.6-35b-nvfp4")

        if not user_query:
            yield 'event: error\ndata: {"error":"No query provided."}\n\n'
            return

        logger.info("Chat-channel stream query for channel=%s, user_query=%r", channel_name, user_query)

        embeddings_view_map = {
            "comprehensive_notes": "public.summaries_v2_comprehensive_notes_embedding",
            "concise_summary": "public.summaries_v2_concise_summary_embedding",
            "key_topics": "public.summaries_v2_key_topics_embedding",
            "important_takeaways": "public.summaries_v2_important_takeaways_embedding",
            "transcript": "public.videos_transcript_no_ts_embedding",
        }
        selected_view = embeddings_view_map.get(data_type, embeddings_view_map["comprehensive_notes"])
        if selected_view not in chat_channel_sql_templates:
            yield 'event: error\ndata: {"error":"Invalid data type."}\n\n'
            return

        session = SessionLocal()
        try:
            user_query_emb = vllm_embed_chunk(user_query, model_name=VLLM_EMBED_MODEL)
            if not user_query_emb:
                yield 'event: error\ndata: {"error":"Failed to get embedding for user query."}\n\n'
                return

            raw_sql = chat_channel_sql_templates[selected_view] % {"view": selected_view}
            emb_literal = "ARRAY[" + ",".join(str(x) for x in user_query_emb) + "]::vector"
            raw_sql = raw_sql.replace(":q_emb", emb_literal)
            chunk_rows = session.execute(text(raw_sql), {"chan": channel_name}).fetchall()

            if not chunk_rows:
                if selected_view != "public.videos_transcript_no_ts_embedding":
                    tmpl = chat_channel_sql_templates["public.videos_transcript_no_ts_embedding"]
                    raw_sql = tmpl % {"view": "public.videos_transcript_no_ts_embedding"}
                    raw_sql = raw_sql.replace(":q_emb", emb_literal)
                    chunk_rows = session.execute(text(raw_sql), {"chan": channel_name}).fetchall()
                if not chunk_rows:
                    yield (
                        'event: done\ndata: {"answer":"No relevant content found for this channel '
                        "and data type. Try selecting 'Transcript' or generate summaries first.\"}\n\n"
                    )
                    return

            if chunk_rows:
                context_pieces = []
                unique_videos = {}
                for row in chunk_rows:
                    chunk_text = row[0]
                    chunk_vid_id = row[1]
                    chunk_vid_title = row[2]
                    context_pieces.append(f"Chunk (similarity={row[3]:.4f}): {chunk_text}")
                    unique_videos[chunk_vid_id] = chunk_vid_title

                context_for_generation = "\n\n".join(context_pieces)
                prompt_str = (
                    f"\nContext:\n{context_for_generation}"
                    f"\n\nUser Query:\n{user_query}"
                    f"\n\nPlease provide a concise answer:\n"
                )

                full_answer = ""
                for delta, _ in vllm_generate_stream(model_name, prompt_str):
                    if delta:
                        full_answer += delta
                        yield f"data: {json.dumps({'delta': delta})}\n\n"

                answer_html = md_safe(full_answer)
                if unique_videos:
                    answer_html += "<h4>Videos used in Context:</h4>\n<ul>\n"
                    for vid_id, vid_title in unique_videos.items():
                        safe_vid_id = _html_escape(vid_id)
                        safe_vid_title = _html_escape(vid_title)
                        answer_html += (
                            f'<li><a href="https://www.youtube.com/watch?v={safe_vid_id}"'
                            f' target="_blank">{safe_vid_title}</a></li>\n'
                        )
                    answer_html += "</ul>\n"

                yield f"data: {json.dumps({'answer': answer_html, 'done': True})}\n\n"
        except (requests.exceptions.RequestException, SQLAlchemyError, ValueError, KeyError) as e:
            logger.exception("Error during chat-channel stream:")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            session.close()

    return Response(stream_with_context(generate()), content_type="text/event-stream")


@chat_bp.route("/api/chat-video/<video_id>/stream", methods=["POST"])
def api_chat_video_stream(video_id):
    """SSE streaming endpoint for chat-video queries."""

    def generate():
        from summarizer_v2 import vllm_generate_stream

        data = request.json or {}
        user_query = data.get("query", "")
        if not user_query:
            yield 'event: error\ndata: {"error":"No query provided."}\n\n'
            return

        data_type = data.get("data_type", "comprehensive_notes")
        model_name = data.get("model_name", "nemo-qwen3.6-35b-nvfp4")

        logger.info("Chat-video stream query for video_id=%s, user_query=%r", video_id, user_query)

        embeddings_table_map = {
            "comprehensive_notes": "public.summaries_v2_comprehensive_notes_embedding",
            "concise_summary": "public.summaries_v2_concise_summary_embedding",
            "key_topics": "public.summaries_v2_key_topics_embedding",
            "important_takeaways": "public.summaries_v2_important_takeaways_embedding",
            "transcript": "public.videos_transcript_no_ts_embedding",
        }
        selected_table = embeddings_table_map.get(data_type, embeddings_table_map["comprehensive_notes"])

        session = SessionLocal()
        try:
            user_query_emb = vllm_embed_chunk(user_query, model_name=VLLM_EMBED_MODEL)
            if not user_query_emb:
                yield 'event: error\ndata: {"error":"Failed to get embedding for user query."}\n\n'
                return

            emb_literal = "ARRAY[" + ",".join(str(x) for x in user_query_emb) + "]::vector"
            raw_sql = chat_video_sql_templates[selected_table] % {"view": selected_table}
            raw_sql = raw_sql.replace(":q_emb", emb_literal)
            chunk_rows = session.execute(text(raw_sql), {"vid": video_id}).fetchall()

            if not chunk_rows:
                if selected_table != "public.videos_transcript_no_ts_embedding":
                    tmpl = chat_video_sql_templates["public.videos_transcript_no_ts_embedding"]
                    raw_sql = tmpl % {"view": "public.videos_transcript_no_ts_embedding"}
                    raw_sql = raw_sql.replace(":q_emb", emb_literal)
                    chunk_rows = session.execute(text(raw_sql), {"vid": video_id}).fetchall()
                if not chunk_rows:
                    yield (
                        'event: done\ndata: {"answer":"No relevant content found for this video '
                        "and data type. Try selecting 'Transcript' or generate summaries first.\"}\n\n"
                    )
                    return

            if chunk_rows:
                context_pieces = [f"Chunk: {row[0]}" for row in chunk_rows]
                context_for_generation = "\n\n".join(context_pieces)
                prompt_text = f"Query: {user_query}\nContext:\n{context_for_generation}"

                full_answer = ""
                for delta, _ in vllm_generate_stream(model_name, prompt_text):
                    if delta:
                        full_answer += delta
                        yield f"data: {json.dumps({'delta': delta})}\n\n"

                answer_html = md_safe(full_answer)
                yield f"data: {json.dumps({'answer': answer_html, 'done': True})}\n\n"
        except (requests.exceptions.RequestException, SQLAlchemyError, ValueError, KeyError) as e:
            logger.exception("Error during chat-video stream:")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            session.close()

    return Response(stream_with_context(generate()), content_type="text/event-stream")
