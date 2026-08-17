/**
 * Admin page — channel management with modal forms and inline validation.
 * Replaces templates/admin.html
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { listChannels, renameChannel, deleteChannel, refreshChannel, startChannelDownload } from "@/lib/api";
import type { ChannelMeta } from "@/lib/api";

// ---------------------------------------------------------------------------
// Icons
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

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="23 4 23 10 17 10" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
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
// Modal
// ---------------------------------------------------------------------------

function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700"
          >
            <XIcon className="w-5 h-5 text-gray-500" />
          </button>
        </div>
        <div className="px-6 py-4">{children}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AdminPage() {
  const [channels, setChannels] = useState<ChannelMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [editingChannel, setEditingChannel] = useState<ChannelMeta | null>(null);
  const [deletingChannel, setDeletingChannel] = useState<string | null>(null);
  const [newUrl, setNewUrl] = useState("");
  const [newName, setNewName] = useState("");
  const [addLoading, setAddLoading] = useState(false);
  const [renameLoading, setRenameLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const { toasts, show: showToast } = useToast();

  const loadChannels = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listChannels();
      setChannels(data);
    } catch {
      // silent — user sees loading state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadChannels();
  }, [loadChannels]);

  // Add channel
  const handleAdd = async () => {
    if (!newUrl.trim()) return;
    setAddLoading(true);
    try {
      const res = await startChannelDownload(newUrl.trim());
      if (res.task_id) {
        showToast(`Download started. Task: ${res.task_id}`, "success");
        setNewUrl("");
        setShowAddModal(false);
        loadChannels();
      } else {
        showToast(res.message || "Download failed", "error");
      }
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Download failed", "error");
    } finally {
      setAddLoading(false);
    }
  };

  // Rename channel
  const handleRename = async () => {
    if (!editingChannel || !newName.trim()) return;
    setRenameLoading(true);
    try {
      await renameChannel(editingChannel.folder_name, newName.trim());
      setChannels((prev) =>
        prev.map((c) =>
          c.folder_name === editingChannel.folder_name
            ? { ...c, folder_name: newName.trim() }
            : c,
        ),
      );
      showToast(`Renamed to "${newName.trim()}"`, "success");
      setShowRenameModal(false);
      setEditingChannel(null);
      setNewName("");
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Rename failed", "error");
    } finally {
      setRenameLoading(false);
    }
  };

  // Delete channel
  const handleDelete = async () => {
    if (!deletingChannel) return;
    setDeleteLoading(true);
    try {
      await deleteChannel(deletingChannel);
      setChannels((prev) => prev.filter((c) => c.folder_name !== deletingChannel));
      showToast(`Deleted "${deletingChannel}"`, "success");
      setShowDeleteModal(false);
      setDeletingChannel(null);
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Delete failed", "error");
    } finally {
      setDeleteLoading(false);
    }
  };

  // Refresh channel
  const handleRefresh = async (name: string) => {
    setRefreshing(name);
    try {
      await refreshChannel(name);
      showToast(`Refreshed "${name}"`, "info");
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Refresh failed", "error");
    } finally {
      setRefreshing(null);
    }
  };

  // Validation
  const addValid = newUrl.trim().length > 0;
  const renameValid = newName.trim().length > 0 && newName.trim() !== editingChannel?.folder_name;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Admin</h1>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 font-medium text-sm transition-colors flex items-center gap-2"
        >
          <PlusIcon className="w-4 h-4" />
          Add Channel
        </button>
      </div>

      {/* Channel list */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg divide-y divide-gray-200 dark:divide-gray-700">
        {loading ? (
          <div className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
            Loading...
          </div>
        ) : channels.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
            No channels. Add one to get started.
          </div>
        ) : (
          channels.map((ch) => (
            <div key={ch.folder_name} className="flex items-center gap-4 px-6 py-4">
              <div className="flex-1">
                <a
                  href={`/videos/${encodeURIComponent(ch.folder_name)}`}
                  className="text-gray-900 dark:text-gray-100 font-medium hover:text-blue-500 dark:hover:text-blue-400"
                >
                  {ch.folder_name}
                </a>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  {ch.original_playlist_id}
                </p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => {
                    setEditingChannel(ch);
                    setNewName(ch.folder_name);
                    setShowRenameModal(true);
                  }}
                  className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 hover:text-blue-500 transition-colors"
                  title="Rename"
                >
                  <EditIcon className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleRefresh(ch.folder_name)}
                  disabled={refreshing !== null}
                  className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 hover:text-green-500 transition-colors disabled:opacity-50"
                  title="Refresh"
                >
                  <RefreshIcon className={`w-4 h-4 ${refreshing === ch.folder_name ? "animate-spin" : ""}`} />
                </button>
                <button
                  onClick={() => {
                    setDeletingChannel(ch.folder_name);
                    setShowDeleteModal(true);
                  }}
                  className="p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 hover:text-red-500 transition-colors"
                  title="Delete"
                >
                  <TrashIcon className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Add channel modal */}
      {showAddModal && (
        <Modal title="Add Channel" onClose={() => setShowAddModal(false)}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                YouTube URL
              </label>
              <input
                type="text"
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder="https://youtube.com/playlist?list=... or https://youtube.com/@channel"
                className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                autoFocus
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleAdd}
                disabled={!addValid || addLoading}
                className="px-4 py-2 rounded-lg bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
              >
                {addLoading ? "Starting..." : "Download"}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Rename modal */}
      {showRenameModal && editingChannel && (
        <Modal title="Rename Channel" onClose={() => { setShowRenameModal(false); setEditingChannel(null); }}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Current name
              </label>
              <p className="text-sm text-gray-500 dark:text-gray-400">{editingChannel.folder_name}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                New name
              </label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                autoFocus
              />
              {newName.trim() === editingChannel.folder_name && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Same as current name
                </p>
              )}
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setShowRenameModal(false); setEditingChannel(null); }}
                className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleRename}
                disabled={!renameValid || renameLoading}
                className="px-4 py-2 rounded-lg bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
              >
                {renameLoading ? "Renaming..." : "Rename"}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Delete modal */}
      {showDeleteModal && deletingChannel && (
        <Modal title="Delete Channel" onClose={() => { setShowDeleteModal(false); setDeletingChannel(null); }}>
          <div className="space-y-4">
            <p className="text-sm text-gray-700 dark:text-gray-300">
              Are you sure you want to delete <strong>"{deletingChannel}"</strong>?
              This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setShowDeleteModal(false); setDeletingChannel(null); }}
                className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleteLoading}
                className="px-4 py-2 rounded-lg bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 text-sm"
              >
                {deleteLoading ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </Modal>
      )}

      <ToastContainer toasts={toasts} />
    </div>
  );
}
