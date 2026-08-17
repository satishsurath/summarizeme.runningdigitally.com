/**
 * Chat UI — SummarizeMe
 *
 * Provides a chat message bubble UI with:
 * - Message bubbles (user/assistant)
 * - Message history with scroll
 * - Enter to send, Shift+Enter for newline
 * - Loading indicator during generation
 * - Error message bubbles
 *
 * Usage:
 *   const chat = new ChatUI({
 *     textareaId: 'userQuery',
 *     resultId: 'chatResult',
 *     sendBtnId: 'sendBtn',
 *     apiUrl: '/api/chat-channel/mychannel',
 *     method: 'POST',
 *     body: { query, data_type, model_name }
 *   });
 */
class ChatUI {
  constructor(options) {
    this.textarea = document.getElementById(options.textareaId);
    this.result = document.getElementById(options.resultId);
    this.sendBtn = document.getElementById(options.sendBtnId);
    this.apiUrl = options.apiUrl;
    this.method = options.method || 'POST';
    this.getBody = options.getBody || ((query) => ({ query }));
    this.isLoading = false;
    this._instanceId = `chat-${Math.random().toString(36).slice(2, 9)}`;

    this.init();
  }

  init() {
    // Enter to send, Shift-Enter for newline
    this.textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    // Send button click
    if (this.sendBtn) {
      this.sendBtn.addEventListener('click', () => this.sendMessage());
    }

    // Disable textarea while loading
    this.textarea.addEventListener('input', () => this.updateSendButton());
  }

  updateSendButton() {
    if (this.sendBtn) {
      const hasText = this.textarea.value.trim().length > 0;
      this.sendBtn.disabled = this.isLoading || !hasText;
      this.sendBtn.style.opacity = (this.isLoading || !hasText) ? '0.5' : '1';
      this.sendBtn.style.cursor = (this.isLoading || !hasText) ? 'not-allowed' : 'pointer';
    }
  }

  async sendMessage() {
    const query = this.textarea.value.trim();
    if (!query || this.isLoading) return;

    // Add user message bubble
    this.addMessage('user', query);
    this.textarea.value = '';
    this.updateSendButton();

    // Show loading indicator
    this.isLoading = true;
    this.updateSendButton();
    this.setBusy(true);
    this.showLoading();

    try {
      const body = this.getBody(query);
      const resp = await fetch(this.apiUrl, {
        method: this.method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      }

      const data = await resp.json();
      this.hideLoading();
      this.addMessage('assistant', data.answer || 'No response');
    } catch (err) {
      this.hideLoading();
      this.addMessage('error', `Error: ${err.message || err}`);
    } finally {
      this.isLoading = false;
      this.updateSendButton();
      this.setBusy(false);
      // Focus textarea after a short delay to ensure DOM is stable
      requestAnimationFrame(() => this.textarea.focus());
    }
  }

  addMessage(role, content) {
    const bubble = document.createElement('div');
    bubble.className = `flex ${role === 'user' ? 'justify-end' : 'justify-start'} mb-4`;

    const inner = document.createElement('div');
    inner.className = `max-w-[80%] rounded-lg px-4 py-3 ${this.getMessageClasses(role)}`;

    if (role === 'user') {
      // User input: escape HTML to prevent XSS
      const p = document.createElement('p');
      p.className = 'text-white text-sm';
      p.textContent = content;
      inner.appendChild(p);
    } else if (role === 'assistant') {
      // Assistant response: backend already renders safe HTML via md_safe()
      // No double-escaping — insert directly as innerHTML
      const div = document.createElement('div');
      div.className = 'prose prose-sm dark:prose-invert max-w-none text-gray-900 dark:text-gray-100 text-sm';
      div.innerHTML = content;
      inner.appendChild(div);
    } else {
      // Error message: escape HTML for safety
      const p = document.createElement('p');
      p.className = 'text-red-600 dark:text-red-400 text-sm flex items-center gap-2';
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('class', 'w-4 h-4 flex-shrink-0');
      svg.setAttribute('fill', 'currentColor');
      svg.setAttribute('viewBox', '0 0 20 20');
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('fill-rule', 'evenodd');
      path.setAttribute('d', 'M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z');
      path.setAttribute('clip-rule', 'evenodd');
      svg.appendChild(path);
      const span = document.createElement('span');
      span.textContent = content;
      p.appendChild(svg);
      p.appendChild(span);
      inner.appendChild(p);
    }

    bubble.appendChild(inner);
    this.result.appendChild(bubble);
    this.scrollToBottom();
  }

  showLoading() {
    const loading = document.createElement('div');
    loading.className = 'flex justify-start mb-4';
    loading.dataset.chatLoadingId = this._instanceId;
    loading.innerHTML = `
      <div class="max-w-[80%] rounded-lg px-4 py-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
        <div class="flex items-center gap-2">
          <svg class="animate-spin h-4 w-4 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span class="text-sm text-gray-500 dark:text-gray-400">Thinking...</span>
        </div>
      </div>
    `;
    this.result.appendChild(loading);
    this.scrollToBottom();
  }

  hideLoading() {
    const loading = this.result.querySelector(`[data-chat-loading-id="${this._instanceId}"]`);
    if (loading) loading.remove();
  }

  setBusy(busy) {
    this.result.setAttribute('aria-busy', String(busy));
  }

  getMessageClasses(role) {
    switch (role) {
      case 'user':
        return 'bg-blue-500 text-white rounded-br-none';
      case 'assistant':
        return 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-bl-none';
      case 'error':
        return 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-bl-none';
      default:
        return 'bg-gray-100 dark:bg-gray-800';
    }
  }

  scrollToBottom() {
    this.result.scrollTop = this.result.scrollHeight;
  }
}

// Expose globally
if (typeof window !== 'undefined') {
  window.ChatUI = ChatUI;
}
