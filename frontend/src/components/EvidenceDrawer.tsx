"use client";

import { useState } from "react";
import type { EvidenceReference } from "../types/summary";

interface EvidenceDrawerProps {
  evidence: EvidenceReference[];
  selectedEvidenceId?: string | null;
  onClose?: () => void;
}

function formatSeconds(sec: number): string {
  const totalSeconds = Math.max(0, Math.floor(sec));
  const mins = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function EvidenceDrawer({
  evidence,
  selectedEvidenceId,
  onClose,
}: EvidenceDrawerProps) {
  const [searchQuery, setSearchQuery] = useState<string>("");

  if (!evidence || evidence.length === 0) {
    return (
      <div className="p-4 text-xs text-slate-400 dark:text-slate-500 italic bg-slate-50 dark:bg-slate-900/50 rounded-lg">
        No evidence excerpts cited in this summary.
      </div>
    );
  }

  const filteredEvidence = evidence.filter((item) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      item.id.toLowerCase().includes(q) ||
      (item.speaker && item.speaker.toLowerCase().includes(q)) ||
      item.excerpt.toLowerCase().includes(q)
    );
  });

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-xs">
      {/* Header with Search */}
      <div className="p-3 bg-slate-50/80 dark:bg-slate-800/40 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm">🔍</span>
          <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
            Cited Evidence Repository ({evidence.length})
          </span>
        </div>

        <div className="flex items-center gap-2 flex-1 max-w-xs">
          <input
            type="text"
            placeholder="Filter citations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-2.5 py-1 text-xs rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 px-1"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Evidence List */}
      <div className="divide-y divide-slate-100 dark:divide-slate-800 max-h-[500px] overflow-y-auto">
        {filteredEvidence.map((item) => {
          const isSelected = selectedEvidenceId === item.id;
          return (
            <div
              key={item.id}
              id={`evidence-${item.id}`}
              className={`p-3.5 transition-colors ${
                isSelected
                  ? "bg-amber-50/70 dark:bg-amber-950/30 border-l-4 border-l-amber-500"
                  : "hover:bg-slate-50/60 dark:hover:bg-slate-800/30"
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 text-xs font-mono font-bold rounded-md bg-amber-100 dark:bg-amber-900/60 text-amber-900 dark:text-amber-200">
                    [{item.id}]
                  </span>
                  {item.speaker && (
                    <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
                      Speaker: <span className="text-slate-900 dark:text-slate-100 font-semibold">{item.speaker}</span>
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
                    ⏱️ {formatSeconds(item.start_seconds)} - {formatSeconds(item.end_seconds)}
                  </span>
                  {item.youtube_url && (
                    <a
                      href={item.youtube_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium inline-flex items-center gap-0.5"
                    >
                      Watch ↗
                    </a>
                  )}
                </div>
              </div>

              {/* Exact Quote */}
              <blockquote className="text-xs text-slate-700 dark:text-slate-300 italic pl-3 border-l-2 border-slate-300 dark:border-slate-700 my-1 leading-relaxed">
                &ldquo;{item.excerpt}&rdquo;
              </blockquote>
            </div>
          );
        })}
      </div>
    </div>
  );
}
