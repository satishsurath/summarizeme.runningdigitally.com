/**
 * Transcript page — searchable, timestamped transcript.
 * Replaces templates/transcript.html
 */

"use client";

import { useState, useMemo, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getTranscript } from "@/lib/api";

// ---------------------------------------------------------------------------
// Icons (inline SVGs)
// ---------------------------------------------------------------------------

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function TranscriptPage() {
  const params = useParams();
  const videoId = params.videoId as string;
  const [transcript, setTranscript] = useState("");
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    getTranscript(videoId)
      .then((res) => {
        if (res.status === "ok") {
          setTitle(res.title);
          setTranscript(res.transcript);
        }
      })
      .catch(() => { /* silent */ })
      .finally(() => setLoading(false));
  }, [videoId]);

  // The backend only provides transcript_no_ts (no timing data), so segments
  // are plain text chunks used for search — no timestamps are shown or exported.
  const segments = useMemo(() => {
    if (!transcript) return [];
    const chunks: string[] = [];
    const maxChunkSize = 3000;
    let offset = 0;
    while (offset < transcript.length) {
      const end = Math.min(offset + maxChunkSize, transcript.length);
      let breakPoint = transcript.lastIndexOf(". ", end);
      if (breakPoint < offset) breakPoint = end;
      else breakPoint += 2;
      const text = transcript.slice(offset, breakPoint).trim();
      if (text) chunks.push(text);
      offset = breakPoint;
    }
    return chunks;
  }, [transcript]);


  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return segments;
    const q = searchQuery.toLowerCase();
    return segments.filter((s) => s.toLowerCase().includes(q));
  }, [searchQuery, segments]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(transcript);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };

  const handleDownload = () => {
    const blob = new Blob([transcript], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `transcript-${videoId}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8 text-center text-gray-500 dark:text-gray-400">
        Loading transcript...
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <Link
          href="/"
          className="text-sm text-gray-500 dark:text-gray-400 hover:text-blue-500 transition-colors"
        >
          ← Back to Home
        </Link>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 hover:text-blue-500 transition-colors"
            title="Copy"
          >
            <CopyIcon className="w-4 h-4" />
          </button>
          <button
            onClick={handleDownload}
            className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 hover:text-blue-500 transition-colors"
            title="Download"
          >
            <DownloadIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
        {title || "Transcript"}
      </h1>

      {/* Search */}
      <div className="relative mb-6">
        <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search transcript..."
          className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            ✕
          </button>
        )}
      </div>

      {/* Results count */}
      {searchQuery && (
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
          {filtered.length} of {segments.length} segments match
        </p>
      )}

      {/* Segments */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg divide-y divide-gray-200 dark:divide-gray-700">
        {filtered.map((segment, index) => (
          <div key={index} className="px-6 py-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
              {searchQuery ? (
                <span>
                  {segment.split(new RegExp(`(${searchQuery.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi")).map((part, i) =>
                    part.toLowerCase() === searchQuery.toLowerCase() ? (
                      <mark key={i} className="bg-yellow-200 dark:bg-yellow-700 rounded px-0.5">{part}</mark>
                    ) : (
                      part
                    )
                  )}
                </span>
              ) : (
                segment
              )}
            </p>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
            No matches found.
          </div>
        )}
      </div>

      {copied && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 bg-green-500 text-white rounded-lg text-sm shadow-lg">
          Copied to clipboard!
        </div>
      )}
    </div>
  );
}
