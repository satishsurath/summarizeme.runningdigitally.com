/**
 * Icon System — SummarizeMe
 *
 * Provides a centralized icon library using inline SVG paths.
 * Replaces inline SVGs across templates and JS files.
 *
 * Usage:
 *   // JavaScript: renderIcon('bell', 'md') → returns SVG string
 *   // Jinja template: {{ render_icon('bell', 'md') }}
 *
 * Icons are stored as SVG path data. Sizes map to Tailwind classes.
 */
const IconLibrary = {
  icons: {
    bell: {
      path: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9',
      viewBox: '0 0 24 24',
      attrs: 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"',
    },
    sun: {
      path: 'M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z',
      viewBox: '0 0 24 24',
      attrs: 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"',
    },
    moon: {
      path: 'M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z',
      viewBox: '0 0 24 24',
      attrs: 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"',
    },
    menu: {
      path: 'M4 6h16M4 12h16M4 18h16',
      viewBox: '0 0 24 24',
      attrs: 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"',
    },
    x: {
      path: 'M6 18L18 6M6 6l12 12',
      viewBox: '0 0 24 24',
      attrs: 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"',
    },
    check: {
      path: 'M5 13l4 4L19 7',
      viewBox: '0 0 24 24',
      attrs: 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"',
    },
    warning: {
      path: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
      viewBox: '0 0 24 24',
      attrs: 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"',
    },
    info: {
      path: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
      viewBox: '0 0 24 24',
      attrs: 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"',
    },
    edit: {
      path: 'M200-200h57l391-391-57-57-391 391v57Zm-80 80v-170l528-527q12-11 26.5-17t30.5-6q16 0 31 6t26 18l55 56q12 11 17.5 26t5.5 30q0 16-5.5 30.5T817-647L290-120H120Z',
      viewBox: '0 -960 960 960',
      attrs: 'fill="currentColor"',
    },
    trash: {
      path: 'M280-120q-33 0-56.5-23.5T200-200v-520h-40v-80h200v-40h240v40h200v80h-40v520q0 33-23.5 56.5T680-120H280Z',
      viewBox: '0 -960 960 960',
      attrs: 'fill="currentColor"',
    },
    refresh: {
      path: 'M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 .34-.03.67-.08 1h2.02c.05-.33.06-.66.06-1 0-4.42-3.58-8-8-8zm-6 8c0-.34.03-.67.08-1H4.06c-.05.33-.06.66-.06 1 0 4.42 3.58 8 8 8v3l4-4-4-4v3c-3.31 0-6-2.69-6-6z',
      viewBox: '0 0 24 24',
      attrs: 'fill="currentColor"',
    },
    chat: {
      path: 'M240-400h320v-80H240v80Zm0-120h480v-80H240v80Zm0-120h480v-80H240v80ZM80-80v-720q0-33 23.5-56.5T160-880h640q33 0 56.5 23.5T880-800v480q0 33-23.5 56.5T800-240H240L80-80Z',
      viewBox: '0 -960 960 960',
      attrs: 'fill="currentColor"',
    },
    chevronDown: {
      path: 'M19 9l-7 7-7-7',
      viewBox: '0 0 24 24',
      attrs: 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"',
    },
    folder: {
      path: 'M200-200h57l391-391-57-57-391 391v57Zm-80 80v-170l528-527q12-11 26.5-17t30.5-6q16 0 31 6t26 18l55 56q12 11 17.5 26t5.5 30q0 16-5.5 30.5T817-647L290-120H120Z',
      viewBox: '0 -960 960 960',
      attrs: 'fill="currentColor"',
    },
    back: {
      path: 'M200-200h57l391-391-57-57-391 391v57Zm-80 80v-170l528-527q12-11 26.5-17t30.5-6q16 0 31 6t26 18l55 56q12 11 17.5 26t5.5 30q0 16-5.5 30.5T817-647L290-120H120Z',
      viewBox: '0 -960 960 960',
      attrs: 'fill="currentColor"',
    },
    document: {
      path: 'M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3',
      viewBox: '0 0 24 24',
      attrs: 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"',
    },
  },

  sizes: {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6',
    xl: 'w-8 h-8',
  },

  /**
   * Render an icon as an SVG string.
   * @param {string} name - Icon name (e.g., 'bell', 'edit')
   * @param {string} size - Size key ('sm', 'md', 'lg', 'xl')
   * @param {Object} extraAttrs - Additional SVG attributes
   * @returns {string} SVG element string
   */
  render(name, size = 'md', extraAttrs = {}) {
    const icon = this.icons[name];
    if (!icon) {
      return '';
    }
    const sizeClass = this.sizes[size] || this.sizes.md;
    const attrs = [
      `class="${sizeClass}"`,
      icon.attrs,
      `viewBox="${icon.viewBox}"`,
    ];
    if (extraAttrs.class) {
      attrs[0] = `class="${sizeClass} ${extraAttrs.class}"`;
    }
    if (extraAttrs.id) {
      attrs.push(`id="${extraAttrs.id}"`);
    }
    if (extraAttrs.style) {
      attrs.push(`style="${extraAttrs.style}"`);
    }
    return `<svg ${attrs.join(' ')}><path d="${icon.path}"/></svg>`;
  },

  /**
   * Render an icon with a custom path (for dynamic icons).
   * @param {string} path - SVG path data
   * @param {string} size - Size key
   * @param {Object} extraAttrs - Additional attributes
   * @returns {string} SVG element string
   */
  renderCustom(path, size = 'md', extraAttrs = {}) {
    const sizeClass = this.sizes[size] || this.sizes.md;
    const attrs = [
      `class="${sizeClass}"`,
      'fill="currentColor"',
      `viewBox="0 0 24 24"`,
    ];
    if (extraAttrs.class) {
      attrs[0] = `class="${sizeClass} ${extraAttrs.class}"`;
    }
    return `<svg ${attrs.join(' ')}><path d="${path}"/></svg>`;
  },
};

// Expose globally
if (typeof window !== 'undefined') {
  window.IconLibrary = IconLibrary;
}
