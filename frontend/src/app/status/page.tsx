/**
 * Status page — real-time task monitoring with filtering and detail modal.
 * Replaces templates/status.html
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { listAllTasks, listActiveTasks } from "@/lib/api";
import type { TaskInfo } from "@/lib/api";

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

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

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
    in_progress: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    completed: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
  };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${
      colors[status] || "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300"
    }`}>
      {status.replace("_", " ")}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Progress bar
// ---------------------------------------------------------------------------

function ProgressBar({ processed, total }: { processed: number; total: number }) {
  const percent = total > 0 ? Math.round((processed / total) * 100) : 0;
  return (
    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
      <div
        className="bg-blue-500 h-2 rounded-full transition-all duration-500"
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail modal
// ---------------------------------------------------------------------------

function TaskDetailModal({
  task,
  onClose,
}: {
  task: TaskInfo;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-lg w-full p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Task Details</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700"
          >
            <XIcon className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Task ID</label>
            <p className="text-sm font-mono text-gray-900 dark:text-gray-100">{task.task_id}</p>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Type</label>
            <p className="text-sm text-gray-900 dark:text-gray-100">{task.task_type}</p>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</label>
            <StatusBadge status={task.status} />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Progress</label>
            <div className="mt-1">
              <ProgressBar processed={task.processed} total={task.total} />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {task.processed} / {task.total}
              </p>
            </div>
          </div>
          {task.errors && task.errors.length > 0 && (
            <div>
              <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Errors</label>
              <ul className="mt-1 space-y-1">
                {task.errors.map((err, i) => (
                  <li key={i} className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded px-2 py-1">
                    {err}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Created</label>
            <p className="text-sm text-gray-900 dark:text-gray-100">
              {task.created_at ? new Date(task.created_at * 1000).toLocaleString() : "N/A"}
            </p>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Updated</label>
            <p className="text-sm text-gray-900 dark:text-gray-100">
              {task.updated_at ? new Date(task.updated_at * 1000).toLocaleString() : "N/A"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function StatusPage() {
  const [tasks, setTasks] = useState<TaskInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [selectedTask, setSelectedTask] = useState<TaskInfo | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadTasks = useCallback(async () => {
    try {
      const [active, all] = await Promise.all([listActiveTasks(), listAllTasks()]);
      // Merge: active tasks take priority
      const merged = new Map<string, TaskInfo>();
      active.forEach((t) => merged.set(t.task_id, t));
      all.forEach((t) => {
        if (!merged.has(t.task_id)) merged.set(t.task_id, t);
      });
      setTasks(Array.from(merged.values()));
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time data fetch; state updates happen inside the async load callback
    loadTasks();
  }, [loadTasks]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(loadTasks, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, loadTasks]);

  const filtered = filter === "all"
    ? tasks
    : tasks.filter((t) => t.status === filter);

  const activeCount = tasks.filter((t) => t.status === "in_progress").length;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Task Status</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              autoRefresh
                ? "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
                : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400"
            }`}
          >
            {autoRefresh ? "Auto-refresh On" : "Auto-refresh Off"}
          </button>
          <button
            onClick={loadTasks}
            className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400"
            title="Refresh"
          >
            <RefreshIcon className={`w-5 h-5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Active tasks banner */}
      {activeCount > 0 && (
        <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300">
          <SpinnerIcon className="w-4 h-4" />
          {activeCount} task{activeCount > 1 ? "s" : ""} running
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 mb-4">
        {["all", "pending", "in_progress", "completed", "failed"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-colors ${
              filter === f
                ? "bg-blue-500 text-white"
                : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600"
            }`}
          >
            {f === "all" ? "All" : f.replace("_", " ")}
          </button>
        ))}
      </div>

      {/* Task list */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg divide-y divide-gray-200 dark:divide-gray-700">
        {loading ? (
          <div className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
            Loading...
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
            No tasks found.
          </div>
        ) : (
          filtered.map((task) => (
            <div
              key={task.task_id}
              onClick={() => setSelectedTask(task)}
              className="px-6 py-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <StatusBadge status={task.status} />
                  <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    {task.task_type}
                  </span>
                </div>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {task.updated_at ? new Date(task.updated_at * 1000).toLocaleTimeString() : "N/A"}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <ProgressBar processed={task.processed} total={task.total} />
                </div>
                <span className="text-xs text-gray-500 dark:text-gray-400 shrink-0">
                  {task.processed}/{task.total}
                </span>
              </div>
              {task.errors && task.errors.length > 0 && (
                <p className="text-xs text-red-600 dark:text-red-400 mt-1 truncate">
                  {task.errors[0]}
                </p>
              )}
            </div>
          ))
        )}
      </div>

      {/* Detail modal */}
      {selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          onClose={() => setSelectedTask(null)}
        />
      )}
    </div>
  );
}
