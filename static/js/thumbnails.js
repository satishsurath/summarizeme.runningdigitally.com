/**
 * Thumbnail System — SummarizeMe
 *
 * Provides YouTube thumbnail URL generation, lazy loading via IntersectionObserver,
 * and placeholder fallbacks for video thumbnails.
 *
 * Usage:
 *   // Generate thumbnail URL from video ID
 *   const url = ThumbnailSystem.getUrl('dQw4w9WgXcQ');
 *
 *   // Lazy load thumbnails on page
 *   ThumbnailSystem.initLazyLoading();
 */
const ThumbnailSystem = {
  /**
   * Generate a YouTube thumbnail URL from a video ID.
   * @param {string} videoId - YouTube video ID
   * @param {string} quality - Thumbnail quality: 'default', 'mqdefault', 'hqdefault', 'sddefault', 'maxresdefault'
   * @returns {string} Thumbnail URL
   */
  getUrl(videoId, quality = 'mqdefault') {
    if (!videoId) return '';
    return `https://img.youtube.com/vi/${videoId}/${quality}.jpg`;
  },

  /**
   * Get the best available thumbnail URL for a video.
   * Tries maxresdefault first, falls back to hqdefault, then mqdefault.
   * @param {string} videoId - YouTube video ID
   * @returns {string} Best thumbnail URL
   */
  getBestUrl(videoId) {
    if (!videoId) return '';
    return this.getUrl(videoId, 'maxresdefault') || this.getUrl(videoId, 'hqdefault') || this.getUrl(videoId, 'mqdefault');
  },

  /**
   * Initialize lazy loading for all thumbnail images on the page.
   * Uses IntersectionObserver to load thumbnails only when they enter the viewport.
   */
  initLazyLoading() {
    const placeholders = document.querySelectorAll('[data-thumbnail]');
    if (!placeholders.length) return;

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const el = entry.target;
          const videoId = el.dataset.thumbnail;
          const img = el.querySelector('img');
          if (img && videoId) {
            img.src = this.getBestUrl(videoId);
            img.removeAttribute('data-thumbnail');
            observer.unobserve(el);
          }
        }
      });
    }, {
      rootMargin: '200px 0px',
      threshold: 0.01,
    });

    placeholders.forEach((el) => observer.observe(el));
  },

  /**
   * Create a thumbnail element for a video.
   * @param {string} videoId - YouTube video ID
   * @param {Object} options - Options: size, className, linkUrl
   * @returns {HTMLElement} Thumbnail element
   */
  create(videoId, options = {}) {
    const { size = 'mqdefault', className = '', linkUrl = null } = options;
    const url = this.getUrl(videoId, size);

    let wrapper;
    if (linkUrl) {
      wrapper = document.createElement('a');
      wrapper.href = linkUrl;
      wrapper.target = '_blank';
      wrapper.rel = 'noopener noreferrer';
    } else {
      wrapper = document.createElement('div');
    }

    wrapper.className = `thumbnail-wrapper ${className}`.trim();

    const img = document.createElement('img');
    img.alt = 'Video thumbnail';
    img.className = 'thumbnail';
    img.style.aspectRatio = '16/9';
    img.style.objectFit = 'cover';
    img.style.borderRadius = '0.5rem';
    img.style.backgroundColor = '#f3f4f6';
    img.dataset.thumbnail = videoId;

    // Placeholder while loading
    const placeholder = document.createElement('div');
    placeholder.className = 'thumbnail-placeholder';
    placeholder.style.aspectRatio = '16/9';
    placeholder.style.borderRadius = '0.5rem';
    placeholder.style.backgroundColor = '#e5e7eb';
    placeholder.style.display = 'flex';
    placeholder.style.alignItems = 'center';
    placeholder.style.justifyContent = 'center';

    // YouTube play button icon
    placeholder.innerHTML = `<svg class="w-8 h-8 text-gray-400" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>`;

    wrapper.appendChild(placeholder);
    wrapper.appendChild(img);

    // Replace placeholder when image loads
    img.onload = () => {
      if (placeholder.parentNode) {
        placeholder.style.opacity = '0';
        setTimeout(() => placeholder.remove(), 200);
      }
    };

    // Fallback if image fails to load
    img.onerror = () => {
      placeholder.style.display = 'flex';
      placeholder.style.opacity = '1';
      img.style.display = 'none';
    };

    return wrapper;
  },
};

// Expose globally
if (typeof window !== 'undefined') {
  window.ThumbnailSystem = ThumbnailSystem;
}
