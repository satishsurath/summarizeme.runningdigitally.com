# SummarizeMe UI/UX Improvement — Implementation Spec

**Date:** 2026-08-16
**Branch:** feature/ui-ux-improvements
**Status:** Draft

---

## Overview

This spec converts the UI/UX analysis into an actionable implementation plan. The goal is to transform the current functional-but-frustrating interface into a polished, accessible, mobile-friendly application.

### Goals
1. Replace alert() with toast notifications
2. Add loading states to all async actions
3. Replace status page with notification dropdown
4. Fix mobile responsiveness across all pages
5. Create a unified icon system
6. Improve navigation with proper structure
7. Add accessibility improvements (ARIA, focus, skip nav)
8. Define a design system (colors, spacing, typography)
9. Add video thumbnails to all lists
10. Improve chat UI with message bubbles

### Non-Goals
- Complete rewrite of backend
- New framework (React/Vue) — stay with Flask + Jinja2
- PWA/service worker (deferred to Phase 4)
- Real-time WebSockets (deferred to Phase 4)

---

## Implementation Phases

### Phase 1: Foundation (P0 — 1-2 days)

#### 1.1 Design System Tokens

**Files to create:**
- `static/css/tailwind.config.js` — Custom Tailwind config
- `static/css/components.css` — Reusable component classes
- `static/css/icons.css` — Icon sizing classes

**Tailwind config additions:**
```js
// tailwind.config.js
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe',
          300: '#93c5fd', 400: '#60a5fa', 500: '#3b82f6',
          600: '#2563eb', 700: '#1d4ed8', 800: '#1e40af', 900: '#1e3a8a',
        },
        success: '#22c55e',
        warning: '#f59e0b',
        error: '#ef4444',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      spacing: {
        '44': '11px', // minimum touch target
        '56': '14px',
      },
    },
  },
  plugins: [],
}
```

**Component classes (components.css):**
```css
/* Buttons */
.btn-primary {
  @apply inline-flex items-center justify-center px-4 py-2 bg-primary-500 text-white font-medium rounded-lg hover:bg-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors;
}

.btn-secondary {
  @apply inline-flex items-center justify-center px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-medium rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors;
}

.btn-danger {
  @apply inline-flex items-center justify-center px-4 py-2 bg-error text-white font-medium rounded-lg hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-error focus:ring-offset-2 transition-colors;
}

.btn-icon {
  @apply inline-flex items-center justify-center p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors min-w-[44px] min-h-[44px];
}

/* Cards */
.card {
  @apply bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700;
}

.card-header {
  @apply px-6 py-4 border-b border-gray-200 dark:border-gray-700;
}

.card-body {
  @apply px-6 py-4;
}

/* Inputs */
.input {
  @apply w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors;
}

.input-error {
  @apply border-error focus:ring-error;
}

/* Badges */
.badge {
  @apply inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium;
}

.badge-success {
  @apply bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200;
}

.badge-warning {
  @apply bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200;
}

.badge-error {
  @apply bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200;
}

.badge-info {
  @apply bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200;
}

/* Status indicators */
.status-dot {
  @apply w-2 h-2 rounded-full;
}

.status-dot-success { @apply bg-success; }
.status-dot-warning { @apply bg-warning; }
.status-dot-error { @apply bg-error; }
.status-dot-info { @apply bg-primary-500; }
```

**Icon sizing classes (icons.css):**
```css
.icon-sm { @apply w-4 h-4; }
.icon-md { @apply w-5 h-5; }
.icon-lg { @apply w-6 h-6; }
.icon-xl { @apply w-8 h-8; }
```

**Acceptance Criteria:**
- [ ] Tailwind config exists with custom colors and content paths
- [ ] Component classes defined for buttons, cards, inputs, badges
- [ ] Icon sizing classes defined (sm/md/lg/xl)
- [ ] All component classes support dark mode
- [ ] Touch targets are minimum 44px

#### 1.2 Toast Notification System

**Files to create:**
- `static/js/toast.js` — Toast notification manager

