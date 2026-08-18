# run_vectorizers.py
# Plain Python vectorization using vLLM directly - no PGAI ai extension required

import json
import logging
import os
import re

import httpx
import psycopg2
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def split_into_chunks(text, chunk_size=1500, overlap=300):
    """Split text into sentence-aware overlapping chunks (~300-500 words / ~1500 chars)."""
    if not text:
        return []

    chunks = []
    start = 0
    text = text.strip()

    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:])
            break

        # Try to break at a sentence boundary within the overlap window
        chunk = text[start:end]
        for pattern in [r"\.\s+", r"\n\s*\n", r"(?<=[.!?])\s"]:
            match = re.search(pattern, chunk[-overlap:])
            if match:
                actual_end = start + (len(chunk) - overlap) + match.end()
                if actual_end > start + chunk_size // 2:
                    end = actual_end
                    break

        chunks.append(text[start:end].strip())
        start = max(start + 1, end - overlap)

    return [c for c in chunks if c.strip()]


def get_embedding(text, model_name="nemo-nomic-embed-text-v1.5", is_query=False):
    """Get embedding from vLLM directly using httpx."""
    embed_host = os.getenv("VLLM_EMBED_HOST", "localhost")
    embed_port = os.getenv("VLLM_EMBED_PORT", "8001")

    if not embed_host:
        return None

    if (
        text
        and isinstance(text, str)
        and not (text.startswith("search_query: ") or text.startswith("search_document: "))
    ):
        prefix = "search_query: " if is_query else "search_document: "
        text = f"{prefix}{text}"

    for attempt in range(3):
        try:
            resp = httpx.post(
                f"http://{embed_host}:{embed_port}/v1/embeddings",
                json={"model": model_name, "input": [text]},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.getenv('VLLM_EMBED_API_KEY', 'local-noauth')}",
                },
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            items = result.get("data") or []
            return items[0].get("embedding") if items else None
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as e:
            if attempt < 2:
                logger.warning("vLLM embed error (attempt %d/3): %s", attempt + 1, e)
                import time

                time.sleep(2**attempt)
                continue
            logger.error("vLLM embed error: %s", e)
            return None


def ensure_pgvector(cur, conn):
    """Ensure pgvector extension is installed."""
    logger.info("Ensuring pgvector extension is installed...")
    original_autocommit = conn.autocommit
    try:
        conn.autocommit = True
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    finally:
        conn.autocommit = original_autocommit
        if not conn.autocommit:
            conn.commit()


def ensure_destination_table(cur, conn, table_name):
    """Create the destination embeddings table if it doesn't exist."""
    from psycopg2 import sql

    # Extract table name without schema prefix for index naming
    table_only = table_name.split(".")[-1] if "." in table_name else table_name
    index_name = f"{table_only}_embedding_idx"
    table_ref = sql.Identifier(table_only)
    index_ref = sql.Identifier(index_name)
    source_id_idx_ref = sql.Identifier(f"{table_only}_source_id_idx")
    cur.execute(
        sql.SQL(
            "CREATE TABLE IF NOT EXISTS {} ("
            "id BIGSERIAL PRIMARY KEY, "
            "source_id VARCHAR(100) NOT NULL, "
            "source_table VARCHAR(100) NOT NULL, "
            "source_column VARCHAR(100) NOT NULL, "
            "chunk_order INTEGER NOT NULL, "
            "content TEXT NOT NULL, "
            "embedding vector(768) NOT NULL, "
            "UNIQUE (source_id, source_table, source_column, chunk_order));"
        ).format(table_ref)
    )
    cur.execute(
        sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} USING hnsw (embedding vector_cosine_ops);").format(
            index_ref, table_ref
        )
    )
    cur.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (source_id);").format(source_id_idx_ref, table_ref))
    conn.commit()


def upsert_embedding(cur, conn, table_name, source_id, source_table, source_column, chunk_order, content, embedding):
    """Insert or update an embedding."""
    from psycopg2 import sql

    table_only = table_name.split(".")[-1] if "." in table_name else table_name
    cur.execute(
        sql.SQL(
            "INSERT INTO {} (source_id, source_table, source_column, chunk_order, content, embedding) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (source_id, source_table, source_column, chunk_order) "
            "DO UPDATE SET content = EXCLUDED.content, embedding = EXCLUDED.embedding"
        ).format(sql.Identifier(table_only)),
        (str(source_id), source_table, source_column, chunk_order, content, embedding),
    )


