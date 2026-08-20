import { sanitizeHtml } from "./sanitize";

/**
 * Enhanced Markdown-to-HTML converter for reasoning thinking blocks.
 * Turns raw model thoughts into clean, readable, structured visual layouts.
 */
export function renderMarkdownToHtml(markdown: string): string {
  if (!markdown) return "";

  let html = markdown;

  // 1. Convert code blocks ```lang\ncode\n```
  html = html.replace(/```(?:\w+)?\n([\s\S]*?)```/g, (_, code) => {
    return `<pre class="my-2 p-2.5 rounded-md bg-purple-950/80 text-purple-100 font-mono text-[11px] overflow-x-auto border border-purple-800/40"><code>${escapeHtml(code.trim())}</code></pre>`;
  });

  // 2. Convert inline code `code`
  html = html.replace(
    /`([^`]+)`/g,
    '<code class="px-1.5 py-0.5 rounded bg-purple-200/60 dark:bg-purple-900/50 font-mono text-[11px] text-purple-900 dark:text-purple-200">$1</code>',
  );

  // 3. Headings ###, ##, #
  html = html.replace(
    /^### (.*$)/gim,
    '<h3 class="text-xs font-bold text-purple-950 dark:text-purple-100 mt-3 mb-1">$1</h3>',
  );
  html = html.replace(
    /^## (.*$)/gim,
    '<h2 class="text-xs font-bold text-purple-950 dark:text-purple-100 mt-3.5 mb-1.5">$1</h2>',
  );
  html = html.replace(
    /^# (.*$)/gim,
    '<h1 class="text-sm font-bold text-purple-950 dark:text-purple-100 mt-4 mb-2">$1</h1>',
  );

  // 4. Bold **text** and Italic *text*
  html = html.replace(
    /\*\*([^*]+)\*\*/g,
    '<strong class="font-semibold text-purple-950 dark:text-purple-100">$1</strong>',
  );
  html = html.replace(/\*([^*]+)\*/g, '<em class="italic">$1</em>');

  // 5. Expand inline dashes " - " into line breaks for bullet items if inline
  html = html.replace(/\s+-\s+(?=[A-Z0-9"'\*\(\[\{])/g, "\n- ");

  // 6. Highlight key reasoning stage labels (e.g., Self-Correction:, Output Generation:)
  html = html.replace(
    /(?:^|\n|\s)(Self-Correction\/Refinement[^:\n]*:|Self-Correction\/Verification[^:\n]*:|Output Generation:|Final Output Generation:|Final Check of the Prompt:)/gim,
    '\n\n<strong class="inline-block mt-2 mb-1 px-2 py-0.5 rounded bg-purple-200/80 dark:bg-purple-900/60 text-purple-900 dark:text-purple-200 text-[11px] font-bold">$1</strong>\n',
  );

  // 7. Ordered lists (1. Item)
  html = html.replace(
    /^(\d+)\.\s+(.*$)/gim,
    '<li class="ml-4 list-decimal my-1 text-purple-950 dark:text-purple-100">$2</li>',
  );

  // 8. Unordered lists (- Item or * Item)
  html = html.replace(
    /^[-*]\s+(.*$)/gim,
    '<li class="ml-4 list-disc my-0.5 text-purple-950 dark:text-purple-200/90">$1</li>',
  );

  // Wrap contiguous <li> lines in <ol>/<ul>
  html = html.replace(
    /((?:<li class="ml-4 list-decimal my-1 text-purple-950 dark:text-purple-100">.*?<\/li>\s*)+)/g,
    '<ol class="my-2 pl-2 space-y-1">$1</ol>',
  );
  html = html.replace(
    /((?:<li class="ml-4 list-disc my-0\.5 text-purple-950 dark:text-purple-200\/90">.*?<\/li>\s*)+)/g,
    '<ul class="my-1.5 pl-2 space-y-0.5">$1</ul>',
  );

  // 9. Style checkmark badges ✅ cleanly
  html = html.replace(
    /✅/g,
    '<span class="inline-flex items-center justify-center w-4 h-4 text-[10px] text-green-500 font-bold bg-green-100 dark:bg-green-950/60 rounded-full mx-1" title="Passed check">✓</span>',
  );

  // 10. Single and double line breaks into clean paragraph structure
  html = html.replace(/\n\n+/g, '<div class="h-2.5"></div>');
  html = html.replace(/\n/g, '<br />');

  return sanitizeHtml(html);
}

function escapeHtml(str: string): string {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
