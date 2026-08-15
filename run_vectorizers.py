# run_vectorizers.py
# Plain Python vectorization using vLLM directly - no PGAI ai extension required

import os
import re
import psycopg2
from dotenv import load_dotenv

# Import vLLM embedding function
try:
    from openai import OpenAI as _OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False


def split_into_chunks(text, chunk_size=1000, overlap=200):
    """Split text into overlapping chunks."""
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
        
        # Try to break at a sentence boundary
        chunk = text[start:end]
        # Look for a sentence boundary within the last 200 chars
        for pattern in [r'\.\s+', r'\n\s*\n', r'(?<=[.!?])\s']:
            match = re.search(pattern, chunk[-overlap:])
            if match:
                end = start + len(chunk[:end]) - (len(chunk) - (match.start() + end - start))
                actual_end = start + len(chunk[:end]) - (len(chunk) - match.end())
                if actual_end > start + chunk_size // 2:  # Don't make chunks too small
                    end = start + len(chunk[:end]) - (len(chunk) - actual_end)
                    break
        
        chunks.append(text[start:end].strip())
        start = end - overlap
    
    return [c for c in chunks if c.strip()]


def get_embedding(text, model_name="nomic-ai/nomic-embed-text-v1.5"):
    """Get embedding from vLLM directly."""
    embed_host = os.getenv("VLLM_EMBED_HOST", "localhost")
    embed_port = os.getenv("VLLM_EMBED_PORT", "8001")
    
    if not embed_host:
        return None
    
    url = f"http://{embed_host}:{embed_port}"
    
    if not _HAS_OPENAI:
        print(f"[ERROR] openai SDK not installed")
        return None
    
    client = _OpenAI(base_url=url, api_key="not-needed")
    response = client.embeddings.create(
        model=model_name,
        input=[text],
    )
    return response.data[0].embedding if response.data else None


def ensure_pgvector(cur, conn):
    """Ensure pgvector extension is installed."""
    print("[INFO] Ensuring pgvector extension is installed...")
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    conn.commit()


def ensure_destination_table(cur, conn, table_name):
    """Create the destination embeddings table if it doesn't exist."""
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id BIGSERIAL PRIMARY KEY,
            source_id BIGINT NOT NULL,
            source_table VARCHAR(100) NOT NULL,
            source_column VARCHAR(100) NOT NULL,
            chunk_order INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector(768) NOT NULL
        );
    """)
    # Create index for vector similarity search
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS {table_name}_embedding_idx 
        ON {table_name} USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)
    conn.commit()


def upsert_embedding(cur, conn, table_name, source_id, source_table, source_column, 
                     chunk_order, content, embedding):
    """Insert or update an embedding."""
    cur.execute(f"""
        INSERT INTO {table_name} (source_id, source_table, source_column, chunk_order, content, embedding)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (source_id, source_table, source_column, chunk_order, content, embedding))


def process_column(table_name, column_name, id_column="id", 
                   destination_prefix="", chunk_size=1000, overlap=200):
    """Process a column and generate embeddings."""
    print(f"[INFO] Processing {table_name}.{column_name}...")
    
    dest_table = f"{destination_prefix}{column_name}_embedding" if destination_prefix else f"{table_name}_{column_name}_embedding"
    
    ensure_destination_table(cur, conn, dest_table)
    
    # Get all rows that need processing
    cur.execute(f"""
        SELECT {id_column}, {column_name} FROM {table_name}
        WHERE {id_column} NOT IN (
            SELECT DISTINCT source_id FROM {dest_table}
        )
        LIMIT 100;
    """)
    
    rows = cur.fetchall()
    if not rows:
        print(f"  [INFO] No new rows to process for {table_name}.{column_name}")
        return
    
    print(f"  [INFO] Processing {len(rows)} rows...")
    
    for row_id, content in rows:
        if not content or not content.strip():
            continue
        
        chunks = split_into_chunks(content, chunk_size, overlap)
        
        # Format template based on table
        if "videos" in table_name:
            # Get video title for context
            cur.execute(f"SELECT title FROM {table_name} WHERE {id_column} = %s", (row_id,))
            title_row = cur.fetchone()
            title = title_row[0] if title_row else ""
            fmt_template = f"Video Title: {title}\nTranscript chunk:\n{{chunk}}"
        else:
            # Get video_id and video_title for context
            cur.execute(f"SELECT video_id, video_title FROM {table_name} WHERE {id_column} = %s", (row_id,))
            ctx_row = cur.fetchone()
            video_id = ctx_row[0] if ctx_row else ""
            video_title = ctx_row[1] if ctx_row else ""
            fmt_template = f"Video ID: {video_id}\nVideo Title: {video_title}\n{column_name.replace('_', ' ').title()} chunk:\n{{chunk}}"
        
        for order, chunk_text in enumerate(chunks):
            formatted = fmt_template.format(chunk=chunk_text)
            embedding = get_embedding(formatted)
            
            if embedding:
                upsert_embedding(cur, conn, dest_table, row_id, table_name, column_name,
                               order, formatted, embedding)
        
        conn.commit()
    
    print(f"  [OK] Done with {table_name}.{column_name}")


def main():
    # 1) Load environment
    load_dotenv()
    
    DB_URL = os.environ.get("DATABASE_URL")
    if not DB_URL:
        print("[ERROR] DATABASE_URL not set in environment")
        return
    
    print(f"[INFO] Connecting to database...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    try:
        # Ensure pgvector extension
        ensure_pgvector(cur, conn)
        
        # Process videos.transcript_no_ts
        process_column(
            table_name="public.videos",
            column_name="transcript_no_ts",
            id_column="id",
            destination_prefix="",
            chunk_size=1000,
            overlap=200
        )
        
        # Process summaries_v2 columns
        for col in ["concise_summary", "key_topics", "important_takeaways", "comprehensive_notes"]:
            process_column(
                table_name="public.summaries_v2",
                column_name=col,
                id_column="id",
                destination_prefix="summaries_v2_",
                chunk_size=2000,
                overlap=200
            )
        
        print("[SUCCESS] All embeddings processed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Error during vectorization: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
