"use client";

import { useEffect, useRef, useState } from "react";

interface CopyMessageMenuProps {
  content: string;
  thinking?: string | null;
  answer?: string;
  role: "user" | "assistant";
}

export function CopyMessageMenu({
  content,
  thinking,
  answer,
  role,
}: CopyMessageMenuProps) {
  const [copied, setCopied] = useState<boolean>(false);
  const [copiedLabel, setCopiedLabel] = useState<string>("Copied!");
  const [menuOpen, setMenuOpen] = useState<boolean>(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpen]);

  const copyToClipboard = async (textToCopy: string, label: string = "Copied!") => {
    try {
      await navigator.clipboard.writeText(textToCopy);
      setCopiedLabel(label);
      setCopied(true);
      setMenuOpen(false);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text: ", err);
    }
  };

  const stripHtml = (html: string): string => {
    if (!html) return "";
    return html
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/p>/gi, "\n\n")
      .replace(/<\/li>/gi, "\n")
      .replace(/<[^>]+>/g, "")
      .replace(/&amp;/g, "&")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  };

  // Default Copy action (Answer only, plain text)
  const handleDefaultCopy = () => {
    const textToCopy = role === "user" ? content : stripHtml(answer || content);
    copyToClipboard(textToCopy, "Copied!");
  };

  // Handle right-click context menu
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setMenuOpen(true);
  };

  const hasThinking = Boolean(thinking && thinking.trim().length > 0);

  return (
    <div className="relative inline-block" ref={menuRef}>
      <div className="flex items-center gap-0.5">
        {/* Main Copy Button */}
        <button
          type="button"
          onClick={handleDefaultCopy}
          onContextMenu={handleContextMenu}
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium transition-colors ${
            role === "user"
              ? "text-blue-100 hover:bg-blue-600/60 hover:text-white"
              : "text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-800 dark:hover:text-gray-200"
          }`}
          title="Click to copy answer. Right-click or click arrow for options."
        >
          {copied ? (
            <>
              <svg
                className="w-3.5 h-3.5 text-green-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-green-500 font-semibold">{copiedLabel}</span>
            </>
          ) : (
            <>
              <svg
                className="w-3.5 h-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                />
              </svg>
              <span>Copy</span>
            </>
          )}
        </button>

        {/* Options Dropdown Trigger Button */}
        <button
          type="button"
          onClick={() => setMenuOpen((prev) => !prev)}
          className={`p-0.5 rounded-md text-[11px] transition-colors ${
            role === "user"
              ? "text-blue-200 hover:bg-blue-600/60 hover:text-white"
              : "text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-200"
          }`}
          title="More copy options"
        >
          <svg
            className="w-3 h-3"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* Options Dropdown Menu */}
      {menuOpen && (
        <div className="absolute right-0 top-full mt-1 w-56 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-lg py-1 z-50 text-xs text-gray-700 dark:text-gray-200 animate-in fade-in slide-in-from-top-2 duration-150">
          <div className="px-3 py-1 font-semibold text-[10px] uppercase tracking-wider text-gray-400 border-b border-gray-100 dark:border-gray-700/60">
            Copy Options
          </div>

          <button
            type="button"
            onClick={() => copyToClipboard(stripHtml(answer || content), "Copied Answer!")}
            className="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-between transition-colors"
          >
            <span>📋 Copy Answer Only (Plain Text)</span>
          </button>

          <button
            type="button"
            onClick={() => copyToClipboard(answer || content, "Copied Markdown!")}
            className="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-between transition-colors"
          >
            <span>📝 Copy Answer (Markdown)</span>
          </button>

          {hasThinking && (
            <button
              type="button"
              onClick={() =>
                copyToClipboard(
                  `Thought process:\n${thinking}\n\nAnswer:\n${stripHtml(answer || "")}`,
                  "Copied with Thoughts!",
                )
              }
              className="w-full text-left px-3 py-2 hover:bg-purple-50 dark:hover:bg-purple-950/40 text-purple-900 dark:text-purple-300 flex items-center justify-between transition-colors"
            >
              <span>🧠 Copy with Thought Process</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => copyToClipboard(content, "Copied Raw!")}
            className="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 flex items-center justify-between transition-colors border-t border-gray-100 dark:border-gray-700/60"
          >
            <span>⚡ Copy Raw Message</span>
          </button>
        </div>
      )}
    </div>
  );
}