def process_column(
    cur,
    conn,
    table_name,
    column_name,
    id_column="id",
    destination_prefix="",
    chunk_size=1000,
    overlap=200,
):
    """Process a column and generate embeddings."""
    logger.info("Processing %s.%s...", table_name, column_name)

    dest_table = (
        f"{destination_prefix}{column_name}_embedding"
        if destination_prefix
        else f"{table_name}_{column_name}_embedding"
    )

    ensure_destination_table(cur, conn, dest_table)

    from psycopg2 import sql

    # Strip schema prefix for sql.Identifier (dots are treated as part of the name)
    table_only = table_name.split(".")[-1] if "." in table_name else table_name
    table_ref = sql.Identifier(table_only)
    id_col_ref = sql.Identifier(id_column)
    col_ref = sql.Identifier(column_name)
    dest_table_ref = sql.Identifier(dest_table.split(".")[-1] if "." in dest_table else dest_table)

    failed_row_ids: set[str] = set()

    while True:
        cur.execute(
            sql.SQL(
                "SELECT src.{}, src.{} FROM {} src "
                "WHERE NOT EXISTS ("
                "    SELECT 1 FROM {} dst WHERE dst.source_id = CAST(src.{} AS VARCHAR)"
                ") LIMIT 100;"
            ).format(id_col_ref, col_ref, table_ref, dest_table_ref, id_col_ref)
        )

        rows = cur.fetchall()
        rows_to_process = [r for r in rows if str(r[0]) not in failed_row_ids]
        if not rows_to_process:
            break

        logger.info("Processing batch of %d rows for %s.%s...", len(rows_to_process), table_name, column_name)

        for row_id, content in rows_to_process:
            if not content or not content.strip():
                failed_row_ids.add(str(row_id))
                continue

            chunks = split_into_chunks(content, chunk_size, overlap)
            if not chunks:
                failed_row_ids.add(str(row_id))
                continue

            # Format template based on table
            if "videos" in table_name:
                cur.execute(sql.SQL("SELECT title FROM {} WHERE {} = %s").format(table_ref, id_col_ref), (row_id,))
                title_row = cur.fetchone()
                title = title_row[0] if title_row else ""
                fmt_template = f"Video Title: {title}\nTranscript chunk:\n{{chunk}}"
            else:
                cur.execute(
                    sql.SQL("SELECT video_id, video_title FROM {} WHERE {} = %s").format(table_ref, id_col_ref),
                    (row_id,),
                )
                ctx_row = cur.fetchone()
                video_id = ctx_row[0] if ctx_row else ""
                video_title = ctx_row[1] if ctx_row else ""
                col_label = column_name.replace("_", " ").title()
                fmt_template = f"Video ID: {video_id}\nVideo Title: {video_title}\n{col_label} chunk:\n{{chunk}}"

            row_embeddings = []
            all_succeeded = True

            for order, chunk_text in enumerate(chunks):
                formatted = fmt_template.format(chunk=chunk_text)
                embedding = get_embedding(formatted, is_query=False)
                if embedding is None:
                    all_succeeded = False
                    break
                row_embeddings.append((order, formatted, embedding))

            if all_succeeded:
                for order, formatted, embedding in row_embeddings:
                    upsert_embedding(
                        cur, conn, dest_table, row_id, table_name, column_name, order, formatted, embedding
                    )
                conn.commit()
            else:
                logger.warning(
                    "Skipping commit for row %s due to embedding failure; marking row as failed for this run.", row_id
                )
                conn.rollback()
                failed_row_ids.add(str(row_id))

    logger.info("Done with %s.%s", table_name, column_name)


def main():
    # 1) Load environment
    load_dotenv()

    DB_URL = os.environ.get("DATABASE_URL")
    if not DB_URL:
        logger.error("DATABASE_URL not set in environment")
        return

    logger.info("Connecting to database...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    try:
        # Ensure pgvector extension
        ensure_pgvector(cur, conn)

        # Process videos.transcript_no_ts
        process_column(
            cur,
            conn,
            table_name="public.videos",
            column_name="transcript_no_ts",
            id_column="video_id",
            destination_prefix="",
            chunk_size=1000,
            overlap=200,
        )

        # Process summaries_v2 columns
        for col in ["concise_summary", "key_topics", "important_takeaways", "comprehensive_notes"]:
            process_column(
                cur,
                conn,
                table_name="public.summaries_v2",
                column_name=col,
                id_column="id",
                destination_prefix="summaries_v2_",
                chunk_size=2000,
                overlap=200,
            )

        logger.info("All embeddings processed successfully!")

    except Exception as e:
        conn.rollback()
        logger.error("Error during vectorization: %s", e)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
