# SummarizeMe Architecture Analysis: Split into Next.js Frontend + Flask Backend

**Date:** 2026-08-17  
**Branch:** main (891eed5)  
**Repository:** `/Users/satishsurath/Developer/summarizeme.runningdigitally.com`

---

## 1. Current Architecture

### 1.1 Monolithic Flask Application

The application is a **single Flask process** serving both server-rendered pages (Jinja2) and JSON API endpoints.

```
app.py                          # Flask app factory, blueprint registration
├── blueprints/main.py          # Page routes (index, status, videos, summaries, transcripts)
├── blueprints/api.py           # JSON API routes (channels, videos, summarize, tasks)
├── blueprints/chat.py          # Chat routes (channel chat, video chat)
├── blueprints/admin.py         # Admin routes (settings, roles)
├── app_config.py               # Shared config: DB, vLLM URLs, SQL templates, md_safe, require_role
├── db/models.py                # SQLAlchemy models: Video, VideoFolder, SummariesV2, SyncJob, User
├── summarizer_v2.py            # Chunking, prompt generation, vLLM generation & embedding calls
├── youtube_utils.py            # yt-dlp/pytube wrappers: transcript download, channel listing
├── auth_utils.py               # Cloudflare Access JWT validation, dev auth, user provisioning
├── templates/                  # 10 Jinja2 HTML templates
├── static/js/                  # 8 vanilla JS files (~1500 LOC total)
├── static/css/                 # Tailwind CDN + custom CSS
├── Dockerfile                  # Production: gunicorn on port 8000
├── Dockerfile.dev              # Dev: flask run on port 5000
└── docker-compose.dev.yml      # db (TimescaleDB), redis, app
```

### 1.2 Data Model (5 tables)

| Table | Key Fields |
|-------|-----------|
| `videos` | `video_id` (PK), `title`, `upload_date`, `transcript_with_ts`, `transcript_no_ts`, `tokens_with_ts`, `tokens_no_ts` |
| `video_folders` | `id` (PK), `folder_name`, `original_playlist_id`, `video_id` (FK), `last_modified` |
| `summaries_v2` | `id` (PK), `video_id` (FK), `video_title`, `model_name`, `date_generated`, `concise_summary`, `key_topics`, `important_takeaways`, `comprehensive_notes` |
| `sync_jobs` | `id` (PK), `start_time`, `end_time`, `status`, `message` |
| `users` | `id` (PK), `email` (unique), `role` (admin/member/reader) |

### 1.3 Current API Surface

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| GET | `/` | Index page (Jinja2) | Cloudflare JWT |
| GET | `/videos/<channel>` | Videos page (Jinja2) | Cloudflare JWT |
| GET | `/summaries_v2/<id>` | Summary page (Jinja2) | Cloudflare JWT |
| GET | `/transcript/<video_id>` | Transcript page (Jinja2) | Cloudflare JWT |
| GET | `/chat-channel/<channel>` | Chat page (Jinja2) | Cloudflare JWT |
| GET | `/chat-video/<video_id>` | Video chat page (Jinja2) | Cloudflare JWT |
| GET | `/status` | Status page (Jinja2) | Cloudflare JWT |
| GET | `/admin-settings` | Admin settings page (Jinja2) | admin role |
| POST | `/admin-update-role` | Update user role (form) | admin role |
| POST | `/admin-add-user` | Add user (form) | admin role |
| GET | `/health` | Health check | None |
| POST | `/api/channel/start` | Start channel download | admin role |
| GET | `/api/channel/status/<id>` | Poll download status | None |
| GET | `/api/videos/<channel>` | Paginated video list | None |
| POST | `/api/summarize_v2` | Start summarization | None |
| GET | `/api/summarize_v2/status/<id>` | Poll summarize status | None |
| GET | `/api/active-tasks` | List active tasks | None |
| GET | `/api/channels` | List channels | None |
| POST | `/api/channels/rename` | Rename channel | admin role |
| POST | `/api/channels/delete` | Delete channel | admin role |
| POST | `/api/channels/refresh` | Refresh channel | admin role |
| POST | `/api/chat-channel/<channel>` | Chat with channel | Cloudflare JWT |
| POST | `/api/chat-video/<video_id>` | Chat with video | Cloudflare JWT |

### 1.4 Current Frontend Characteristics

