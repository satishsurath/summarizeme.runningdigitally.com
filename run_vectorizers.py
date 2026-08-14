#!/usr/bin/env python3
# run_vectorizers.py
# Create PGAI vectorizers for embeddings — works with both vLLM and Ollama.

import os
import sys

import psycopg2
from dotenv import load_dotenv


def build_embedding_func(use_vllm):
    """Return the embedding SQL fragment for vLLM or Ollama mode."""
    if use_vllm:
        embed_host = os.getenv("VLLM_EMBED_HOST", "localhost")
        embed_port = os.getenv("VLLM_EMBED_PORT", "8001")
        embed_api_key = os.getenv("VLLM_EMBED_API_KEY", "")
        embed_url = f"http://{embed_host}:{embed_port}/v1"
        embed_model = "nemo-nomic-embed-text-v1.5"
# NOTE: PGAI embeds the API key in the vectorizer definition SQL.
        # This is stored in the pgai_vectorizer table in Postgres.
        # Protect the database from unauthorized access.
        return f"ai.embedding_openai('{embed_model}', 768, api_key => '{embed_api_key}', base_url => '{embed_url}')"
    else:
        ollama_host = os.getenv("REMOTE_OLLAMA_HOST", "localhost")
        return f"ai.embedding_ollama('nomic-embed-text', 768, base_url => 'http://{ollama_host}:11434')"


TRANSCRIPT_SQL = """
SELECT ai.create_vectorizer(
    'public.videos'::regclass,
    embedding => {embed_func},
    chunking => ai.chunking_recursive_character_text_splitter(
        'transcript_no_ts',
        1000,
        200,
        separators => array[E'\\n\\n', E'\\n', '.', '?', '!']
    ),
    formatting => ai.formatting_python_template(
        'Video Title: $title\\nTranscript chunk:\\n$chunk'
    ),
    indexing => ai.indexing_default()
);
"""

SUMMARIES_V2_TEMPLATE = """
SELECT ai.create_vectorizer(
    'public.summaries_v2'::regclass,
    destination => '{destination}',
    embedding => {embed_func},
    chunking => ai.chunking_recursive_character_text_splitter(
        '{column}',
        2000,
        200,
        separators => array[
            E'^# ',
            E'^## ',
            E'^### ',
            E'^#### ',
            E'^##### ',
            E'\\n\\n',
            E'\\n',
            '.',
            '?',
            '!'
        ],
        is_separator_regex => true
    ),
    formatting => ai.formatting_python_template(
        'Video ID: $video_id\\nVideo Title: $video_title\\n{label} chunk:\\n$chunk'
    ),
    indexing => ai.indexing_default()
);
"""


def main():
    load_dotenv()

    DB_URL = os.environ["DATABASE_URL"]
    use_vllm = os.getenv("VLLM_EMBED_HOST") is not None

    print(f"[INFO] Using {'vLLM' if use_vllm else 'Ollama'} for embeddings")
    print(f"[INFO] DB_URL: {DB_URL}")

    embed_func = build_embedding_func(use_vllm)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    try:
        # 1) Ensure pgai extension installed
        print("[INFO] Ensuring pgai extension is installed...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS ai CASCADE;")
        conn.commit()

        # 2) Create vectorizer for transcript
        print("[INFO] Creating transcript vectorizer for videos.transcript_no_ts...")
        cur.execute(TRANSCRIPT_SQL.format(embed_func=embed_func))

        # 3) Create vectorizers for summaries_v2 columns
        vectorizer_configs = [
            ("summaries_v2_concise_summary_embedding", "concise_summary", "Concise Summary"),
            ("summaries_v2_key_topics_embedding", "key_topics", "Key Topics"),
            ("summaries_v2_important_takeaways_embedding", "important_takeaways", "Important Takeaways"),
            ("summaries_v2_comprehensive_notes_embedding", "comprehensive_notes", "Comprehensive Notes"),
        ]

        for dest, col, label in vectorizer_configs:
            sql = SUMMARIES_V2_TEMPLATE.format(
                destination=dest,
                column=col,
                label=label,
                embed_func=embed_func,
            )
            print(f"[INFO] Creating {label} vectorizer ({dest})...")
            cur.execute(sql)

        conn.commit()
        print("[SUCCESS] All vectorizers created successfully!")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Unable to create vectorizers: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