**Implementation:**
```js
// static/js/toast.js
class ToastManager {
  constructor() {
    this.container = null;
    this.init();
  }

  init() {
    this.container = document.createElement('div');
    this.container.className = 'fixed top-4 right-4 z-50 space-y-2 max-w-sm';
    document.body.appendChild(this.container);
  }

  show(message, type = 'info', duration = 5000) {
    const id = `toast-${Date.now()}`;
    const el = document.createElement('div');
    el.id = id;
    el.className = `flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg transform transition-all duration-300 translate-x-full ${this.colorMap(type)}`;
    el.innerHTML = `
      ${this.iconMap(type)}
      <span class="flex-1 text-sm font-medium">${message}</span>
      <button onclick="toast.dismiss('${id}')" class="p-1 rounded hover:opacity-70">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    `;
    this.container.appendChild(el);
    requestAnimationFrame(() => el.classList.remove('translate-x-full'));
    if (duration > 0) {
      setTimeout(() => this.dismiss(id), duration);
    }
    return id;
  }

  dismiss(id) {
    const el = document.getElementById(id);
    if (el) {
      el.classList.add('translate-x-full', 'opacity-0');
      setTimeout(() => el.remove(), 300);
    }
  }

  success(msg, duration) { return this.show(msg, 'success', duration); }
  error(msg, duration) { return this.show(msg, 'error', duration); }
  warning(msg, duration) { return this.show(msg, 'warning', duration); }
  info(msg, duration) { return this.show(msg, 'info', duration); }

  colorMap(type) {
    const map = {
      success: 'bg-green-50 dark:bg-green-900 text-green-800 dark:text-green-200 border border-green-200 dark:border-green-700',
      error: 'bg-red-50 dark:bg-red-900 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-700',
      warning: 'bg-yellow-50 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 border border-yellow-200 dark:border-yellow-700',
      info: 'bg-blue-50 dark:bg-blue-900 text-blue-800 dark:text-blue-200 border border-blue-200 dark:border-blue-700',
    };
    return map[type] || map.info;
  }

  iconMap(type) {
    const map = {
      success: '<svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>',
      error: '<svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>',
      warning: '<svg class="w-5 h-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>',
      info: '<svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
    };
    return map[type] || map.info;
  }
}

const toast = new ToastManager();
```

**Integration:**
- Add `<script src="{{ url_for('static', filename='js/toast.js') }}"></script>` to `layout.html`
- Replace all `alert()` calls in `index.js` with `toast.error()` or `toast.success()`
- Replace all inline notification code in `transcript_v2.html` with `toast.success()`

**Acceptance Criteria:**
- [ ] Toast manager created and exported as global `toast`
- [ ] Toasts appear top-right, slide in from right
- [ ] Toasts auto-dismiss after 5 seconds (configurable)
- [ ] Toasts support success/error/warning/info types
- [ ] All `alert()` calls replaced with toast calls
- [ ] Toast dismiss button works
- [ ] Toasts stack properly (no overlap)
- [ ] Toasts work in dark mode

#### 1.3 Loading State System

**Files to create:**
- `static/js/loading.js` — Loading state manager

**Implementation:**
```js
// static/js/loading.js
class LoadingManager {
  constructor() {
    this.activeLoads = new Map();
  }

  start(id, element) {
    if (!element) return;
    this.activeLoads.set(id, element);
    element.disabled = true;
    element.dataset.originalText = element.textContent;
    element.innerHTML = `<svg class="animate-spin h-4 w-4 inline mr-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg> Loading...`;
    element.classList.add('opacity-75', 'cursor-not-allowed');
  }

  end(id) {
    const el = this.activeLoads.get(id);
    if (!el) return;
    el.disabled = false;
    el.textContent = el.dataset.originalText || el.textContent;
    el.classList.remove('opacity-75', 'cursor-not-allowed');
    this.activeLoads.delete(id);
  }
}