- **Jinja2 server-rendered pages** with Tailwind CSS via CDN
- **Vanilla JavaScript** (no framework) — 8 files, ~1500 lines total
- **Client-side fetch calls** to `/api/*` endpoints
- **Polling-based** task status updates (5s interval)
- **Inline `<script>` blocks** in templates for page-specific JS (`channel_name` variable)
- **Dark mode** via localStorage + CSS class toggle
- **No SSR/SSG** — every route is a full page reload
- **No component system** — HTML is duplicated across templates

### 1.5 Background Processing

- **Thread-based** background tasks (daemon threads) with in-memory `dict` status storage
- Two task types: channel downloads and summarization
- Redis is configured in `docker-compose.dev.yml` but **not used** by the app
- No Celery, no job queue, no retry logic

### 1.6 External Dependencies

| Service | Role |
|---------|------|
| vLLM (generation, port 8000) | LLM text generation (Qwen 3.6 35B) |
| vLLM (embedding, port 8001) | Embedding generation (nomic-embed-text) |
| PostgreSQL/TimescaleDB | Primary data store |
| Redis | Configured but unused |
| yt-dlp (wrapper service) | YouTube metadata + transcript extraction |
| Cloudflare Access | JWT-based authentication |

---

## 2. Feasibility Assessment

### 2.1 Can it be split? **Yes, straightforwardly.**

The application already has a **clear API boundary** — the `/api/*` routes are pure JSON endpoints that the Jinja2 pages consume via `fetch()`. This makes the split mechanical rather than architectural.

### 2.2 What moves where

| Current Location | Next.js Frontend | Flask Backend |
|-----------------|:---:|:---:|
| Jinja2 templates | ✅ All 10 templates → React/Next.js components | ❌ Removed |
| Static JS files | ✅ All 8 files → React components/hooks | ❌ Removed |
| Static CSS | ✅ Tailwind config + custom CSS | ❌ Removed |
| `/api/*` routes | ❌ | ✅ All preserved |
| `blueprints/main.py` page routes | ✅ → Next.js App Router pages | ❌ Removed |
| `blueprints/chat.py` page routes | ✅ → Next.js pages | ✅ API routes only |
| `blueprints/admin.py` page routes | ✅ → Next.js admin pages | ✅ API routes only |
| `db/models.py` | ❌ | ✅ SQLAlchemy models |
| `summarizer_v2.py` | ❌ | ✅ Core logic |
| `youtube_utils.py` | ❌ | ✅ Core logic |
| `auth_utils.py` | ✅ JWT verification middleware | ✅ Cloudflare JWT validation |
| `app_config.py` | ✅ Config constants | ✅ DB, vLLM, SQL templates |
| `wsgi.py` | ❌ | ✅ Entry point |
| `requirements.txt` | ❌ | ✅ Python deps |
| `Dockerfile` | ✅ Separate Dockerfile | ✅ Separate Dockerfile |

### 2.3 What stays in Flask (Backend)

1. **All `/api/*` JSON endpoints** — already structured correctly
2. **Database models** (SQLAlchemy)
3. **Background task orchestration** — thread-based (or Celery/Redis later)
4. **vLLM integration** (generation + embedding)
5. **YouTube acquisition** (yt-dlp wrappers, transcript parsing)
6. **Cloudflare JWT validation**
7. **Role-based access control** (`require_role` decorator)
8. **Markdown-safe rendering** (`md_safe`)
9. **SQL templates** for vector similarity search

### 2.4 What moves to Next.js (Frontend)

1. **All Jinja2 templates** → React/Next.js App Router pages
2. **All vanilla JS** → React components, hooks, state management
3. **Dark mode** → CSS variables or Tailwind dark mode
4. **Navigation/layout** → Next.js `layout.tsx`
5. **Client-side fetch calls** → Already use `fetch()`, just restructured
6. **Tailwind CSS** → Next.js Tailwind config (build-time compilation)
7. **Icon system** → React icon components

### 2.5 What can be improved in the split

| Issue | Current | After Split |
|-------|---------|-------------|
| Task status polling | 5s interval, in-memory dict | Server-Sent Events or WebSocket |
| Background tasks | In-memory dicts, daemon threads | Redis + Celery or BullMQ |
| Auth | Cloudflare JWT only | Next.js middleware + Flask JWT |
| State management | Global JS variables | React state + SWR/React Query |
| SEO | Server-rendered HTML | Next.js SSR/SSG for summary pages |
| Build step | CDN Tailwind at runtime | Build-time Tailwind compilation |
| Type safety | None | TypeScript across both services |
| File upload | None | Next.js API routes for thumbnails |

