"use client";

import { useState, useMemo, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getTranscript, type TranscriptSegment } from "@/lib/api";

function formatSeconds(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  const h = Math.floor(m / 60);
  if (h > 0) {
    const remM = m % 60;
    return `${h}:${remM.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }
  return `${m}:${s.toString().padStart(2, "0")}`;
}

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

function PlayIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5 3 19 12 5 21 5 3" />
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
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
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
          if (res.segments && res.segments.length > 0) {
            setSegments(res.segments);
          }
        }
      })
      .catch(() => { /* silent */ })
      .finally(() => setLoading(false));
  }, [videoId]);

  // Fallback chunking if no fine-grained segments in DB
  const displaySegments: TranscriptSegment[] = useMemo(() => {
    if (segments.length > 0) return segments;
    if (!transcript) return [];
    const chunks: TranscriptSegment[] = [];
    const maxChunkSize = 2500;
    let offset = 0;
    let idx = 0;
    while (offset < transcript.length) {
      const end = Math.min(offset + maxChunkSize, transcript.length);
      let breakPoint = transcript.lastIndexOf(". ", end);
      if (breakPoint < offset) breakPoint = end;
      else breakPoint += 2;
      const text = transcript.slice(offset, breakPoint).trim();
      if (text) {
        chunks.push({
          segment_index: idx++,
          start_seconds: 0,
          end_seconds: 0,
          text,
          youtube_url: `https://www.youtube.com/watch?v=${videoId}`,
        });
      }
      offset = breakPoint;
    }
    return chunks;
  }, [segments, transcript, videoId]);

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return displaySegments;
    const q = searchQuery.toLowerCase();
    return displaySegments.filter((s) => s.text.toLowerCase().includes(q) || (s.speaker && s.speaker.toLowerCase().includes(q)));
  }, [searchQuery, displaySegments]);

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
      <div className="max-w-5xl mx-auto px-4 py-8 text-center text-gray-500 dark:text-gray-400">
        Loading transcript...
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
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

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          {title || "Transcript"}
        </h1>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          {segments.length > 0 ? `${segments.length} timestamped segments` : "Full raw transcript"} · Video ID: {videoId}
        </p>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search transcript by keywords, timestamps, or speaker..."
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
          {filtered.length} of {displaySegments.length} segments match
        </p>
      )}

      {/* Segments list */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md border border-gray-200 dark:border-gray-700 divide-y divide-gray-100 dark:divide-gray-700/60">
        {filtered.map((segment) => (
          <div key={segment.segment_index} className="p-4 sm:p-5 hover:bg-gray-50 dark:hover:bg-gray-700/40 transition-colors flex flex-col sm:flex-row gap-3 sm:gap-4 items-start">
            {segment.start_seconds > 0 || segments.length > 0 ? (
              <div className="shrink-0 flex items-center gap-1.5">
                <a
                  href={segment.youtube_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-2 py-1 rounded bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 text-xs font-mono font-semibold hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors"
                  title="Jump to video timestamp on YouTube"
                >
                  <PlayIcon className="w-2.5 h-2.5" />
                  {formatSeconds(segment.start_seconds)}
                </a>
              </div>
            ) : null}

            <div className="flex-1 min-w-0">
              {segment.speaker && (
                <span className="inline-block text-[11px] font-semibold uppercase tracking-wider text-purple-600 dark:text-purple-400 mb-1 mr-2">
                  [{segment.speaker}]
                </span>
              )}
              <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed font-sans">
                {searchQuery ? (
                  <span>
                    {segment.text.split(new RegExp(`(${searchQuery.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi")).map((part, i) =>
                      part.toLowerCase() === searchQuery.toLowerCase() ? (
                        <mark key={i} className="bg-yellow-200 dark:bg-yellow-700 text-gray-900 dark:text-white rounded px-0.5">{part}</mark>
                      ) : (
                        part
                      )
                    )}
                  </span>
                ) : (
                  segment.text
                )}
              </p>
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
            No matches found for &quot;{searchQuery}&quot;.
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
