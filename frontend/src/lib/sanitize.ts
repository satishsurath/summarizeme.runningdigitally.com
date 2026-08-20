/**
 * Lightweight HTML sanitizer for chat responses.
 * Strips dangerous tags/attributes while preserving formatting.
 *
 * Allowed elements: p, h1-h6, ul, ol, li, a, strong, em, code, pre, br, hr,
 *                   blockquote, img, svg, table, thead, tbody, tr, th, td
 * Allowed attributes: href (a), src/alt (img), viewBox/width/height/xlink:href (svg)
 *
 * Disallowed: script, iframe, object, embed, form, input, button, style,
 *             any element with on* attributes, javascript: URLs
 */

const ALLOWED_TAGS = new Set([
  "p", "h1", "h2", "h3", "h4", "h5", "h6", "div",
  "ul", "ol", "li", "dl", "dt", "dd",
  "a", "strong", "b", "em", "i", "code", "pre", "br", "hr",
  "blockquote", "img", "svg", "path",
  "table", "thead", "tbody", "tr", "th", "td",
  "sup", "sub", "span",
]);

const VOID_TAGS = new Set(["br", "hr", "img"]);

const ALLOWED_ATTRS: Record<string, Set<string>> = {
  a: new Set(["href", "title", "target", "rel", "class"]),
  div: new Set(["class"]),
  span: new Set(["class"]),
  img: new Set(["src", "alt", "title", "class"]),
  svg: new Set(["viewbox", "viewBox", "width", "height", "xmlns", "xlink:href", "fill", "stroke", "class"]),
  path: new Set(["d", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "class"]),
  td: new Set(["colspan", "rowspan", "class"]),
  th: new Set(["colspan", "rowspan", "class"]),
};

const STRIP_TAGS = new Set(["script", "iframe", "object", "embed", "form", "input", "button", "style", "link", "meta"]);

function escapeText(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttr(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function isDangerousUrl(url: string): boolean {
  const trimmed = url.trim().toLowerCase().replace(/[\x00-\x20]/g, "");
  if (trimmed.startsWith("javascript:") || trimmed.startsWith("vbscript:")) return true;
  if (trimmed.startsWith("data:") && !trimmed.startsWith("data:image/")) return true;
  return false;
}

/**
 * Parse a single attribute from attrStr starting at position `pos`.
 * Returns { name, value, end } where `end` is the position after the attribute.
 * Returns null if no attribute found at pos.
 */
function parseAttr(
  attrStr: string,
  pos: number,
): { name: string; value: string; end: number } | null {
  let value = "";
  const len = attrStr.length;
  // Skip whitespace
  while (pos < len && /\s/.test(attrStr[pos])) pos++;
  if (pos >= len) return null;

  // Read attribute name (up to = or whitespace)
  const nameStart = pos;
  while (pos < len && attrStr[pos] !== "=" && !/\s/.test(attrStr[pos])) pos++;
  const name = attrStr.slice(nameStart, pos).trim().toLowerCase();
  if (pos < len && attrStr[pos] === "=") {
    pos++;
    while (pos < len && /\s/.test(attrStr[pos])) pos++;
    if (pos < len && (attrStr[pos] === '"' || attrStr[pos] === "'")) {
      const quote = attrStr[pos];
      pos++;
      const valStart = pos;
      while (pos < len && attrStr[pos] !== quote) pos++;
      value = attrStr.slice(valStart, pos);
      if (pos < len) pos++;
    } else {
      const valStart = pos;
      while (pos < len && !/\s/.test(attrStr[pos]) && attrStr[pos] !== ">") pos++;
      value = attrStr.slice(valStart, pos);
    }
  }
  return { name, value, end: pos };
}

export function sanitizeHtml(html: string): string {
  if (!html) return "";

  let result = "";
  let i = 0;
  const len = html.length;
  const stack: string[] = [];

  while (i < len) {
    const lt = html.indexOf("<", i);
    if (lt === -1) {
      result += escapeText(html.slice(i));
      break;
    }

    // Text before tag
    if (lt > i) {
      result += escapeText(html.slice(i, lt));
    }

    // Closing tag
    if (lt + 1 < len && html[lt + 1] === "/") {
      const gt = html.indexOf(">", lt);
      if (gt === -1) { i = lt + 1; continue; }
      const tagName = html.slice(lt + 2, gt).trim().toLowerCase();
      for (let s = stack.length - 1; s >= 0; s--) {
        if (stack[s] === tagName) {
          stack.splice(s);
          result += `</${tagName}>`;
          break;
        }
      }
      i = gt + 1;
      continue;
    }

    // Opening tag
    const gt = html.indexOf(">", lt);
    if (gt === -1) { i = lt + 1; continue; }

    const tagContent = html.slice(lt + 1, gt);
    const spaceIdx = tagContent.indexOf(" ");
    const tagName = spaceIdx === -1
      ? tagContent.trim().toLowerCase()
      : tagContent.slice(0, spaceIdx).trim().toLowerCase();

    // Strip dangerous tags entirely
    if (STRIP_TAGS.has(tagName)) {
      const closeTag = `</${tagName}>`;
      const closeIdx = html.toLowerCase().indexOf(closeTag, gt + 1);
      i = closeIdx !== -1 ? closeIdx + closeTag.length : gt + 1;
      continue;
    }

    // Parse attributes
    let attrs = "";
    if (spaceIdx !== -1) {
      let pos = spaceIdx + 1;
      while (pos < tagContent.length) {
        const attr = parseAttr(tagContent, pos);
        if (!attr) break;
        pos = attr.end;

        // Skip dangerous attributes (on*)
        if (attr.name.startsWith("on")) continue;

        // Validate URL attribute values
        const isUrlAttr = attr.name === "href" || attr.name === "src" || attr.name === "xlink:href";
        if (isUrlAttr && isDangerousUrl(attr.value)) continue;

        // Only keep allowed attributes
        const allowedForTag = ALLOWED_ATTRS[tagName];
        if (!allowedForTag || allowedForTag.has(attr.name)) {
          if (attr.value) {
            attrs += ` ${attr.name}="${escapeAttr(attr.value)}"`;
          } else {
            attrs += ` ${attr.name}`;
          }
        }
      }
    }

    // Strip disallowed tags but keep content
    if (!ALLOWED_TAGS.has(tagName)) {
      const closeTag = `</${tagName}>`;
      const closeIdx = html.toLowerCase().indexOf(closeTag, gt + 1);
      if (closeIdx !== -1) {
        result += escapeText(html.slice(gt + 1, closeIdx));
        i = closeIdx + closeTag.length;
      } else {
        const nextLt = html.indexOf("<", gt + 1);
        if (nextLt === -1) {
          result += escapeText(html.slice(gt + 1));
          i = len;
        } else {
          result += escapeText(html.slice(gt + 1, nextLt));
          i = nextLt;
        }
      }
      continue;
    }

    // Emit allowed tag
    if (VOID_TAGS.has(tagName)) {
      result += `<${tagName}${attrs}>`;
    } else {
      result += `<${tagName}${attrs}>`;
      stack.push(tagName);
    }
    i = gt + 1;
  }

  // Close unclosed allowed tags
  for (let s = stack.length - 1; s >= 0; s--) {
    const tag = stack[s];
    if (ALLOWED_TAGS.has(tag)) {
      result += `</${tag}>`;
    }
  }

  return result;
}