---

## 3. Proposed Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Next.js Frontend                        │
│  (App Router, TypeScript, Tailwind build-time)              │
│                                                             │
│  Pages:                                                     │
│    /          → Home (channel list)                         │
│    /videos/[channel] → Channel videos                       │
│    /summaries/[id]   → Summary view                         │
│    /transcripts/[id] → Transcript view                      │
│    /chat/channel/[channel] → Channel chat                   │
│    /chat/video/[id]    → Video chat                         │
│    /status       → Task status dashboard                    │
│    /admin        → Admin panel                              │
│                                                             │
│  Components:                                                │
│    Layout (nav, dark mode, notifications)                   │
│    ChannelList, VideoCard, SummaryView                      │
│    ChatInterface, TaskPanel, AdminSettings                  │
│                                                             │
│  Data fetching:                                             │
│    Server Components (SSR) for initial page load            │
│    SWR/React Query for API data + caching                   │
│    Client components for interactive UI                     │
└──────────────────┬──────────────────────────────────────────┘
                   │  HTTP/JSON (fetch)
                   │  Base: http://flask-backend:8000
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                     Flask Backend                             │
│  (FastAPI or Flask, Pydantic models)                        │
│                                                             │
│  API Routes (/api/...):                                      │
│    Channels:  GET/POST/PUT/DELETE                           │
│    Videos:    GET (paginated, filtered, sorted)              │
│    Summaries: POST (trigger), GET (list)                    │
│    Chat:      POST (channel/video)                          │
│    Tasks:     GET (active), GET/<id> (status)               │
│    Admin:     POST (role, add user)                         │
│                                                             │
│  Services:                                                  │
│    YouTubeDownloader (yt-dlp wrapper)                       │
│    Summarizer (chunking, prompts, vLLM calls)               │
│    ChatService (embedding, vector search, LLM response)     │
│    AuthService (Cloudflare JWT, role check)                 │
│    TaskManager (Redis + Celery)                             │
│                                                             │
│  Data:                                                      │
│    PostgreSQL (TimescaleDB)                                 │
│    Redis (task queue, cache)                                │
└──────────────────┬──────────────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
  vLLM Gen     vLLM Embed    yt-dlp
  (port 8000)  (port 8001)   (wrapper)
