# Problem Tickets

Operational issue tracking for the SummarizeMe project.

## Directory Structure

```
docs/problem-tickets/
├── PT-001-summarization-vllm-reasoning.md  # Summarization vLLM 404 + Qwen3.6 reasoning content
├── PT-002-chat-model-selector.md           # Chat deprecated model selector not working
├── PT-003-youtu-be-url-format.md           # Single video download youtu.be format not detected
├── PT-004-db-persistence.md                # Database not persistent on Docker rebuild
├── PT-005-chat-embedding-404.md            # Chat embedding 404 fix
├── PT-006-missing-required-status-checks.md # PR merged despite failed lint; branch protection gap
├── PT-007-chat-thinking-block-post-stream.md # Chat thinking block dissolving into main answer post-stream
└── 2026-08-17-status-page-and-chat-fixes.md  # Status page errors, chat failures, video refresh

## Format

Each problem ticket follows a consistent format:

- **Title**: Brief description of the issue
- **Problem**: What was broken
- **Root Cause**: Why it happened
- **Fix**: How it was resolved
- **Verification**: How to confirm the fix works
- **Status**: open | resolved | closed

## Creating a New Ticket

1. Create a new file: `PT-NNN-<short-description>.md`
2. Use the next available number (PT-006, PT-007, etc.)
3. Fill in all sections
4. Reference related code changes in the Fix section
