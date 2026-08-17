/**
 * Loading State Manager — SummarizeMe
 * 
 * Manages loading states for buttons and form elements.
 * Shows spinner + disables element during async operations.
 * Restores original state on completion.
 * 
 * Usage:
 *   loading.start('download', buttonEl)
 *   try { await doSomething() } finally { loading.end('download') }
 * 
 * Features:
 * - Unique IDs per operation (prevents conflicts)
 * - Preserves original button text
 * - Supports custom loading text
 * - Multiple concurrent operations
 */
class LoadingManager {
  constructor() {
    this.activeLoads = new Map();
  }

  /**
   * Start loading state on an element
   * @param {string} id - Unique operation ID
   * @param {HTMLElement} element - Button or element to disable
   * @param {string} [loadingText='Loading...'] - Custom loading text
   */
  start(id, element, loadingText = 'Loading...') {
    if (!element) return;
    
    this.activeLoads.set(id, element);
    element.disabled = true;
    element.dataset.originalText = element.textContent || '';
    element.dataset.originalClassName = element.className || '';
    
    // Add loading spinner and text
    element.innerHTML = `
      <svg class="spinner inline mr-2" fill="none" viewBox="0 0 24 24" aria-hidden="true">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
      ${loadingText}
    `;
    element.classList.add('opacity-75', 'cursor-not-allowed');
  }

  /**
   * End loading state on an element
   * @param {string} id - Unique operation ID
   */
  end(id) {
    const el = this.activeLoads.get(id);
    if (!el) return;
    
    // Restore original text and classes
    el.disabled = false;
    el.textContent = el.dataset.originalText || el.textContent;
    el.className = el.dataset.originalClassName || '';
    delete el.dataset.originalText;
    delete el.dataset.originalClassName;
    
    this.activeLoads.delete(id);
  }

  /**
   * Check if an operation is currently loading
   * @param {string} id - Operation ID
   * @returns {boolean}
   */
  isActive(id) {
    return this.activeLoads.has(id);
  }

  /**
   * Get all active operation IDs
   * @returns {string[]}
   */
  getActiveIds() {
    return Array.from(this.activeLoads.keys());
  }
}

// Global singleton
const loading = new LoadingManager();
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { LoadingManager, loading };
}