```

---

## 4. Migration Strategy

### Phase 1: Backend API Hardening (no frontend changes)

1. **Move background tasks to Redis/Celery** — replace in-memory dicts with a proper queue
2. **Add Pydantic response models** — strict typing for all API responses
3. **Add API authentication middleware** — JWT token auth alongside Cloudflare
4. **Add rate limiting** — Flask-Limiter or middleware
5. **Add OpenAPI/Swagger docs** — `flask-openapi3` or `apistar`
6. **Add unit tests** — for all API endpoints

### Phase 2: Next.js Scaffolding

1. **Initialize Next.js 15+** with App Router, TypeScript, Tailwind
2. **Create Dockerfiles** for both services
3. **Update docker-compose** with Next.js dev/prod services
4. **Set up CORS** between Next.js and Flask
5. **Create API client library** — typed fetch wrapper (e.g., `@/lib/api.ts`)

### Phase 3: Page Migration (iterative, one page at a time)

1. **Home page** — channel list, download form
2. **Channel videos page** — video table, pagination, filtering, summarization trigger
3. **Summary view page** — rendered markdown
4. **Transcript view page** — transcript display
5. **Chat pages** — channel chat, video chat
6. **Status page** — task monitoring
7. **Admin page** — user management

### Phase 4: Enhancement

1. **Server Components** — SSR for SEO on summary/transcript pages
2. **SWR/React Query** — data fetching with caching, background refetch
3. **Real-time updates** — SSE or WebSocket for task progress
4. **Auth middleware** — Next.js middleware for protected routes
5. **Error boundaries** — graceful error handling
6. **Performance** — image optimization, lazy loading, code splitting

---

## 5. Risks & Considerations

### 5.1 Low Risk

- **API surface is stable** — existing `/api/*` endpoints work and are well-structured
- **Data model is simple** — 5 tables, no complex relationships
- **Frontend is vanilla JS** — no framework lock-in to migrate away from
- **No file uploads** — simplifies the split

### 5.2 Medium Risk

- **Chat interactivity** — the chat UI has message bubbles, typing indicators, and scroll management. This needs careful React conversion.
- **Task polling** — current 5s polling works but is inefficient. Should migrate to SSE/WebSocket.
- **Dark mode** — currently inline JS + localStorage. Can be done in Next.js but needs migration.
- **Cloudflare Access** — auth happens at the Cloudflare edge. Need to preserve this in the split.

### 5.3 High Risk

- **vLLM integration** — the summarization and chat flows involve multi-step LLM calls. These must stay on the backend (secrets, model access).
- **yt-dlp dependency** — runs on the backend. The wrapper service architecture must be preserved.
- **Vector similarity search** — PostgreSQL pgvector queries are backend-only.
- **In-memory task status** — the current daemon-thread + dict approach doesn't survive restarts. This is a bug regardless of the split.

### 5.4 Operational Impact

| Aspect | Before | After |
|--------|--------|-------|
| Docker containers | 1 (app) + db + redis | 2+ (frontend + backend) + db + redis |
| Deployment | Single image | Two images, coordinated deploy |
| Scaling | Monolithic | Independent scaling per service |
| CI/CD | Single pipeline | Two pipelines or monorepo pipeline |
| Local dev | `docker-compose up` | `docker-compose up` (same) |
| Production | Single gunicorn | Two services behind reverse proxy |

---

## 6. Recommended Tech Choices

| Component | Recommendation | Rationale |
|-----------|---------------|-----------|
| Next.js version | 15+ (App Router) | Latest stable, React 19, server components |
| Language | TypeScript | Type safety across API contract |
| State management | SWR or TanStack Query | Data fetching + caching for API calls |
| Styling | Tailwind CSS (build-time) | Already in use; build-time is faster |
| Backend framework | Keep Flask or migrate to FastAPI | Flask is proven; FastAPI gives auto OpenAPI + async |
| Task queue | Redis + Celery (Python) or BullMQ (Node) | Celery keeps Python stack; BullMQ gives real-time |
| Auth | Cloudflare Access (edge) + JWT (API) | Preserve existing; add token auth for SPA |
| API docs | OpenAPI/Swagger | Auto-generated from Pydantic (FastAPI) or flask-openapi3 |
| Testing | Jest/RTL (frontend) + pytest (backend) | Industry standard |

---

## 7. Estimated Effort

| Phase | Effort | Notes |
|-------|--------|-------|
| 1. Backend hardening | 2-3 days | Task queue, Pydantic models, auth middleware |
| 2. Next.js scaffolding | 1 day | Project setup, Dockerfiles, docker-compose |
| 3. Page migration | 5-7 days | 7 pages, iterative, one at a time |
| 4. Enhancement | 3-5 days | SSR, SWR, SSE, auth middleware |
| **Total** | **~3-4 weeks** | Assuming one developer, part-time |

---

## 8. Conclusion

**The split is highly feasible and recommended.** The application already has a clean API boundary (`/api/*` routes), and the frontend is vanilla JavaScript with no framework lock-in. The main work is:

1. **Converting 10 Jinja2 templates** → React/Next.js components (~2-3 days)
2. **Converting 8 vanilla JS files** → React hooks/components (~2-3 days)
3. **Fixing the in-memory task status** → Redis-backed queue (critical bug fix, 1 day)
4. **Docker/infra changes** → Two services instead of one (1 day)

The existing API surface is stable and well-structured, making the migration low-risk. The biggest technical debt item is the in-memory background task system, which should be fixed regardless of the frontend split.
---

## 9. UI/UX Analysis & Improvement Plan

### 9.1 Current UI Audit

#### 9.1.1 Visual Design

| Aspect | Current State | Assessment |
|--------|--------------|------------|
| Color system | Single primary `#3b82f6` (blue-500), gray scale | Functional but flat; no secondary/accent colors |
| Typography | Arial fallback, no font stack | Generic; no brand personality |
| Spacing | Tailwind spacing tokens applied inconsistently | Some pages feel cramped (chat), others loose (admin) |
| Shadows | `shadow-lg` everywhere | No elevation hierarchy; all cards feel equal weight |
| Border radius | `rounded-lg` (8px) everywhere | No distinction between interactive vs. content elements |
| Icons | 100+ inline SVGs via Jinja macro | Works but no consistent sizing/weight system |
| Dark mode | `.dark` class toggle via localStorage | Functional; some CSS variables missing |
| Empty states | "No channels found." / "Loading..." text | No illustrations, no CTAs |
| Loading states | `animate-pulse` divs in some places | Inconsistent; many async ops show nothing |

#### 9.1.2 Layout & Navigation

| Page | Layout Pattern | Issues |
|------|---------------|--------|
| **Home** (`/`) | Single column, max-w-4xl | Channel list has no search/filter; no recent activity |
| **Videos** (`/videos/[channel]`) | Full-width table + card view | Table/card toggle not obvious; no inline actions |
| **Summary** (`/summaries_v2/[id]`) | 4 collapsible accordions | All collapsed by default; no "expand all"; no tab navigation |
| **Transcript** (`/transcript/[id]`) | 2 collapsible sections | No search within transcript; no timestamp navigation |
| **Channel Chat** (`/chat-channel/[channel]`) | 2/3 chat + 1/3 video list | Video list static; no click-to-chat from list |
| **Video Chat** (`/chat-video/[id]`) | Single column chat | No message history; no conversation threads |
| **Status** (`/status`) | Single table | No task detail view; no filtering; "Coming Soon" placeholder |
| **Admin** (`/admin-settings`) | Table + cards responsive | Form POSTs (not SPA-friendly); no bulk actions |

#### 9.1.3 Interaction Patterns

| Pattern | Current | Issues |
|---------|---------|--------|
| **Task initiation** | Button click → API call → toast | No inline progress; user must navigate to /status |
| **Channel rename** | Click icon → inline edit → blur/Enter | Works but no cancel option; visual feedback minimal |
| **Channel delete** | Click icon → `confirm()` dialog → API call | Standard but destructive action has no undo |
| **Summarize** | Check boxes → button → task ID shown | No progress feedback on the videos page itself |
| **Chat** | Type → Send → bubble appears | No message history, no thread, no model selector in flow |
| **Copy transcript** | Click icon → toast | Works but no visual change on the icon itself |
| **Navigation** | Click link → full page reload | No loading indicator during navigation |
| **Filtering** | Type → Apply button → full reload | No debounced search; no visual indication of active filter |

#### 9.1.4 Accessibility

| Aspect | Current | Issues |
|--------|---------|--------|
| **ARIA roles** | Chat has `role="log"`, `aria-live="polite"` | Good where present; missing on many interactive elements |
| **Keyboard nav** | Enter on chat input; basic tab order | No global keyboard shortcuts; no focus management on modals |
| **Screen reader** | Some labels present | Collapsible sections lack `aria-expanded`; no live regions for task status |
| **Color contrast** | Mostly passes | Some gray-on-gray combinations borderline |
| **Focus visible** | `focus:ring-2` on inputs | Missing on icon buttons and interactive divs |

### 9.2 Improvement Priorities

#### P0 — Must Fix (Breaks UX)

| # | Issue | Fix |
|---|-------|-----|
| 1 | **No loading state during page navigation** | Next.js `pending` UI with `startTransition` or Suspense |
| 2 | **Task progress invisible after initiation** | Inline progress bar on the initiating page; push notification to status page |
| 3 | **All summary sections start collapsed** | Default to first section open; add "Expand all" toggle |
| 4 | **No empty state illustrations** | Add contextual empty states with CTAs for every list view |
| 5 | **Chat has no message persistence** | Store conversation history in React state; add clear/reset button |

#### P1 — Should Improve (Major UX wins)

| # | Issue | Fix |
|---|-------|-----|
| 6 | **Summary view: 4 accordions → tabs** | Replace accordions with tab navigation (Concise / Topics / Takeaways / Notes) |
| 7 | **Transcript: no search** | Add a search bar that highlights matching text with timestamp navigation |
| 8 | **Status page: bare table** | Add task detail modal, filter by type/status, sortable columns |
| 9 | **Chat: no conversation thread** | Support multiple questions per session; show model + data source used |
| 10 | **Home: no channel search** | Add a search input that filters the channel list in real-time |
| 11 | **Videos page: no inline actions** | Add hover actions: chat, view summary, view transcript per row |
| 12 | **Admin: form POSTs → modal forms** | Convert to modal-based forms with inline validation |

#### P2 — Nice to Have (Differentiation)

| # | Feature | Description |
|---|---------|-------------|
| 13 | **Sidebar navigation** | Replace top nav with collapsible sidebar for desktop; keep mobile hamburger |
| 14 | **Global search** | Search across channels, videos, summaries, and transcripts |
| 15 | **Export summaries** | Download as PDF, Markdown, or copy to clipboard |
| 16 | **Bookmarks** | Save videos/summaries to a personal collection |
| 17 | **Recent activity feed** | Show recently downloaded, summarized, or chatted content on home |
| 18 | **Keyboard shortcuts** | `g h` → home, `g v` → videos, `/` → search, `?` → help |
| 19 | **Onboarding tour** | First-time user guide highlighting key features |
| 20 | **Share summaries** | Generate a public link to a summary view |
| 21 | **Timestamp links in chat** | Click a video reference in chat → navigate to that video's chat |
| 22 | **Model comparison** | View summaries from different models side-by-side |

### 9.3 Proposed UI Redesign

#### 9.3.1 Layout System

```
+---------------------------------------------------------+
|  [Logo]  [Search...]                    [bell] [moon]   |  <- Top bar (persistent)
+----------+----------------------------------------------+
|          |                                              |
|  Channel |  Page Content                                |
|  Videos  |  +----------------------------------------+  |
|  Chat    |  |  Page Header + Breadcrumb              |  |
|  Status  |  +----------------------------------------+  |
|  Admin   |  |  Page Body (varies by route)             |  |
|  [+] Add |  |                                        |  |
|  Channel |  |                                        |  |
|          |  |                                        |  |
|          |  +----------------------------------------+  |
|          |                                              |
+----------+----------------------------------------------+
```

- **Sidebar**: Collapsible, icon+label on expand, icon-only when collapsed
- **Top bar**: Global search, notifications, dark mode, user menu
- **Breadcrumb**: Auto-generated from sidebar selection
- **Mobile**: Sidebar becomes a slide-out drawer

#### 9.3.2 Page Redesigns

**Home Page (`/`)**
```
+-------------------------------------------------------+
|  Add a Channel                                      |
|  +-----------------------------------------------+  |
|  | https://youtube.com/...         [Download]    |  |
|  +-----------------------------------------------+  |
|                                                       |
|  Recent Activity                                      |
|  +-----------------------------------------------+  |
|  | [download] 2h ago - "Tech Daily" - 12 videos  |  |
|  | [summary]  5h ago - "AI Explained" - 3 sums   |  |
|  | [chat]     1d ago - "Data Science" - 3 msgs   |  |
|  +-----------------------------------------------+  |
|                                                       |
|  Your Channels (searchable)                           |
|  +-----------------------------------------------+  |
|  | [search icon] Search channels...              |  |
|  |                                               |  |
|  | [channel] Channel A          [Rename] [Chat]  |  |
|  | [channel] Channel B          [Rename] [Chat]  |  |
|  | [channel] Channel C          [Rename] [Chat]  |  |
|  |                                               |  |
|  +-----------------------------------------------+  |
+-------------------------------------------------------+
```

**Summary Page (`/summaries/[id]`)**
```
+-------------------------------------------------------+
|  <- Back to Videos    [copy] [export] [share]        |
|                                                       |
|  AI Explained - "How LLMs Work"                       |
|  Model: Qwen 3.6 35B  *  Generated: 2h ago           |
|                                                       |
|  +----------+----------+----------+----------+       |
|  | Summary | Topics  | Takeaways| Notes    |       |
|  +----------+----------+----------+----------+       |
|                                                       |
|  +-----------------------------------------------+  |
|  | [Tab content - rendered markdown]               |  |
|  |                                               |  |
|  | The key insight is that...                      |  |
|  |                                               |  |
|  | * Point one                                     |  |
|  | * Point two                                     |  |
|  +-----------------------------------------------+  |
|                                                       |
|  ------------------------------------------           |
|  Transcript (quick view)                            |
|  +-----------------------------------------------+  |
|  | [0:00] Introduction to the topic...           |  |
|  | [1:23] Main concept explanation...            |  |
|  | [3:45] Example use case...                    |  |
|  +-----------------------------------------------+  |
|  [View Full Transcript ->]                          |
+-------------------------------------------------------+
```

**Chat Page (`/chat/[channel-or-video]`)**
```
+-------------------------------------------------------+
|  Chat with "Tech Daily"           [Notes] [Summary]  |
|  +------------------------+--------------------------+|
|  |                        |  [channel] Video List   ||
|  |  [messages area]       |  +-------------------+  ||
|  |                        |  | [thumb] Title     |  ||
|  |  +------------------+- |  +-------------------+  ||
|  |  | You: How does    | |  | [thumb] Title     |  ||
|  |  | chunking work?   | |  +-------------------+  ||
|  |  +------------------+- |  | [thumb] Title     |  ||
|  |                        |  +-------------------+  ||
|  |  +------------------+- |  Click to chat with     ||
|  |  | Assistant: Chunking|  individual videos.      ||
|  |  | splits text into...|                          ||
|  |  +------------------+- |  24 videos in           ||
|  |                        |  this channel           ||
|  |                        |                          ||
|  |  +------------------+- |                          ||
|  |  | Type a message...| |                          ||
|  |  |             [Send]| |                          ||
|  |  +------------------+- |                          ||
|  +------------------------+--------------------------+|
+-------------------------------------------------------+
```

**Status Page (`/status`)**
```
+-------------------------------------------------------+
|  Task Dashboard                                       |
|                                                       |
|  +----------+----------+----------+                   |
|  | 3 Active | 12 Done  | 2 Failed |                   |
|  |  [green] |  [gray]  |  [red]   |                   |
|  +----------+----------+----------+                   |
|                                                       |
|  Filter: [All v]  Type: [All v]  Search: [search]   |
|                                                       |
|  +-----------------------------------------------+  |
|  | Task ID        | Type     | Progress         |  |
|  +-----------------------------------------------+  |
|  | dl_a1b2c3      | Download | ####.. 67%       |  |
|  | [details ->]   |          | 8/12 videos      |  |
|  +-----------------------------------------------+  |
|  | summ_d4e5f6    | Summary  | ##.... 40%       |  |
|  | [details ->]   |          | 2/5 videos       |  |
|  +-----------------------------------------------+  |
|  | dl_g7h8i9      | Download | ###### 100%      |  |
|  |                |          | 10/10 videos     |  |
|  +-----------------------------------------------+  |
|                                                       |
|  [View All History ->]                                |
+-------------------------------------------------------+
```

#### 9.3.3 Component Library

```
src/components/
├── ui/                          # Base primitives
│   ├── Button/                  # primary, secondary, danger, ghost, icon
│   ├── Input/                   # text, search, select, textarea
│   ├── Card/                    # with header, body, footer variants
│   ├── Badge/                   # status colors (success, info, warning, error)
│   ├── Avatar/                  # user, channel, video thumbnails
│   ├── Skeleton/                # loading placeholders
│   ├── Modal/                   # dialog, confirm, form modal
│   ├── Toast/                   # auto-dismiss, manual dismiss
│   ├── Tabs/                    # tab list + tab panels
│   ├── Accordion/               # collapsible sections (keep for transcripts)
│   ├── Progress/                # linear progress bar
│   ├── EmptyState/              # illustration + text + CTA
│   └── Search/                  # debounced search input
│
├── layout/                      # Page chrome
│   ├── Sidebar/                 # collapsible nav
│   ├── TopBar/                  # search, notifications, user
│   ├── Breadcrumb/              # auto-generated nav path
│   └── PageHeader/              # title, actions, subtitle
│
├── channels/                    # Channel domain
│   ├── ChannelList/             # searchable, filterable list
│   ├── ChannelCard/             # channel with actions
│   ├── ChannelForm/             # add/rename channel
│   └── ChannelActions/          # rename, delete, refresh dropdown
│
├── videos/                      # Video domain
│   ├── VideoTable/              # desktop table view
│   ├── VideoCard/               # mobile card view
│   ├── VideoRow/                # single row with hover actions
│   ├── VideoGrid/               # thumbnail grid view
│   └── VideoActions/            # chat, summarize, view inline
│
├── summaries/                   # Summary domain
│   ├── SummaryView/             # main summary display
│   ├── SummaryTabs/             # concise/topics/takeaways/notes
│   ├── SummaryExport/           # copy, download, share
│   └── ModelBadge/              # model name with color
│
├── chat/                        # Chat domain
│   ├── ChatWindow/              # message list + input
│   ├── MessageBubble/           # user/assistant/error
│   ├── ChatControls/            # data source, model selector
│   └── ChatSidebar/             # video list sidebar
│
├── tasks/                       # Task domain
│   ├── TaskList/                # filterable task table
│   ├── TaskCard/                # single task with progress
│   ├── TaskModal/               # detailed task view
│   └── ActiveTaskBadge/         # inline task indicator
│
└── admin/                       # Admin domain
    ├── UserTable/               # users with inline editing
    ├── UserModal/               # add/edit user
    ├── RoleBadge/               # color-coded role
    └── AdminStats/              # dashboard stats
```

### 9.4 Animation & Motion Guidelines

| Interaction | Animation | Duration | Easing |
|-------------|-----------|----------|--------|
| Page transition | Fade in | 200ms | ease-out |
| Sidebar collapse | Slide + fade | 300ms | ease-in-out |
| Toast appear/disappear | Slide up/fade | 300ms | ease-out |
| Modal open/close | Scale + fade | 200ms | ease-out |
| Task progress bar | Width transition | 500ms | ease-out |
| Skeleton loading | Shimmer sweep | 1500ms | linear (loop) |
| Button click | Scale down + up | 100ms | ease-out |
| Accordion open/close | Height transition | 200ms | ease-in-out |
| Tab switch | Content fade | 150ms | ease-out |
| Notification badge | Pulse | 500ms | ease-in-out (once) |

### 9.5 Design Tokens (Proposed)

```css
/* Color palette */
--color-primary: #3b82f6;         /* Keep existing */
--color-primary-light: #60a5fa;   /* Hover states */
--color-primary-dark: #2563eb;    /* Pressed states */
--color-accent: #8b5cf6;          /* New: purple for chat/AI */
--color-success: #22c55e;
--color-warning: #f59e0b;
--color-error: #ef4444;
--color-info: #06b6d4;