const loading = new LoadingManager();
```

**Integration:**
- Add `<script src="{{ url_for('static', filename='js/loading.js') }}"></script>` to `layout.html`
- Use in `index.js`:
  ```js
  loading.start('download', startDownloadBtn);
  try { ... } finally { loading.end('download'); }
  ```
- Use in `videos.js` for summarize button
- Use in chat pages for query button

**Acceptance Criteria:**
- [ ] Loading manager created and exported as global `loading`
- [ ] Buttons show spinner + "Loading..." during async operations
- [ ] Buttons are disabled during loading
- [ ] Buttons restore original text after completion
- [ ] Loading states work in dark mode
- [ ] Multiple concurrent loading states work correctly

---

### Phase 2: Navigation & Status (P0 — 2-3 days)

#### 2.1 Navigation Redesign

**Files to modify:**
- `templates/layout.html` — Nav structure

**Current nav:**
```html
[Summarizeme]  [Home] [Check Status] [Admin] [🌙]
```

**New nav:**
```html
[SummarizeMe]  [Channels] [Videos] [Chat] [Admin] [🔔] [🌙]
```

**Changes:**
1. Rename "Summarizeme" → "SummarizeMe"
2. Rename "Home" → "Channels" (link to `/`)
3. Add "Videos" link (link to `/videos`)
4. Add "Chat" link (link to `/chat` — or remove, chat is accessed via channels)
5. Rename "Check Status" → "Notifications" (bell icon dropdown)
6. Add dark mode toggle (keep existing)
7. Add active state indicator

**Implementation:**
```html
<!-- Nav structure -->
<nav class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex items-center justify-between h-16">
      <!-- Logo -->
      <div class="flex-shrink-0">
        <a href="/" class="text-xl font-bold text-primary-500">SummarizeMe</a>
      </div>

      <!-- Desktop Nav -->
      <div class="hidden md:flex items-center space-x-4">
        <a href="/" class="nav-link {% if request.endpoint == 'index' %}active{% endif %}">Channels</a>
        <a href="/videos" class="nav-link {% if request.endpoint == 'videos' %}active{% endif %}">Videos</a>
        <div class="relative">
          <button id="notificationBtn" class="nav-link relative" aria-label="Notifications">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
            </svg>
            {% if active_tasks|length > 0 %}
            <span class="absolute -top-1 -right-1 w-4 h-4 bg-primary-500 rounded-full text-xs text-white flex items-center justify-center">{{ active_tasks|length }}</span>
            {% endif %}
          </button>
          <!-- Notification Dropdown -->
          <div id="notificationDropdown" class="hidden absolute right-0 mt-2 w-80 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 z-50">
            <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
              <h3 class="text-sm font-semibold text-gray-900 dark:text-white">Active Tasks</h3>
            </div>
            <div class="max-h-64 overflow-y-auto">
              {% if active_tasks %}
                {% for task in active_tasks %}
                <div class="px-4 py-3 border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer" onclick="window.location.href='/status'">
                  <div class="flex items-center gap-2">
                    {% if task.status == 'completed' %}
                    <span class="status-dot status-dot-success"></span>
                    {% elif task.status == 'failed' %}
                    <span class="status-dot status-dot-error"></span>
                    {% else %}
                    <span class="status-dot status-dot-info"></span>
                    {% endif %}
                    <span class="text-sm text-gray-700 dark:text-gray-300">{{ task.name }}</span>
                  </div>
                </div>
                {% endfor %}
              {% else %}
                <div class="px-4 py-6 text-center text-gray-500 dark:text-gray-400">
                  No active tasks
                </div>
              {% endif %}
            </div>
            <div class="px-4 py-2 border-t border-gray-200 dark:border-gray-700">
              <a href="/status" class="text-sm text-primary-500 hover:text-primary-600">View All Tasks →</a>
            </div>
          </div>
        </div>
      </div>

      <!-- Right side -->
      <div class="flex items-center space-x-2">
        <!-- Dark mode toggle -->
        <button id="darkModeToggle" class="btn-icon" aria-label="Toggle dark mode">
          <!-- sun/moon icons -->
        </button>
        <!-- Mobile menu button -->
        <button id="mobileMenuBtn" class="btn-icon md:hidden" aria-label="Open menu">
          <!-- hamburger icon -->
        </button>
      </div>
    </div>
  </div>

  <!-- Mobile menu -->
  <div id="mobileMenu" class="hidden md:hidden border-t border-gray-200 dark:border-gray-700">
    <div class="px-4 py-2 space-y-1">
      <a href="/" class="block px-3 py-2 rounded-lg {% if request.endpoint == 'index' %}bg-primary-50 dark:bg-primary-900{% endif %}">Channels</a>
      <a href="/videos" class="block px-3 py-2 rounded-lg {% if request.endpoint == 'videos' %}bg-primary-50 dark:bg-primary-900{% endif %}">Videos</a>
      <a href="/status" class="block px-3 py-2 rounded-lg {% if request.endpoint == 'status' %}bg-primary-50 dark:bg-primary-900{% endif %}">Status</a>
      <a href="/admin" class="block px-3 py-2 rounded-lg {% if request.endpoint == 'admin' %}bg-primary-50 dark:bg-primary-900{% endif %}">Admin</a>
    </div>
  </div>
</nav>
```

**Nav CSS (add to components.css):**
```css
.nav-link {
  @apply inline-flex items-center px-3 py-2 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-colors;
}

