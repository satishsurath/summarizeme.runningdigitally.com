# PT-004: Database Not Persistent — Data Lost on Docker Rebuild

**Date:** 2026-08-15  
**Status:** Fixed  
**PR:** #7 (fix/chat-model-selector) — same commit as PT-002

## Problem
Database data (videos, summaries, folders) was lost every time Docker containers were rebuilt/restarted. All YouTube video data disappeared.

## Root Cause
Two issues:
1. **Wrong data directory:** The TimescaleDB image stores data at `/home/postgres/pgdata/data`, not `/var/lib/postgresql/data`. The volume mount was targeting the wrong path.
2. **Docker named volume:** Was using a Docker-managed named volume `postgres_data` instead of a host path, making data inaccessible on the local disk.

## Fix Applied
1. **docker-compose.dev.yml:** Changed volume mount from `postgres_data:/var/lib/postgresql/data` to `./.data/postgres:/home/postgres/pgdata/data`
2. **docker-compose.dev.yml:** Removed unused `postgres_data` named volume
3. **.gitignore:** Added `.data/` to prevent local db data from being committed

## Verification
- Database data persists at `./.data/postgres/` on local disk
- Data survives Docker restarts (`docker compose down` + `up`)
- PostgreSQL query `SHOW data_directory;` confirms `/home/postgres/pgdata/data`
- All tables (videos, summaries_v2, video_folders, etc.) persist across restarts

## Files Changed
- `docker-compose.dev.yml` — db volume mount path, removed postgres_data volume
- `.gitignore` — added `.data/`
