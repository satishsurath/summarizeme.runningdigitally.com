-- Create the pgvector extension in the primary database.
-- The chat (RAG) SQL templates use `::vector` casts and the `<=>` cosine
-- distance operator. The pgvector/pgvector:pg17 image ships the extension
-- files; this makes the extension available in the app database from first
-- boot. run_vectorizers.py re-ensures this on every run.
CREATE EXTENSION IF NOT EXISTS vector;