.nav-link.active {
  @apply text-primary-500 bg-primary-50 dark:bg-primary-900/50;
}
```

**Backend changes (main.py):**
- Add `active_tasks` context variable to all templates
- Create `/api/active-tasks` endpoint for polling

**Acceptance Criteria:**
- [ ] Nav has Channels, Videos, Chat, Admin links
- [ ] Logo is "SummarizeMe" (correct capitalization)
- [ ] Status link replaced with bell icon dropdown
- [ ] Bell shows badge count for active tasks
- [ ] Dropdown shows active tasks with status dots
- [ ] Dropdown has "View All Tasks" link
- [ ] Mobile menu has all nav links
- [ ] Active nav link highlighted
- [ ] Bell dropdown closes on outside click
- [ ] All nav links have aria-labels

#### 2.2 Notification Dropdown JavaScript

**Files to create:**
- `static/js/notifications.js` — Notification dropdown manager

**Implementation:**
```js
// static/js/notifications.js
document.addEventListener('DOMContentLoaded', () => {
  const bellBtn = document.getElementById('notificationBtn');
  const dropdown = document.getElementById('notificationDropdown');
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');
  const mobileMenu = document.getElementById('mobileMenu');

  if (!bellBtn || !dropdown) return;

  // Toggle dropdown on bell click
  bellBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('hidden');
  });

  // Close dropdown on outside click
  document.addEventListener('click', (e) => {
    if (!dropdown.contains(e.target) && e.target !== bellBtn) {
      dropdown.classList.add('hidden');
    }
  });

  // Close dropdown on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      dropdown.classList.add('hidden');
      mobileMenu.classList.add('hidden');
    }
  });

  // Mobile menu toggle
  if (mobileMenuBtn && mobileMenu) {
    mobileMenuBtn.addEventListener('click', () => {
      mobileMenu.classList.toggle('hidden');
    });
  }
});
```

**Backend changes (main.py):**
- Add `/api/active-tasks` endpoint
- Return list of active tasks with status
- Add polling interval (5 seconds)

```python
@app.route('/api/active-tasks')
def api_active_tasks():
    """Return list of active tasks for notification dropdown."""
    active = {}
    for task_id, task in background_tasks.items():
        if task['status'] in ('pending', 'running'):
            active[task_id] = {
                'name': task.get('name', task_id),
                'status': task['status'],
            }
    return jsonify(list(active.values()))
```

**Acceptance Criteria:**
- [ ] Bell dropdown toggles on click
- [ ] Dropdown closes on outside click
- [ ] Dropdown closes on Escape key
- [ ] Active tasks polled every 5 seconds
- [ ] Badge count updates in real-time
- [ ] Status dots show correct color (green/yellow/red)
- [ ] Click task row navigates to /status

---

### Phase 3: Icon System (P1 — 2-3 days)

#### 3.1 Icon Library Selection & Setup

**Decision:** Use [Lucide Icons](https://lucide.dev/) (lightweight, consistent, MIT license)

**Files to create:**
- `static/js/icons.js` — Icon rendering helper

**Implementation:**
```js
// static/js/icons.js
const ICONS = {
  edit: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg>',
  trash: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/></svg>',
  refresh: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>',
  chat: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9a2 2 0 0 1-2 2H6l-4 4V4c0-1.1.9-2 2-2h8a2 2 0 0 1 2 2v5Z"/><path d="M18 9h2a2 2 0 0 1 2 2v11l-4-4h-6a2 2 0 0 1-2-2v-1"/></svg>',
  youtube: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.55 49.55 0 0 1-16.2 0A2 2 0 0 1 2.5 17"/><path d="m10 15 5-3-5-3z"/></svg>',
  copy: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>',
  chevronDown: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>',
  menu: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/></svg>',
  sun: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>',
  moon: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>',
  check: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
  x: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>',
  bell: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>',
  video: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2" ry="2"/></svg>',
  channel: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m10 2 4 12"/></svg>',
  admin: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>',
};

