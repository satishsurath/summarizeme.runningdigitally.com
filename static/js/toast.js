/**
 * Toast Notification System — SummarizeMe
 * 
 * Non-blocking toast notifications that slide in from the right.
 * Auto-dismiss after configurable duration (default 5s).
 * Supports success, error, warning, and info types.
 * 
 * Usage:
 *   toast.success('Channel added successfully')
 *   toast.error('Failed to download channel')
 *   toast.warning('Rate limit approaching')
 *   toast.info('Task completed')
 *   toast.show('Custom message', 'info', 3000)
 *   toast.dismiss(id)  // dismiss specific toast
 */
class ToastManager {
  constructor() {
    this.container = null;
    this.init();
  }

  init() {
    this.container = document.createElement('div');
    this.container.id = 'toast-container';
    this.container.className = 'toast-container';
    this.container.setAttribute('aria-live', 'polite');
    this.container.setAttribute('aria-atomic', 'true');
    document.body.appendChild(this.container);
  }

  /**
   * Show a toast notification
   * @param {string} message - Toast message
   * @param {string} type - 'success' | 'error' | 'warning' | 'info'
   * @param {number} duration - Auto-dismiss in ms (0 = manual dismiss only)
   * @returns {string} Toast ID
   */
  show(message, type = 'info', duration = 5000) {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    const el = document.createElement('div');
    el.id = id;
    el.className = `toast toast-${type} animate-slide-in-right`;
    el.setAttribute('role', 'status');
    el.innerHTML = `
      ${this._iconMap(type)}
      <span class="flex-1 text-sm font-medium">${this._escapeHtml(message)}</span>
      <button onclick="toast.dismiss('${id}')" 
              class="p-1 rounded hover:opacity-70 focus:outline-none focus:ring-2 focus:ring-primary-500"
              aria-label="Dismiss notification">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    `;
    this.container.appendChild(el);

    // Auto-dismiss
    if (duration > 0) {
      setTimeout(() => this.dismiss(id), duration);
    }
    return id;
  }

  /**
   * Dismiss a specific toast
   * @param {string} id - Toast ID
   */
  dismiss(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('animate-slide-in-right');
    el.classList.add('animate-slide-out-right');
    setTimeout(() => el.remove(), 300);
  }

  /**
   * Dismiss all toasts
   */
  dismissAll() {
    this.container.querySelectorAll('.toast').forEach((el) => {
      el.classList.add('animate-slide-out-right');
      setTimeout(() => el.remove(), 300);
    });
  }

  success(msg, duration) { return this.show(msg, 'success', duration); }
  error(msg, duration) { return this.show(msg, 'error', duration); }
  warning(msg, duration) { return this.show(msg, 'warning', duration); }
  info(msg, duration) { return this.show(msg, 'info', duration); }

  /** @private */
  _iconMap(type) {
    const map = {
      success: '<svg class="w-5 h-5 text-green-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>',
      error: '<svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>',
      warning: '<svg class="w-5 h-5 text-yellow-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>',
      info: '<svg class="w-5 h-5 text-blue-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
    };
    return map[type] || map.info;
  }

  /** @private */
  _escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Global singleton
const toast = new ToastManager();
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { ToastManager, toast };
}
