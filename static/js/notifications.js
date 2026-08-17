/**
 * Notification Dropdown — SummarizeMe
 *
 * Polls /api/active-tasks every 5 seconds and updates the notification
 * dropdown in the nav. Shows badge count, task status dots, and progress.
 *
 * Features:
 * - Auto-polling every 5 seconds
 * - Badge count for active tasks
 * - Status dots (green/yellow/red)
 * - Progress bars for in-progress tasks
 * - Click task row navigates to /status
 * - Closes on outside click or Escape
 */
document.addEventListener('DOMContentLoaded', () => {
  const bellBtn = document.getElementById('notificationBtn');
  const dropdown = document.getElementById('notificationDropdown');
  const badge = document.getElementById('notificationBadge');
  const list = document.getElementById('notificationList');
  const mobileMenuBtn = document.getElementById('mobile-menu-button');
  const mobileMenu = document.getElementById('mobile-menu');

  if (!bellBtn || !dropdown || !list) return;

  // Toggle dropdown on bell click
  bellBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = !dropdown.classList.contains('hidden');
    dropdown.classList.toggle('hidden');
    bellBtn.setAttribute('aria-expanded', !isOpen);
    if (!isOpen) {
      fetchActiveTasks();
    }
  });

  // Close dropdown on outside click
  document.addEventListener('click', (e) => {
    if (!dropdown.contains(e.target) && e.target !== bellBtn) {
      dropdown.classList.add('hidden');
      bellBtn.setAttribute('aria-expanded', 'false');
    }
  });

  // Close dropdown on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      dropdown.classList.add('hidden');
      bellBtn.setAttribute('aria-expanded', 'false');
      if (mobileMenu && !mobileMenu.classList.contains('hidden')) {
        mobileMenu.classList.add('hidden');
        mobileMenuBtn.setAttribute('aria-expanded', 'false');
      }
    }
  });

  // Mobile menu toggle
  if (mobileMenuBtn && mobileMenu) {
    mobileMenuBtn.addEventListener('click', () => {
      const isOpen = !mobileMenu.classList.contains('hidden');
      mobileMenu.classList.toggle('hidden');
      mobileMenuBtn.setAttribute('aria-expanded', !isOpen);
    });
  }

  /**
   * Fetch active tasks from API and update the dropdown.
   */
  async function fetchActiveTasks() {
    try {
      const res = await fetch('/api/active-tasks');
      if (!res.ok) return;
      const tasks = await res.json();
      renderTasks(tasks);
    } catch {
      // Silently fail — dropdown will show "No active tasks"
    }
  }

  /**
   * Render active tasks in the dropdown.
   * @param {Array} tasks - Array of task objects
   */
  function renderTasks(tasks) {
    if (!tasks || tasks.length === 0) {
      badge.classList.add('hidden');
      list.innerHTML = `
        <div class="px-4 py-6 text-center text-gray-500 dark:text-gray-400 text-sm">
          No active tasks
        </div>
      `;
      return;
    }

    // Update badge
    badge.classList.remove('hidden');
    badge.textContent = tasks.length;

    // Render task list
    let html = '';
    tasks.forEach(task => {
      const statusClass = task.status === 'completed' ? 'status-dot-success'
        : task.status === 'failed' ? 'status-dot-error'
        : 'status-dot-info';

      const progressPercent = task.total > 0
        ? Math.round((task.processed / task.total) * 100)
        : 0;

      html += `
        <div class="px-4 py-3 border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer transition-colors"
             onclick="window.location.href='/status'"
             role="menuitem">
          <div class="flex items-center gap-2 mb-1">
            <span class="status-dot ${statusClass}"></span>
            <span class="text-sm text-gray-700 dark:text-gray-300 truncate">${escapeHtml(task.name)}</span>
          </div>
          ${task.total > 0 ? `
            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1">
              <div class="bg-primary-500 h-1.5 rounded-full transition-all" style="width: ${progressPercent}%"></div>
            </div>
            <div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">${task.processed} / ${task.total}</div>
          ` : ''}
        </div>
      `;
    });
    list.innerHTML = html;
  }

  /**
   * Escape HTML to prevent XSS.
   * @param {string} text
   * @returns {string}
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Poll every 5 seconds
  setInterval(fetchActiveTasks, 5000);
});