function renderIcon(name, sizeClass = 'icon-md') {
  const svg = ICONS[name];
  if (!svg) return '';
  return `<span class="${sizeClass} icon">${svg}</span>`;
}
```

**Integration:**
- Replace all inline SVG icons in templates with `{{ render_icon('name') }}` macro
- Replace inline SVG strings in JS with `renderIcon('name')`
- Add `<script src="{{ url_for('static', filename='js/icons.js') }}"></script>` to `layout.html`

**Template macro:**
```html
{% macro render_icon(name, size='md') %}
  {% set size_class = {
    'sm': 'icon-sm',
    'md': 'icon-md',
    'lg': 'icon-lg',
    'xl': 'icon-xl'
  }[size] %}
  {{ ICONS[name] | safe }}
{% endmacro %}
```

**Acceptance Criteria:**
- [ ] All icons use Lucide Icons
- [ ] Icon library loaded once in layout.html
- [ ] All icon buttons have aria-labels
- [ ] Icons support dark mode (currentColor)
- [ ] No duplicate icon definitions
- [ ] Icon sizing classes work (sm/md/lg/xl)
- [ ] All 10 icons from analysis replaced

#### 3.2 Replace All Inline Icons

**Files to modify:**
- `templates/index.html` — Replace edit/delete/refresh/chat/youtube icons
- `templates/layout.html` — Replace dark mode toggle, menu icons
- `templates/summary_v2.html` — Replace copy/chevron icons
- `templates/transcript_v2.html` — Replace copy/chevron icons
- `static/js/index.js` — Replace edit/delete/refresh/chat/youtube icons

**Replacement mapping:**
| Old | New |
|-----|-----|
| `index.html` edit SVG | `render_icon('edit')` |
| `index.html` trash SVG | `render_icon('trash')` |
| `index.html` refresh SVG | `render_icon('refresh')` |
| `index.html` chat SVG | `render_icon('chat')` |
| `index.html` YouTube SVG | `render_icon('youtube')` |
| `layout.html` dark mode SVG | `render_icon('sun')` / `render_icon('moon')` |
| `layout.html` menu SVG | `render_icon('menu')` |
| `summary_v2.html` copy SVG | `render_icon('copy')` |
| `summary_v2.html` chevron SVG | `render_icon('chevronDown')` |
| `transcript_v2.html` copy SVG | `render_icon('copy')` |
| `transcript_v2.html` chevron SVG | `render_icon('chevronDown')` |
| `index.js` edit SVG | `renderIcon('edit')` |
| `index.js` trash SVG | `renderIcon('trash')` |
| `index.js` refresh SVG | `renderIcon('refresh')` |
| `index.js` chat SVG | `renderIcon('chat')` |
| `index.js` YouTube SVG | `renderIcon('youtube')` |

**Acceptance Criteria:**
- [ ] All inline SVGs replaced with icon library calls
- [ ] No duplicate icon definitions remain
- [ ] All icons render correctly in light and dark mode
- [ ] All icon buttons have aria-labels
- [ ] No broken icons in any template

---

### Phase 4: Accessibility (P1 — 1-2 days)

#### 4.1 ARIA & Keyboard Accessibility

**Files to modify:**
- `templates/layout.html` — Skip nav, ARIA labels
- `templates/index.html` — ARIA labels on icon buttons
- `templates/videos.html` — ARIA labels on table controls
- `templates/channel_chat.html` — ARIA labels on chat controls
- `templates/admin_settings.html` — ARIA labels on admin controls

**Changes:**
```html
<!-- Skip navigation -->
<a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 bg-primary-500 text-white px-4 py-2 rounded-lg z-50">
  Skip to main content
</a>

<!-- Main content wrapper -->
<main id="main-content" role="main">
  {% block content %}{% endblock %}
</main>

<!-- Icon buttons with aria-labels -->
<button class="btn-icon" aria-label="Edit channel" data-channel="...">
  {{ render_icon('edit') }}
</button>

<button class="btn-icon" aria-label="Delete channel" data-channel="...">
  {{ render_icon('trash') }}
</button>

<button class="btn-icon" aria-label="Refresh channel" data-channel="...">
  {{ render_icon('refresh') }}
</button>

<button class="btn-icon" aria-label="Chat with channel" data-channel="...">
  {{ render_icon('chat') }}
</button>

<!-- Live region for dynamic content -->
<div id="liveRegion" aria-live="polite" aria-atomic="true" class="sr-only"></div>

<!-- Error alerts -->
<div role="alert" aria-live="assertive" class="...">
  Error message
</div>
```

**CSS for sr-only:**
```css
.sr-only {
  @apply absolute w-[1px] h-[1px] p-0 m-[-1px] overflow-hidden clip-rect(0,0,0,0) whitespace-nowrap border-0;
}
```

**JavaScript for live region:**
```js
// static/js/accessibility.js
function announce(message) {
  const region = document.getElementById('liveRegion');
  if (region) {
    region.textContent = '';
    setTimeout(() => { region.textContent = message; }, 100);
  }
}
```

**Acceptance Criteria:**
- [ ] Skip navigation link present and works
- [ ] All icon buttons have aria-labels
- [ ] Live region present for dynamic content
- [ ] Error messages use role="alert"
- [ ] All form inputs have labels or aria-labels
- [ ] Focus indicators visible on all interactive elements
- [ ] Keyboard navigation works on all pages

---

### Phase 5: Mobile Responsiveness (P1 — 2-3 days)

#### 5.1 Responsive Layout Fixes

**Files to modify:**
- `templates/videos.html` — Table → card view on mobile
- `templates/channel_chat.html` — Grid → stack on mobile
- `templates/admin_settings.html` — Form → stacked on mobile
- `templates/index.html` — Legend → collapsible on mobile

**Videos page — Card view on mobile:**
```html
<!-- Desktop: table view -->
<div class="hidden md:block">
  <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
    ...
  </table>
</div>