/* Typography */
--font-sans: 'Inter', system-ui, -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;

/* Spacing scale */
--space-1: 0.25rem;
--space-2: 0.5rem;
--space-3: 0.75rem;
--space-4: 1rem;
--space-6: 1.5rem;
--space-8: 2rem;
--space-12: 3rem;
--space-16: 4rem;

/* Border radius */
--radius-sm: 0.25rem;
--radius-md: 0.375rem;
--radius-lg: 0.5rem;
--radius-xl: 0.75rem;
--radius-full: 9999px;

/* Shadows */
--shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
--shadow-md: 0 4px 6px -1px rgba(0,0,0,0.1);
--shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.1);
--shadow-xl: 0 20px 25px -5px rgba(0,0,0,0.1);
```

### 9.6 Migration Approach for UI Improvements

The UI improvements should be integrated into the Next.js migration phases:

| Phase | UI Work |
|-------|---------|
| **Phase 2** (Scaffolding) | Set up design tokens, base component library (`ui/`), layout system (sidebar + topbar) |
| **Phase 3** (Page migration) | Rebuild each page with improved patterns; P0 fixes in order of migration |
| **Phase 4** (Enhancement) | P1 improvements (tabs, search, modals, export); P2 features (bookmarks, global search) |

**Recommended order for P0 fixes (integrated into page migration):**
1. Home page → add search, recent activity, loading states
2. Videos page → add inline actions, loading states, toast notifications
3. Summary page → tabs instead of accordions, expand all, copy/export buttons
4. Transcript page → add search, timestamp navigation
5. Chat pages → message history, model selector, conversation thread
6. Status page → real-time updates, task detail modal, filtering
7. Admin page → modal forms, inline validation

### 9.7 Accessibility Checklist

| Criterion | Current | Target |
|-----------|---------|--------|
| WCAG 2.1 AA | Partial | Full compliance |
| Keyboard navigation | Basic | Full tab order, visible focus, shortcuts |
| Screen reader | Some ARIA | Complete ARIA, live regions, landmarks |
| Color contrast | Mostly passes | All combinations >= 4.5:1 |
| Focus management | Inputs only | Modals, dialogs, dynamic content |
| Reduced motion | None | Respect `prefers-reduced-motion` |
| Form labels | Some | All inputs labeled, error announcements |
| Skip navigation | Present | Enhanced with dynamic skip links |
