/**
 * Videos page — paginated video list with filtering, sorting, selection, summarization.
 * Replaces templates/videos.html
 */

"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import Image from "next/image";
import {
  listVideos,
  summarizeVideos,
  getTaskStatus,
  listModels,
  cancelJob,
  retryJob,
  type Video,
  type ModelInfo,
  type TaskStatus,
} from "@/lib/api";

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
  const hasSummary = video.summaries_v2 && video.summaries_v2.length > 0;

  return (
    <tr className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
      <td className="px-4 py-3">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggle(video.video_id)}
          className="w-4 h-4 text-blue-500 rounded border-gray-300 focus:ring-blue-500 cursor-pointer"
        />
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <Image
            src={`https://i.ytimg.com/vi/${video.video_id}/mqdefault.jpg`}
            alt={video.title}
            width={80}
            height={45}
            className="rounded object-cover shrink-0"
            unoptimized
          />
          <div>
            <span className="text-gray-900 dark:text-gray-100 font-medium line-clamp-2 text-sm">
              {video.title}
            </span>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {video.upload_date || "Unknown date"}
              </span>
              {hasSummary ? (
                <span className="px-1.5 py-0.2 rounded bg-green-100 dark:bg-green-950 text-green-800 dark:text-green-300 text-[10px] font-semibold">
                  Summarized ({video.summaries_v2[0]?.model_name?.split("/").pop() || "v2"})
                </span>
              ) : (
                <span className="px-1.5 py-0.2 rounded bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 text-[10px] font-semibold">
                  Missing Summary
                </span>
              )}
            </div>
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          <button
            onClick={() => onChat(video.video_id)}
            className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 hover:text-blue-500 transition-colors cursor-pointer"
            title="Chat about this video"
          >
            <ChatIcon className="w-4 h-4" />
          </button>
          <button
            onClick={() => onViewTranscript(video.video_id)}
            className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 hover:text-purple-500 transition-colors cursor-pointer"
            title="View transcript"
          >
            <TranscriptIcon className="w-4 h-4" />
          </button>
          {hasSummary && (
            <button
              onClick={() => onViewSummary(video.summaries_v2[0].id)}
              className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 hover:text-green-500 transition-colors cursor-pointer"
              title="View summary"
            >
              <SummaryIcon className="w-4 h-4" />
            </button>
          )}
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
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState("date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [filter, setFilter] = useState("");
  const [missingSummaryOnly, setMissingSummaryOnly] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  // Summarize Modal State
  const [showSummarizeModal, setShowSummarizeModal] = useState(false);
  const [selectedModel, setSelectedModel] = useState("nemo-qwen3.8-27b-nvfp4");
  const [selectedReasoningEffort, setSelectedReasoningEffort] = useState("medium");
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);

  // Task Progress State
  const [summarizing, setSummarizing] = useState(false);
  const [summarizeTaskId, setSummarizeTaskId] = useState<string | null>(null);
  const [taskProgress, setTaskProgress] = useState<TaskStatus | null>(null);
  const { toasts, show: showToast } = useToast();

  const pageSize = 50;

  useEffect(() => {
    listModels()
      .then((res) => {
        if (res.models && res.models.length > 0) {
          setAvailableModels(res.models);
          const def = res.models.find((m) => m.is_default);
          if (def) setSelectedModel(def.model_id);
        }
      })
      .catch(() => { /* fallback */ });
  }, []);

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
      // silent
    } finally {
      setLoading(false);
    }
  }, [channelName, page, pageSize, sortKey, sortDir, filter]);

  useEffect(() => {
    loadVideos();
  }, [loadVideos]);

  // Poll summarize job status
  useEffect(() => {
    if (!summarizing || !summarizeTaskId) return;
    const interval = setInterval(async () => {
      try {
        const status = await getTaskStatus(summarizeTaskId);
        setTaskProgress(status);
        if (status.status === "completed" || status.status === "failed" || status.status === "cancelled") {
          setSummarizing(false);
          loadVideos();
          if (status.status === "completed") {
            showToast("Summarization completed!", "success");
          } else if (status.status === "failed") {
            showToast("Summarization failed.", "error");
          }
        }
      } catch {
        /* ignore */
      }
    }, 2500);
    return () => clearInterval(interval);
  }, [summarizing, summarizeTaskId, loadVideos, showToast]);

  const displayedVideos = useMemo(() => {
    if (!missingSummaryOnly) return videos;
    return videos.filter((v) => !v.summaries_v2 || v.summaries_v2.length === 0);
  }, [videos, missingSummaryOnly]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        if (next.size >= 100) {
          showToast("Maximum 100 videos per batch.", "info");
          return prev;
        }
        next.add(id);
      }
      return next;
    });
  };

  const selectAllCurrentPage = () => {
    if (selected.size >= displayedVideos.length) {
      setSelected(new Set());
    } else {
      const newSet = new Set(selected);
      for (const v of displayedVideos) {
        if (newSet.size >= 100) break;
        newSet.add(v.video_id);
      }
      setSelected(newSet);
    }
  };

  const selectMissingCurrentPage = () => {
    const unsummarized = displayedVideos.filter((v) => !v.summaries_v2 || v.summaries_v2.length === 0);
    const newSet = new Set(selected);
    for (const v of unsummarized) {
      if (newSet.size >= 100) break;
      newSet.add(v.video_id);
    }
    setSelected(newSet);
  };

  const handleStartBatch = async () => {
    const ids = Array.from(selected);
    if (ids.length === 0) {
      showToast("No videos selected", "error");
      return;
    }
    setShowSummarizeModal(false);
    setSummarizing(true);
    setTaskProgress({ status: "pending", processed: 0, total: ids.length, errors: [] });
    try {
      const res = await summarizeVideos(channelName, ids, selectedModel, selectedReasoningEffort);
      if (res.task_id) {
        showToast(`Summarization started (${ids.length} videos).`, "success");
        setSelected(new Set());
        setSummarizeTaskId(res.task_id);
      } else {
        showToast(res.message || "Summarization failed", "error");
        setSummarizing(false);
      }
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Summarization failed", "error");
      setSummarizing(false);
    }
  };

  const handleCancelJob = async () => {
    if (!summarizeTaskId) return;
    try {
      await cancelJob(summarizeTaskId);
      showToast("Job cancellation requested", "info");
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Failed to cancel job", "error");
    }
  };

  const handleRetryJob = async () => {
    if (!summarizeTaskId) return;
    try {
      await retryJob(summarizeTaskId);
      showToast("Retrying failed items", "info");
      setSummarizing(true);
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Failed to retry job", "error");
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-1">
            {channelName}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {total} total videos in playlist
          </p>
        </div>
        <a
          href={`/chat/channel/${encodeURIComponent(channelName)}`}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-sm font-semibold shadow-md transition-colors"
        >
          <ChatIcon className="w-4 h-4" />
          Chat with Channel
        </a>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6 bg-white dark:bg-gray-800 p-4 rounded-xl shadow-xs border border-gray-200 dark:border-gray-700">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search filter */}
          <input
            type="text"
            value={filter}
            onChange={(e) => { setFilter(e.target.value); setPage(1); }}
            placeholder="Filter by title..."
            className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm w-56 focus:ring-2 focus:ring-blue-500"
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
            className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm"
          >
            <option value="title-asc">Title A-Z</option>
            <option value="title-desc">Title Z-A</option>
            <option value="date-asc">Date ↑</option>
            <option value="date-desc">Date ↓</option>
          </select>

          {/* Missing Summary toggle */}
          <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={missingSummaryOnly}
              onChange={(e) => setMissingSummaryOnly(e.target.checked)}
              className="w-4 h-4 text-amber-500 rounded border-gray-300 focus:ring-amber-500 cursor-pointer"
            />
            <span>Missing Summary Only</span>
          </label>
        </div>

        {/* Bulk select and Summarize buttons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={selectAllCurrentPage}
            className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-xs font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors cursor-pointer"
          >
            {selected.size > 0 ? `Clear (${selected.size})` : "Select Page"}
          </button>
          <button
            type="button"
            onClick={selectMissingCurrentPage}
            className="px-3 py-1.5 rounded-lg border border-amber-300 dark:border-amber-700 text-xs font-medium text-amber-700 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-950/40 transition-colors cursor-pointer"
          >
            Select Unsummarized
          </button>
          <button
            onClick={() => setShowSummarizeModal(true)}
            disabled={summarizing || selected.size === 0}
            className="px-4 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm transition-colors cursor-pointer"
          >
            {summarizing ? "Processing..." : `Summarize Selected (${selected.size}/100)`}
          </button>
        </div>
      </div>

      {/* Live task progress card */}
      {summarizing && taskProgress && (
        <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded-xl shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4 text-blue-600 dark:text-blue-400" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span className="text-sm font-semibold text-blue-900 dark:text-blue-200">
                Batch Summarization in Progress ({taskProgress.processed} of {taskProgress.total} completed)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCancelJob}
                className="px-2.5 py-1 text-xs font-semibold rounded bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300 hover:bg-red-200 transition-colors cursor-pointer"
              >
                Cancel Job
              </button>
              {taskProgress.errors && taskProgress.errors.length > 0 && (
                <button
                  type="button"
                  onClick={handleRetryJob}
                  className="px-2.5 py-1 text-xs font-semibold rounded bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300 hover:bg-amber-200 transition-colors cursor-pointer"
                >
                  Retry Failed
                </button>
              )}
            </div>
          </div>
          <div className="w-full bg-blue-200 dark:bg-blue-800 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{
                width: `${taskProgress.total > 0 ? Math.min(100, Math.round((taskProgress.processed / taskProgress.total) * 100)) : 0}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* Videos table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg overflow-hidden border border-gray-200 dark:border-gray-700">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
              <th className="px-4 py-3 w-12">
                <input
                  type="checkbox"
                  checked={displayedVideos.length > 0 && selected.size >= displayedVideos.length}
                  onChange={selectAllCurrentPage}
                  className="w-4 h-4 text-blue-500 rounded border-gray-300 focus:ring-blue-500 cursor-pointer"
                />
              </th>
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                Video Title & Info
              </th>
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 w-32">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
            {loading ? (
              <tr>
                <td colSpan={3} className="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
                  Loading videos...
                </td>
              </tr>
            ) : displayedVideos.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
                  No videos found matching current filters.
                </td>
              </tr>
            ) : (
              displayedVideos.map((video) => (
                <VideoRow
                  key={video.video_id}
                  video={video}
                  selected={selected.has(video.video_id)}
                  onToggle={toggleSelect}
                  onChat={(id) => { window.location.href = `/chat/video/${encodeURIComponent(id)}`; }}
                  onViewSummary={(id) => { window.location.href = `/summaries/${id}`; }}
                  onViewTranscript={(id) => { window.location.href = `/transcript/${encodeURIComponent(id)}`; }}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-sm font-medium disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
          >
            ← Previous
          </button>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-sm font-medium disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
          >
            Next →
          </button>
        </div>
      )}

      {/* Summarize configuration modal */}
      {showSummarizeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-5 border border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-bold text-gray-900 dark:text-white">
              Configure Batch Summarization
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Selected <strong>{selected.size}</strong> video(s) for 9-section structured summary generation.
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-gray-700 dark:text-gray-300 mb-1">
                  AI Model
                </label>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm font-mono"
                >
                  {availableModels.length > 0 ? (
                    availableModels.map((m) => (
                      <option key={m.model_id} value={m.model_id}>
                        {m.display_name} ({m.family})
                      </option>
                    ))
                  ) : (
                    <>
                      <option value="nemo-qwen3.8-27b-nvfp4">Qwen 3.8 27B</option>
                      <option value="nemo-qwen3.5-35b-a3b-nvfp4">Qwen 3.5 35B</option>
                    </>
                  )}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-gray-700 dark:text-gray-300 mb-1">
                  Reasoning Effort
                </label>
                <select
                  value={selectedReasoningEffort}
                  onChange={(e) => setSelectedReasoningEffort(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm"
                >
                  <option value="disabled">Disabled (Fastest)</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium (Standard)</option>
                  <option value="xhigh">Extra High (Deep Hierarchical Analysis)</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowSummarizeModal(false)}
                className="px-4 py-2 rounded-lg text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleStartBatch}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-semibold shadow-xs cursor-pointer"
              >
                Start Summarizing ({selected.size})
              </button>
            </div>
          </div>
        </div>
      )}

      <ToastContainer toasts={toasts} />
    </div>
  );
}