<!-- Mobile: card view -->
<div class="md:hidden space-y-4">
  {% for video in videos %}
  <div class="card">
    <div class="card-body">
      <div class="flex items-start gap-3">
        <input type="checkbox" class="mt-1" data-video="{{ video.video_id }}">
        <div class="flex-1 min-w-0">
          <h3 class="text-sm font-medium text-gray-900 dark:text-white truncate">{{ video.title }}</h3>
          <p class="text-xs text-gray-500 dark:text-gray-400">{{ video.video_id }}</p>
          <div class="flex gap-2 mt-2">
            {% if video.summary %}
            <span class="badge badge-success">Summarized</span>
            {% else %}
            <span class="badge badge-warning">No summary</span>
            {% endif %}
            {% if video.transcript %}
            <span class="badge badge-info">Transcript</span>
            {% endif %}
          </div>
        </div>
      </div>
    </div>
  </div>
  {% endfor %}
</div>
```

**Chat page — Stack on mobile:**
```html
<!-- Desktop: 3-column grid -->
<div class="hidden md:grid md:grid-cols-3 gap-6">
  ...
</div>

<!-- Mobile: stack -->
<div class="md:hidden space-y-4">
  ...
</div>
```

**Acceptance Criteria:**
- [ ] Videos page shows cards on mobile, table on desktop
- [ ] Chat page stacks columns on mobile
- [ ] Admin form stacks on mobile
- [ ] All touch targets ≥ 44px on mobile
- [ ] No horizontal scroll on mobile
- [ ] Tables scroll horizontally on mobile (fallback)

---

### Phase 6: Video Thumbnails (P2 — 2-3 days)

#### 6.1 YouTube Thumbnail Integration

**Files to modify:**
- `templates/index.html` — Channel list (optional)
- `templates/videos.html` — Video table/cards
- `templates/channel_chat.html` — Video sidebar
- `static/js/videos.js` — Thumbnail loading

**Implementation:**
```js
// Get YouTube thumbnail URL
function getThumbnailUrl(videoId, quality = 'medium') {
  const qualities = {
    default: 'default',
    medium: 'mqdefault',
    high: 'hqdefault',
    standard: 'sddefault',
    max: 'maxresdefault',
  };
  return `https://img.youtube.com/vi/${videoId}/${qualities[quality]}.jpg`;
}

// Lazy load thumbnails
function loadThumbnails() {
  const images = document.querySelectorAll('[data-video-id]');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        const videoId = img.dataset.videoId;
        img.src = getThumbnailUrl(videoId);
        observer.unobserve(img);
      }
    });
  }, { rootMargin: '200px' });

  images.forEach(img => observer.observe(img));
}
```

**Template usage:**
```html
<img src="{{ video.thumbnail_url or get_thumbnail_url(video.video_id) }}"
     alt="{{ video.title }}"
     loading="lazy"
     class="w-24 h-16 object-cover rounded">
```

**Acceptance Criteria:**
- [ ] Thumbnails load for all videos
- [ ] Thumbnails lazy load (IntersectionObserver)
- [ ] Thumbnails show in video table/cards
- [ ] Thumbnails show in chat sidebar
- [ ] Fallback to placeholder if thumbnail fails
- [ ] Thumbnails work in dark mode

---

### Phase 7: Chat UI Redesign (P2 — 3-4 days)

#### 7.1 Chat Message Bubbles

**Files to modify:**
- `templates/channel_chat.html` — Chat UI
- `templates/video_chat.html` — Chat UI
- `static/js/chat.js` — Chat message handling

**Implementation:**
```html
<!-- Chat container -->
<div id="chatContainer" class="flex-1 overflow-y-auto p-4 space-y-4">
  <!-- Welcome message -->
  <div class="flex items-start gap-3">
    <div class="w-8 h-8 rounded-full bg-primary-500 flex items-center justify-center flex-shrink-0">
      <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
      </svg>
    </div>
    <div class="flex-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-3">
      <p class="text-sm text-gray-700 dark:text-gray-300">Ask me anything about this channel's content!</p>
    </div>
  </div>

  <!-- User message -->
  <div class="flex items-start gap-3 justify-end">
    <div class="flex-1 bg-primary-500 text-white rounded-lg p-3 max-w-2xl">
      <p class="text-sm">What is this video about?</p>
    </div>
    <div class="w-8 h-8 rounded-full bg-gray-300 dark:bg-gray-600 flex items-center justify-center flex-shrink-0">
      <svg class="w-4 h-4 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
      </svg>
    </div>
  </div>

  <!-- Assistant message -->
  <div class="flex items-start gap-3">
    <div class="w-8 h-8 rounded-full bg-primary-500 flex items-center justify-center flex-shrink-0">
      <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
      </svg>
    </div>
    <div class="flex-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-3 max-w-2xl">
      <p class="text-sm text-gray-700 dark:text-gray-300">This video discusses...</p>
    </div>
  </div>
