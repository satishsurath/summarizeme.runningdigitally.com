/**
 * Videos page — paginated video list with filtering, sorting, selection, summarization.
 * Replaces templates/videos.html
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { listVideos, summarizeVideos, listActiveTasks } from "@/lib/api";
import type { Video, TaskInfo } from "@/lib/api";

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function ChatIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function SummaryIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  );
}

function TranscriptIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

interface Toast {
  id: number;
  message: string;
  type: "success" | "error" | "info";
}

let toastId = 0;

function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const show = useCallback((message: string, type: Toast["type"] = "info") => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  return { toasts, show };
}

function ToastContainer({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`px-4 py-2 rounded-lg shadow-lg text-sm text-white transition-all ${
            t.type === "success"
              ? "bg-green-500"
              : t.type === "error"
                ? "bg-red-500"
                : "bg-blue-500"
          }`}
        >
          {t.message}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Video row
// ---------------------------------------------------------------------------

function VideoRow({
  video,
  selected,
  onToggle,
  onChat,
  onViewSummary,
  onViewTranscript,
}: {
  video: Video;
  selected: boolean;
  onToggle: (id: string) => void;
  onChat: (id: string) => void;
  onViewSummary: (id: number) => void;
  onViewTranscript: (id: string) => void;
}) {
  return (
    <tr className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
      <td className="px-4 py-3">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggle(video.video_id)}
          className="w-4 h-4 text-blue-500 rounded border-gray-300 focus:ring-blue-500"
        />
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <img
            src={`https://img.youtube.com/vi/${video.video_id}/mqdefault.jpg`}
            alt=""
            className="w-16 h-9 rounded object-cover flex-shrink-0"
            loading="lazy"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
          <span className="text-sm text-gray-900 dark:text-gray-100 truncate max-w-md">
            {video.title}
          </span>
        </div>
      </td>
      <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">
        {video.upload_date}
      </td>
      <td className="px-4 py-3 text-sm">
        {video.summaries_v2.length > 0 ? (
          <div className="flex items-center gap-2">
            {video.summaries_v2.map((s) => (
              <button
                key={s.id}
                onClick={() => onViewSummary(s.id)}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors"
              >
                <SummaryIcon className="w-3 h-3" />
                {s.model_name}
              </button>
            ))}
          </div>
        ) : (
          <span className="text-gray-400 text-xs italic">No summaries</span>
        )}
      </td>
      <td className="px-4 py-3 text-sm">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onChat(video.video_id)}
            className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-400 hover:text-purple-500 transition-colors"
            title="Chat"
          >
            <ChatIcon className="w-4 h-4" />
          </button>
          <button
            onClick={() => onViewTranscript(video.video_id)}
            className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-400 hover:text-blue-500 transition-colors"
            title="Transcript"
          >
            <TranscriptIcon className="w-4 h-4" />
          </button>
        </div>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function VideosPage() {
  const params = useParams();
  const channelName = params.channel as string;

  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");
  const [sortKey, setSortKey] = useState("title");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [summarizing, setSummarizing] = useState(false);
  const [taskStatus, setTaskStatus] = useState<{ status: string; processed: number; total: number } | null>(null);
  const { toasts, show: showToast } = useToast();

  const pageSize = 50;

  const loadVideos = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listVideos(channelName, {
        page,
        page_size: pageSize,
        sort_by: sortKey,
        sort_order: sortDir,
        filter: filter || undefined,
      });
      setVideos(data.videos);
      setTotal(data.total);
    } catch {
      // silent — user sees loading state
    } finally {
      setLoading(false);
    }
  }, [channelName, page, pageSize, sortKey, sortDir, filter]);

  useEffect(() => {
    loadVideos();
  }, [loadVideos]);

  // Poll task status if summarizing
  useEffect(() => {
    if (!summarizing) return;
    const interval = setInterval(async () => {
      try {
        const tasks = await listActiveTasks();
        const active = tasks.filter((t) => t.status === "in_progress" || t.status === "pending");
        if (active.length === 0) {
          setSummarizing(false);
          setTaskStatus(null);
          loadVideos();
        }
      } catch {
        /* ignore */
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [summarizing, loadVideos]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (selected.size === videos.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(videos.map((v) => v.video_id)));
    }
  };

  const handleSummarize = async () => {
    const ids = Array.from(selected);
    if (ids.length === 0) {
      showToast("No videos selected", "error");
      return;
    }
    setSummarizing(true);
    try {
      const res = await summarizeVideos(channelName, ids);
      if (res.task_id) {
        showToast(`Summarization started. Task: ${res.task_id}`, "success");
        setSelected(new Set());
        setTaskStatus({ status: "in_progress", processed: 0, total: ids.length });
      } else {
        showToast(res.message || "Summarization failed", "error");
        setSummarizing(false);
      }
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Summarization failed", "error");
      setSummarizing(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-1">
          {channelName}
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {total} videos
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        {/* Filter */}
        <input
          type="text"
          value={filter}
          onChange={(e) => { setFilter(e.target.value); setPage(1); }}
          placeholder="Filter by title..."
          className="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm w-64 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />

        {/* Sort */}
        <select
          value={`${sortKey}-${sortDir}`}
          onChange={(e) => {
            const [by, order] = e.target.value.split("-") as [string, "asc" | "desc"];
            setSortKey(by);
            setSortDir(order);
            setPage(1);
          }}
          className="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm focus:ring-2 focus:ring-blue-500"
        >
          <option value="title-asc">Title A-Z</option>
          <option value="title-desc">Title Z-A</option>
          <option value="date-asc">Date ↑</option>
          <option value="date-desc">Date ↓</option>
        </select>

        {/* Summarize */}
        <button
          onClick={handleSummarize}
          disabled={summarizing || selected.size === 0}
          className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm transition-colors"
        >
          {summarizing ? "Processing..." : `Summarize (${selected.size})`}
        </button>
      </div>

      {/* Task progress */}
      {summarizing && (
        <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <div className="flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Summarization in progress...
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={selected.size === videos.length && videos.length > 0}
                    onChange={selectAll}
                    className="w-4 h-4 text-blue-500 rounded border-gray-300 focus:ring-blue-500"
                  />
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Title</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Date</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Summaries</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                    <div className="animate-pulse">Loading...</div>
                  </td>
                </tr>
              ) : videos.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                    No videos found.
                  </td>
                </tr>
              ) : (
                videos.map((v) => (
                  <VideoRow
                    key={v.video_id}
                    video={v}
                    selected={selected.has(v.video_id)}
                    onToggle={toggleSelect}
                    onChat={(id) => window.open(`/chat/video/${id}`, "_blank")}
                    onViewSummary={(id) => window.open(`/summaries/${id}`, "_blank")}
                    onViewTranscript={(id) => window.open(`/transcript/${id}`, "_blank")}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 dark:border-gray-700">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              Previous
            </button>
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              Next
            </button>
          </div>
        )}
      </div>

      <ToastContainer toasts={toasts} />
    </div>
  );
}
