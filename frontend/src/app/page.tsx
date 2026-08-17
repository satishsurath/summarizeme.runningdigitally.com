/**
 * Home page — channel list, search, download form.
 * Replaces templates/index.html
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { listChannels, startChannelDownload } from "@/lib/api";
import type { ChannelMeta } from "@/lib/api";

// ---------------------------------------------------------------------------
// Icons (inline SVGs — replaces icon_data.py)
// ---------------------------------------------------------------------------

function EditIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}

function ChatIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="23 4 23 10 17 10" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  );
}

function YouTubeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Toast notification
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
// Channel row (editable)
// ---------------------------------------------------------------------------

function ChannelRow({
  channel,
  onRename,
  onDelete,
  onRefresh,
}: {
  channel: ChannelMeta;
  onRename: (oldName: string, newName: string) => Promise<void>;
  onDelete: (name: string) => Promise<void>;
  onRefresh: (name: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [newName, setNewName] = useState(channel.folder_name);
  const [loading, setLoading] = useState<string | null>(null);

  const handleRename = async () => {
    if (newName.trim() === channel.folder_name || !newName.trim()) return;
    setLoading("rename");
    try {
      await onRename(channel.folder_name, newName.trim());
      setEditing(false);
    } catch {
      // error handled by caller
    } finally {
      setLoading(null);
    }
  };

  return (
    <li className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 rounded-lg transition-colors">
      {/* Actions */}
      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={() => setEditing(true)}
          disabled={loading !== null}
          className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500 dark:text-gray-400 hover:text-blue-500 disabled:opacity-50"
          title="Rename"
        >
          <EditIcon className="w-4 h-4" />
        </button>
        <button
          onClick={async () => {
            setLoading("refresh");
            try {
              await onRefresh(channel.folder_name);
            } catch {
              /* handled by caller */
            } finally {
              setLoading(null);
            }
          }}
          disabled={loading !== null}
          className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500 dark:text-gray-400 hover:text-green-500 disabled:opacity-50"
          title="Refresh"
        >
          <RefreshIcon className={`w-4 h-4 ${loading === "refresh" ? "animate-spin" : ""}`} />
        </button>
        <button
          onClick={async () => {
            setLoading("delete");
            try {
              await onDelete(channel.folder_name);
            } catch {
              /* handled by caller */
            } finally {
              setLoading(null);
            }
          }}
          disabled={loading !== null}
          className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500 dark:text-gray-400 hover:text-red-500 disabled:opacity-50"
          title="Delete"
        >
          <TrashIcon className="w-4 h-4" />
        </button>
      </div>

      {/* Channel name */}
      {editing ? (
        <input
          type="text"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onBlur={handleRename}
          onKeyDown={(e) => e.key === "Enter" && handleRename()}
          className="flex-1 px-2 py-1 rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          autoFocus
        />
      ) : (
        <a
          href={`/videos/${encodeURIComponent(channel.folder_name)}`}
          className="flex-1 text-gray-900 dark:text-gray-100 hover:text-blue-500 dark:hover:text-blue-400 font-medium text-sm truncate"
        >
          {channel.folder_name}
        </a>
      )}

      {/* Quick links */}
      <div className="flex items-center gap-2 shrink-0">
        <a
          href={`https://www.youtube.com/playlist?list=${channel.original_playlist_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-400 hover:text-red-500"
          title="YouTube"
        >
          <YouTubeIcon className="w-4 h-4" />
        </a>
        <a
          href={`/chat/channel/${encodeURIComponent(channel.folder_name)}`}
          className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-400 hover:text-purple-500"
          title="Chat"
        >
          <ChatIcon className="w-4 h-4" />
        </a>
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function HomePage() {
  const [channels, setChannels] = useState<ChannelMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [channelUrl, setChannelUrl] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const { toasts, show: showToast } = useToast();
  useEffect(() => {
    listChannels()
      .then((data) => setChannels(data))
      .catch(() => { /* silent */ })
      .finally(() => setLoading(false));
  }, []);

  // Download handler
  const handleDownload = async () => {
    if (!channelUrl.trim()) return;
    setDownloading(true);
    try {
      const res = await startChannelDownload(channelUrl.trim());
      if (res.task_id) {
        showToast(`Download started. Task: ${res.task_id}`, "success");
        setChannelUrl("");
      } else {
        showToast(res.message || "Download failed", "error");
      }
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Download failed", "error");
    } finally {
      setDownloading(false);
    }
  };

  // Rename handler
  const handleRename = async (oldName: string, newName: string) => {
    const res = await listChannels();
    const updated = res.map((c) =>
      c.folder_name === oldName ? { ...c, folder_name: newName } : c,
    );
    setChannels(updated);
    showToast(`Renamed to "${newName}"`, "success");
  };

  // Delete handler
  const handleDelete = async (name: string) => {
    if (!confirm(`Delete channel "${name}"?`)) return;
    setChannels((prev) => prev.filter((c) => c.folder_name !== name));
    showToast(`Deleted "${name}"`, "success");
  };

  // Refresh handler
  const handleRefresh = async (name: string) => {
    try {
      const res = await listChannels();
      showToast(`Refreshed "${name}"`, "info");
      setChannels(res);
    } catch {
      showToast(`Failed to refresh "${name}"`, "error");
    }
  };

  // Filtered channels
  const filtered = searchQuery
    ? channels.filter((c) =>
        c.folder_name.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : channels;

  return (
    <div className="max-w-4xl mx-auto">
      {/* Download form */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
          Add a Channel
        </h2>
        <div className="flex gap-3">
          <input
            type="text"
            value={channelUrl}
            onChange={(e) => setChannelUrl(e.target.value)}
            placeholder="https://youtube.com/... or https://youtube.com/@channel"
            className="flex-1 px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            onKeyDown={(e) => e.key === "Enter" && handleDownload()}
          />
          <button
            onClick={handleDownload}
            disabled={downloading || !channelUrl.trim()}
            className="px-6 py-2.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
          >
            {downloading ? "Starting..." : "Download"}
          </button>
        </div>
      </div>

      {/* Channel list */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg overflow-hidden">
        {/* Search */}
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search channels..."
            className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white placeholder-gray-400 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* List */}
        <ul className="divide-y divide-gray-200 dark:divide-gray-700">
          {loading ? (
            <li className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
              Loading...
            </li>
          ) : filtered.length === 0 ? (
            <li className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
              {searchQuery ? "No channels match your search." : "No channels yet. Add one above."}
            </li>
          ) : (
            filtered.map((ch) => (
              <ChannelRow
                key={ch.folder_name}
                channel={ch}
                onRename={handleRename}
                onDelete={handleDelete}
                onRefresh={handleRefresh}
              />
            ))
          )}
        </ul>
      </div>

      <ToastContainer toasts={toasts} />
    </div>
  );
}