</div>

<!-- Chat input -->
<div class="border-t border-gray-200 dark:border-gray-700 p-4">
  <form id="chatForm" class="flex gap-2">
    <input type="text" id="chatInput" placeholder="Ask a question..."
           class="flex-1 input" autocomplete="off">
    <button type="submit" id="sendBtn" class="btn-primary">
      {{ render_icon('send', 'sm') }}
      <span>Send</span>
    </button>
  </form>
</div>
```

**Chat JavaScript:**
```js
// static/js/chat.js
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('chatForm');
  const input = document.getElementById('chatInput');
  const container = document.getElementById('chatContainer');

  if (!form || !input || !container) return;

  // Enter to send, Shift+Enter for newline
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event('submit'));
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    // Add user message
    addUserMessage(message);
    input.value = '';

    // Add loading indicator
    const loadingId = addLoadingMessage();

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          channel: document.getElementById('channelName')?.value,
          video: document.getElementById('videoId')?.value,
        }),
      });

      const data = await res.json();
      removeLoadingMessage(loadingId);

      if (data.answer) {
        addAssistantMessage(data.answer);
      } else {
        addErrorMessage(data.error || 'No answer was returned.');
      }
    } catch (err) {
      removeLoadingMessage(loadingId);
      addErrorMessage(`Error: ${err.message}`);
    }
  });

  function addUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'flex items-start gap-3 justify-end';
    div.innerHTML = `
      <div class="flex-1 bg-primary-500 text-white rounded-lg p-3 max-w-2xl">
        <p class="text-sm">${escapeHtml(text)}</p>
      </div>
      <div class="w-8 h-8 rounded-full bg-gray-300 dark:bg-gray-600 flex items-center justify-center flex-shrink-0">
        <svg class="w-4 h-4 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
        </svg>
      </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  function addAssistantMessage(text) {
    const div = document.createElement('div');
    div.className = 'flex items-start gap-3';
    div.innerHTML = `
      <div class="w-8 h-8 rounded-full bg-primary-500 flex items-center justify-center flex-shrink-0">
        <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
        </svg>
      </div>
      <div class="flex-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-3 max-w-2xl">
        <p class="text-sm text-gray-700 dark:text-gray-300">${escapeHtml(text)}</p>
      </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  function addLoadingMessage() {
    const id = `loading-${Date.now()}`;
    const div = document.createElement('div');
    div.id = id;
    div.className = 'flex items-start gap-3';
    div.innerHTML = `
      <div class="w-8 h-8 rounded-full bg-primary-500 flex items-center justify-center flex-shrink-0">
        <svg class="w-4 h-4 text-white animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
      </div>
      <div class="flex-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-3">
        <p class="text-sm text-gray-500 dark:text-gray-400">Thinking...</p>
      </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return id;
  }

  function removeLoadingMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function addErrorMessage(text) {
    const div = document.createElement('div');
    div.className = 'flex items-start gap-3';
    div.innerHTML = `
      <div class="w-8 h-8 rounded-full bg-error flex items-center justify-center flex-shrink-0">
        <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </div>
      <div class="flex-1 bg-red-50 dark:bg-red-900/50 rounded-lg p-3 max-w-2xl">
        <p class="text-sm text-red-700 dark:text-red-300">${escapeHtml(text)}</p>
      </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
});
```

**Acceptance Criteria:**
- [ ] Chat messages display as bubbles (user right, assistant left)
- [ ] Enter sends message, Shift+Enter for newline
- [ ] Loading indicator shows during generation
- [ ] Error messages show in red bubble
- [ ] Chat scrolls to bottom on new message
- [ ] Chat input is focused on page load
- [ ] Chat works in dark mode
- [ ] Chat input has placeholder text

---

## Testing Strategy

### Unit Tests (JavaScript)
- `tests/unit/test_toast.js` — Toast manager tests
- `tests/unit/test_loading.js` — Loading manager tests
- `tests/unit/test_icons.js` — Icon rendering tests
- `tests/unit/test_notifications.js` — Notification dropdown tests
- `tests/unit/test_chat.js` — Chat message tests

### Integration Tests (Browser)
- Test toast notifications appear on error
- Test loading states on async actions
- Test notification dropdown opens/closes
- Test mobile menu opens/closes
- Test chat message bubbles render correctly
- Test video thumbnails load
- Test keyboard navigation works

### Visual Regression Tests
- Test dark mode toggle works
- Test all pages render correctly in dark mode
- Test responsive layouts at different breakpoints
- Test icon rendering in light/dark mode

### Accessibility Tests
- Test skip navigation link works
- Test all icon buttons have aria-labels
- Test focus indicators visible
- Test keyboard navigation on all pages
- Test screen reader announcements

---

## File Change Summary

### New Files
| File | Purpose |
|------|---------|
| `static/css/tailwind.config.js` | Custom Tailwind config |
| `static/css/components.css` | Reusable component classes |
| `static/css/icons.css` | Icon sizing classes |
| `static/js/toast.js` | Toast notification manager |
| `static/js/loading.js` | Loading state manager |
| `static/js/icons.js` | Icon library (Lucide) |
| `static/js/notifications.js` | Notification dropdown |
| `static/js/accessibility.js` | ARIA/live region helpers |
| `static/js/chat.js` | Chat message handling |

### Modified Files
| File | Changes |
|------|---------|
| `templates/layout.html` | Nav redesign, skip nav, ARIA, icon imports |
| `templates/index.html` | Icon replacements, toast integration |
| `templates/videos.html` | Card view on mobile, icon replacements |
| `templates/channel_chat.html` | Chat UI redesign, icon replacements |
| `templates/video_chat.html` | Chat UI redesign, icon replacements |
| `templates/admin_settings.html` | Icon replacements, mobile fixes |
| `templates/summary_v2.html` | Icon replacements |
| `templates/transcript_v2.html` | Icon replacements |
| `static/js/index.js` | Toast/loading integration, icon replacements |
| `static/js/videos.js` | Toast/loading integration, icon replacements |
| `static/js/status.js` | Toast integration |
| `app/main.py` | Active tasks endpoint, nav context |

---

## Acceptance Criteria Summary

### P0 — Must Have
- [ ] Toast notifications replace all alert() calls
- [ ] Loading states on all async actions
- [ ] Notification dropdown in nav (replaces status page)
- [ ] Mobile responsive layouts
- [ ] Skip navigation link
- [ ] ARIA labels on all icon buttons

### P1 — Should Have
- [ ] Unified icon system (Lucide)
- [ ] Navigation redesign (Channels, Videos, Chat, Admin)
- [ ] Chat message bubbles
- [ ] Focus indicators on all interactive elements
- [ ] Live region for dynamic content
- [ ] Design system tokens (colors, spacing, typography)

### P2 — Nice to Have
- [ ] Video thumbnails with lazy loading
- [ ] Chat message history
- [ ] Empty state illustrations
- [ ] Export summaries as PDF/Markdown
- [ ] Keyboard shortcuts (Enter to send)

### P3 — Future
- [ ] PWA/service worker
- [ ] Real-time WebSockets
- [ ] Multi-language (i18n)
- [ ] Analytics tracking

---

## Risk Assessment

### High Risk
- **Chat UI redesign** — Changes to existing chat flow could break existing functionality
  - Mitigation: Keep existing chat endpoint, only change UI layer
  - Mitigation: Test with real vLLM endpoint before merging

### Medium Risk
- **Navigation redesign** — Changes to nav structure could affect existing routes
  - Mitigation: Keep all existing routes, only change navigation links
  - Mitigation: Test all navigation links before merging

### Low Risk
- **Icon system** — Replacing inline SVGs with library calls
  - Mitigation: Test all icons render correctly
  - Mitigation: Keep fallback inline SVGs if library fails

---

## Timeline Estimate

| Phase | Description | Days |
|-------|-------------|------|
| 1 | Foundation (tokens, toast, loading) | 1-2 |
| 2 | Navigation & Status (dropdown, nav redesign) | 2-3 |
| 3 | Icon System (Lucide, replace all icons) | 2-3 |
| 4 | Accessibility (ARIA, keyboard, focus) | 1-2 |
| 5 | Mobile Responsiveness (card view, stack) | 2-3 |
| 6 | Video Thumbnails (lazy load, placeholders) | 2-3 |
| 7 | Chat UI Redesign (bubbles, history, streaming) | 3-4 |
| **Total** | | **13-20 days** |

---

## Next Steps

1. **Approve this spec** — Confirm scope and priorities
2. **Create branch** — `feature/ui-ux-improvements` ✅ DONE
3. **Implement Phase 1** — Foundation (tokens, toast, loading)
4. **Test Phase 1** — Verify toast/loading work correctly
5. **Implement Phase 2** — Navigation & Status
6. **Test Phase 2** — Verify nav dropdown works
7. **Continue through phases** — One phase at a time
8. **Final review** — Test all pages, all breakpoints, all modes
9. **Merge to main** — After all tests pass
