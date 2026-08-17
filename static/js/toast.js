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
    if (duration < 0) duration = 0;
    if (duration > 30000) duration = 30000;
    const validTypes = ['success', 'error', 'warning', 'info'];
    if (!validTypes.includes(type)) type = 'info';

    // Enforce max concurrent toasts
    const existing = this.container?.querySelectorAll('.toast') || [];
    if (existing.length >= 5) {
      const oldest = existing[0];
      if (oldest) this.dismiss(oldest.id);
    }

    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    const el = document.createElement('div');
    el.id = id;
    el.className = `toast toast-${type} animate-slide-in-right`;
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');

    const iconSpan = document.createElement('span');
    iconSpan.innerHTML = this._iconMap(type);
    iconSpan.className = 'flex-shrink-0';

    const messageSpan = document.createElement('span');
    messageSpan.className = 'flex-1 text-sm font-medium';
    messageSpan.textContent = message;

    const dismissBtn = document.createElement('button');
    dismissBtn.className = 'p-1 rounded hover:opacity-70 focus:outline-none focus:ring-2 focus:ring-primary-500';
    dismissBtn.setAttribute('aria-label', 'Dismiss notification');
    dismissBtn.innerHTML = this._iconMap('error');
    dismissBtn.addEventListener('click', () => this.dismiss(id));

    el.appendChild(iconSpan);
    el.appendChild(messageSpan);
    el.appendChild(dismissBtn);
    this.container?.appendChild(el);

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
    if (!this.container) return;
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
      success: IconLibrary.render('check', 'md', { class: 'text-green-500' }),
      error: IconLibrary.render('x', 'md', { class: 'text-red-500' }),
      warning: IconLibrary.render('warning', 'md', { class: 'text-yellow-500' }),
      info: IconLibrary.render('info', 'md', { class: 'text-blue-500' }),
    };
    return map[type] || map.info;
  }
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
