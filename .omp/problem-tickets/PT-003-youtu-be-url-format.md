# PT-003: Single Video Download Failing — youtu.be URL Format Not Detected

**Date:** 2026-08-15  
**Status:** Fixed  
**PR:** #7 (fix/chat-model-selector) — same commit as PT-002

## Problem
Downloading a single video using short URL format failed:
```
https://youtu.be/-IGB6Avxwgo?si=PmhWpBlk0ZmO3RnV
```
Long format worked:
```
https://www.youtube.com/watch?v=-IGB6Avxwgo
```

## Root Cause
`youtube_utils.py::get_channel_and_videos()` only checked for `"youtube.com/watch"` in the URL:
```python
if not entries and data.get("id") and "youtube.com/watch" in channel_url:
```
Short URLs use `youtu.be/` format which was not detected.

## Fix Applied
Updated the condition to also check for `youtu.be/`:
```python
if not entries and data.get("id") and ("youtube.com/watch" in channel_url or "youtu.be/" in channel_url):
```

## Verification
- Downloaded video `-IGB6Avxwgo` via `youtu.be` URL → completed successfully
- Video stored in DB with correct title: "You Don't need to use Cloud AI! Switchyard and Nemotron 3.5 Lightning"
- All 46 unit tests pass

## Files Changed
- `youtube_utils.py` — line 185: added `youtu.be/` check
