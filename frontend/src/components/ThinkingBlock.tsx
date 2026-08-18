"use client";

import { useEffect, useState } from "react";
import { renderMarkdownToHtml } from "../lib/markdown";

interface ThinkingBlockProps {
  thinking: string;
  isStreaming?: boolean;
}

export function ThinkingBlock({ thinking, isStreaming = false }: ThinkingBlockProps) {
  // Open by default while streaming, closed when finished
  const [isExpanded, setIsExpanded] = useState<boolean>(isStreaming);
  const [userToggled, setUserToggled] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<"formatted" | "raw">("formatted");

  // Auto-collapse when streaming completes unless user manually toggled
  useEffect(() => {
    if (!userToggled) {
      setIsExpanded(isStreaming);
    }
  }, [isStreaming, userToggled]);

  if (!thinking && !isStreaming) return null;

  const toggleExpand = () => {
    setUserToggled(true);
    setIsExpanded((prev) => !prev);
  };

  const renderedHtml = renderMarkdownToHtml(
    thinking || (isStreaming ? "Formulating response structure..." : ""),
  );

  return (
    <div className="mb-3 rounded-lg border border-purple-200/80 dark:border-purple-900/40 bg-purple-50/40 dark:bg-purple-950/20 overflow-hidden text-xs transition-all">
      {/* Header / Toggle bar */}
      <div
        onClick={toggleExpand}
        className="flex items-center justify-between w-full px-3 py-2 bg-purple-100/60 dark:bg-purple-900/30 hover:bg-purple-100 dark:hover:bg-purple-900/50 transition-colors select-none text-left cursor-pointer"
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggleExpand();
          }
        }}
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-2">
          {/* Brain / Sparkles Icon */}
          <svg
            className="w-4 h-4 text-purple-600 dark:text-purple-400 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
            />
          </svg>

          <span className="font-medium text-purple-900 dark:text-purple-200">
            {isStreaming ? "Thinking..." : "Thought process"}
          </span>

          {isStreaming && (
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500" />
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Formatted vs Raw View Mode Pills */}
          {isExpanded && (
            <div
              className="flex items-center gap-0.5 bg-purple-200/60 dark:bg-purple-900/50 p-0.5 rounded-md border border-purple-300/50 dark:border-purple-800/50"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                type="button"
                onClick={() => setViewMode("formatted")}
                className={`px-2 py-0.5 rounded text-[10px] font-semibold transition-colors ${
                  viewMode === "formatted"
                    ? "bg-purple-600 text-white shadow-xs"
                    : "text-purple-800 dark:text-purple-200 hover:bg-purple-300/40 dark:hover:bg-purple-800/40"
                }`}
                title="View formatted HTML markdown"
              >
                Formatted
              </button>
              <button
                type="button"
                onClick={() => setViewMode("raw")}
                className={`px-2 py-0.5 rounded text-[10px] font-semibold transition-colors ${
                  viewMode === "raw"
                    ? "bg-purple-600 text-white shadow-xs"
                    : "text-purple-800 dark:text-purple-200 hover:bg-purple-300/40 dark:hover:bg-purple-800/40"
                }`}
                title="View raw markdown source"
              >
                Raw
              </button>
            </div>
          )}

          <div className="flex items-center gap-1 text-purple-700 dark:text-purple-300 text-[11px]">
            <span>{isExpanded ? "Hide" : "Show"}</span>
            <svg
              className={`w-3.5 h-3.5 transition-transform duration-200 ${
                isExpanded ? "rotate-180" : ""
              }`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
      </div>

      {/* Expanded thinking body */}
      {isExpanded && (
        <div className="px-3.5 py-3 bg-purple-50/20 dark:bg-purple-950/40 border-t border-purple-200/50 dark:border-purple-900/30 max-h-96 overflow-y-auto">
          {viewMode === "formatted" ? (
            <div
              className="text-[12px] leading-relaxed text-purple-950 dark:text-purple-200"
              dangerouslySetInnerHTML={{ __html: renderedHtml }}
            />
          ) : (
            <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-purple-950 dark:text-purple-200/90 select-text">
              {thinking || (isStreaming ? "Formulating response structure..." : "")}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
