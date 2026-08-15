"""Chat blueprint — chat-channel and chat-video routes (page + API)."""

import requests as requests_lib
from flask import Blueprint, jsonify, render_template, request
from markupsafe import escape as _html_escape
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text

from app_config import (
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


@chat_bp.route("/api/chat-channel/<channel_name>", methods=["POST"])
def api_chat_channel(channel_name):
    """AJAX endpoint to handle chat queries for a given channel."""
    data = request.json or {}
    user_query = data.get("query", "").strip()
    data_type = data.get("data_type", "comprehensive_notes")
    model_name = data.get("model_name", "phi4:latest")

    if not user_query:
        return jsonify({"answer": "No query provided."}), 400

    logger.info(
        f"Chat-channel query for channel={channel_name}, "
        f"user_query='{user_query}', data_type='{data_type}', model='{model_name}'"
    )

    embeddings_view_map = {
        "comprehensive_notes": "public.summaries_v2_comprehensive_notes_embedding",
        "concise_summary": "public.summaries_v2_concise_summary_embedding",
        "key_topics": "public.summaries_v2_key_topics_embedding",
        "important_takeaways": "public.summaries_v2_important_takeaways_embedding",
        "transcript": "public.videos_transcript_no_ts_embedding",
    }
    selected_view = embeddings_view_map.get(data_type, embeddings_view_map["comprehensive_notes"])

    session = SessionLocal()
    final_answer = ""
    used_videos_html = ""
    try:
        user_query_emb = vllm_embed_chunk(user_query, model_name="nemo-nomic-embed-text-v1.5")

        if not user_query_emb:
            return jsonify({"answer": "Failed to get embedding for user query."}), 500

        sql_top_chunks = text(chat_channel_sql_templates[selected_view] % {"view": selected_view})
        # Build embedding array literal for PostgreSQL vector type (bypasses parameter binding)
        emb_literal = "ARRAY[" + ",".join(str(x) for x in user_query_emb) + "]::vector"
        sql_with_emb = sql_top_chunks.compile().string.replace(":q_emb", emb_literal)
        chunk_rows = session.execute(text(sql_with_emb), {"chan": channel_name}).fetchall()
        if not chunk_rows:
            final_answer = "No relevant content found for this channel and data type."
        else:
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

            prompt_str = f"""
Context:
{context_for_generation}

User Query:
{user_query}

Please provide a concise answer:
"""

            final_answer = vllm_generate_chunk(model_name, prompt_str)

            if not final_answer:
                final_answer = "No answer was returned by the model."

            if unique_videos:
                used_videos_html = "<h4>Videos used in Context:</h4>\n<ul>\n"
                for vid_id, vid_title in unique_videos.items():
                    safe_vid_id = _html_escape(vid_id)
                    safe_vid_title = _html_escape(vid_title)
                    used_videos_html += f"""
<li>
    <a href="https://www.youtube.com/watch?v={safe_vid_id}" target="_blank">
        <svg style="fill:#333; height:1em; width:1em;" version="1.1"
             xmlns="http://www.w3.org/2000/svg"
             xmlns:xlink="http://www.w3.org/1999/xlink"
             viewBox="0 0 48 48" xml:space="preserve">
            <use href="#icon-summarizeYouTube" xlink:href="#icon-summarizeYouTube"></use>
        </svg>
    </a>
    &nbsp;
    <a href="/chat-video/{safe_vid_id}">
        <svg xmlns="http://www.w3.org/2000/svg" height="24px"
             viewBox="0 -960 960 960" width="24px">
        <!-- SVG icon (truncated for readability) -->
        </svg>
    </a>
    {safe_vid_title}
</li>
"""
                used_videos_html += "</ul>\n"
            else:
                used_videos_html = ""

    except (requests_lib.exceptions.RequestException, SQLAlchemyError, ValueError, KeyError) as e:
        logger.exception("Error during chat-channel flow:")
        return jsonify({"answer": f"Error: {e!s}"}), 500
    finally:
        session.close()

    final_answer_html = md_safe(final_answer)
    if used_videos_html:
        final_answer_html += used_videos_html

    return jsonify({"answer": final_answer_html})


@chat_bp.route("/chat-video/<video_id>", methods=["GET"])
def chat_video_page(video_id):
    """Renders a page that allows chatting with a single video's content."""
    session = SessionLocal()
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


@chat_bp.route("/api/chat-video/<video_id>", methods=["POST"])
def api_chat_video(video_id):
    """AJAX endpoint for chatting with a single video's content."""
    data = request.json or {}
    user_query = data.get("query", "")
    data_type = data.get("data_type", "comprehensive_notes")
    model_name = data.get("model_name", "nemo-qwen3.6-35b-a3b-nvfp4")

    logger.info(
        f"Chat-video query for video_id={video_id}, user_query={user_query}, data_type={data_type}, model={model_name}"
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
    try:
        user_query_emb = vllm_embed_chunk(user_query, model_name="nemo-nomic-embed-text-v1.5")

        if not user_query_emb:
            return jsonify({"answer": "Failed to get embedding for user query."}), 500

        sql_top_chunks = text(chat_video_sql_templates[selected_table] % {"view": selected_table})
        chunk_rows = session.execute(sql_top_chunks, {"q_emb": user_query_emb, "vid": video_id}).fetchall()

        if not chunk_rows:
            final_answer = "No relevant content found for this video and data type."
        else:
            context_pieces = [f"Chunk: {row[0]}" for row in chunk_rows]
            context_for_generation = "\n\n".join(context_pieces)

            prompt_text = f"Query: {user_query}\nContext:\n{context_for_generation}"
            final_answer = vllm_generate_chunk(model_name, prompt_text)

            if not final_answer:
                final_answer = "No answer was returned by the model."
    except (requests_lib.exceptions.RequestException, SQLAlchemyError, ValueError, KeyError) as e:
        logger.exception("Error while handling chat-video")
        final_answer = f"Error: {e}"
    finally:
        session.close()

    final_answer_html = md_safe(final_answer)

    return jsonify({"answer": final_answer_html})
