/**
 * Helper utilities to parse, decode, and isolate model thinking/reasoning processes.
 */

export interface ParsedMessageContent {
  thinking: string | null;
  answer: string;
  isThinkingActive: boolean;
}

function cleanHtmlWrapper(str: string): string {
  if (!str) return "";
  let s = str.trim();
  s = s.replace(/^(?:<p>|<br\s*\/?>|<div>|\s)+/i, "");
  s = s.replace(/(?:<\/p>|<br\s*\/?>|<\/div>|\s)+$/i, "");
  return s;
}

function cleanAnswerStart(answer: string): string {
  if (!answer) return "";
  let cleaned = answer.trim();
  while (true) {
    const prev = cleaned;
    cleaned = cleaned
      .replace(
        /^(?:<p>\s*(?:[✅✓]|\[Response Text\]|\[Output\]|\[Done\.?\]|Proceeds\.?)\s*<\/p>|<br\s*\/?>|\s)*/gi,
        "",
      )
      .trim();
    cleaned = cleaned
      .replace(/^(?:->|=>|-&gt;|[✅✓]|\"|'|\s)+/gi, "")
      .trim();
    if (cleaned === prev) break;
  }
  return cleaned;
}

/**
 * Decode HTML entities like &#39; -> ' and &#34; -> " for clean typography.
 */
export function decodeHtmlEntities(str: string): string {
  if (!str) return "";
  return str
    .replace(/&#39;/g, "'")
    .replace(/&#34;/g, '"')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, "&");
}

/**
 * Parse raw assistant message content to separate reasoning/thinking thoughts from the main answer.
 */
export function parseThinkingContent(
  content: string,
  isStreaming: boolean = false,
): ParsedMessageContent {
  if (!content) {
    return { thinking: null, answer: "", isThinkingActive: false };
  }

  const decoded = decodeHtmlEntities(content);

  const normalized = decoded
    .replace(/&lt;think&gt;/gi, "<think>")
    .replace(/&lt;\/think&gt;/gi, "</think>");

  // ---------------------------------------------------------------------------
  // Case 1: <think> ... </think> XML tags (e.g. DeepSeek R1 / Qwen reasoning)
  // ---------------------------------------------------------------------------
  const thinkStart = normalized.indexOf("<think>");
  if (thinkStart !== -1) {
    const thinkEnd = normalized.indexOf("</think>", thinkStart);
    if (thinkEnd !== -1) {
      // Closed thinking block
      const thinking = normalized.slice(thinkStart + 7, thinkEnd).trim();
      const rawAnswer = normalized.slice(thinkEnd + 8).trim();
      const answer = cleanAnswerStart(cleanHtmlWrapper(rawAnswer));
      return {
        thinking: cleanHtmlWrapper(thinking) || null,
        answer,
        isThinkingActive: false,
      };
    } else {
      // Open / in-progress thinking block
      const thinking = normalized.slice(thinkStart + 7).trim();
      return {
        thinking: cleanHtmlWrapper(thinking) || null,
        answer: "",
        isThinkingActive: isStreaming,
      };
    }
  }

  // ---------------------------------------------------------------------------
  // Case 2: Model output prefix ("Here's a thinking process:" / "Thinking Process:")
  // ---------------------------------------------------------------------------
  const thinkingPrefixMatch = normalized.match(
    /^(?:\s*<(?:p|div|span|strong)[^>]*>)*\s*(?:Here(?:'|&#39;|\u2019)?s a thinking process:|Thinking Process:|Thought Process:)/i,
  );
  if (thinkingPrefixMatch) {
    const prefixLen = thinkingPrefixMatch[0].length;
    const rest = normalized.slice(prefixLen);

    // Transition marker regex
    const transitionRegex =
      /(?:\(Done\.\)|\[Done\.\]|\(Done\)|\[Done\]|\(Finished\.\)|\[Finished\.\]|\[Output Generation\](?:\s*(?:-|&amp;|-&gt;|->)\s*Proceeds)?|\[Output\]|Final Answer:|Final Output:|(?:\[)?Proceeds?(?:\.|\s*\])?|✅ Output matches\.\s*(?:\[Proceeds\])?)/gi;

    // Find ALL matches in rest
    const matches = Array.from(rest.matchAll(transitionRegex));

    if (matches.length > 0) {
      // Pick the LAST match that leaves non-empty answer text
      let chosenMatch = matches[matches.length - 1];
      for (let i = matches.length - 1; i >= 0; i--) {
        const m = matches[i];
        if (m.index !== undefined) {
          const candidateAns = rest.slice(m.index + m[0].length).trim();
          if (candidateAns.length > 0) {
            chosenMatch = m;
            break;
          }
        }
      }

      if (chosenMatch && chosenMatch.index !== undefined) {
        let thinking = rest.slice(0, chosenMatch.index + chosenMatch[0].length).trim();
        let answer = rest.slice(chosenMatch.index + chosenMatch[0].length).trim();

        thinking = cleanHtmlWrapper(thinking);
        answer = cleanAnswerStart(cleanHtmlWrapper(answer));

        if (thinking && answer) {
          return {
            thinking,
            answer,
            isThinkingActive: false,
          };
        }
      }
    }

    // Fallback: Split on double newline before final paragraph
    const doubleNewlineMatch = rest.match(
      /(?:<\/p>\s*<p>(?=(?:This video|Here is|In this|The video|Answer:|[A-Z][a-z0-9\s]{2,30}:))|\n\n(?=(?:This video|Here is|In this|The video|Answer:|[A-Z][a-z0-9\s]{2,30}:)))/i,
    );
    if (doubleNewlineMatch && doubleNewlineMatch.index !== undefined) {
      let thinking = rest.slice(0, doubleNewlineMatch.index).trim();
      let answer = rest.slice(doubleNewlineMatch.index + doubleNewlineMatch[0].length).trim();
      thinking = cleanHtmlWrapper(thinking);
      answer = cleanAnswerStart(cleanHtmlWrapper(answer));
      return {
        thinking: thinking || null,
        answer: answer || decoded,
        isThinkingActive: false,
      };
    } else if (isStreaming) {
      return {
        thinking: cleanHtmlWrapper(rest.trim()) || null,
        answer: "",
        isThinkingActive: true,
      };
    }
  }

  // ---------------------------------------------------------------------------
  // Case 3: Standard answer without explicit thinking block
  // ---------------------------------------------------------------------------
  return {
    thinking: null,
    answer: cleanAnswerStart(decoded),
    isThinkingActive: false,
  };
}
