"use client";

import type { ChapterSection } from "../types/summary";

interface ChapterTimelineProps {
  videoId: string;
  chapters: ChapterSection[];
  onSelectTimestamp?: (seconds: number) => void;
  onSelectEvidence?: (evidenceId: string) => void;
}

function formatSeconds(sec: number): string {
  const totalSeconds = Math.max(0, Math.floor(sec));
  const hrs = Math.floor(totalSeconds / 3600);
  const mins = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function ChapterTimeline({
  videoId,
  chapters,
  onSelectTimestamp,
  onSelectEvidence,
}: ChapterTimelineProps) {
  if (!chapters || chapters.length === 0) {
    return (
      <div className="p-4 text-xs text-slate-400 dark:text-slate-500 italic bg-slate-50 dark:bg-slate-900/50 rounded-lg">
        No chapter breakdowns generated for this video.
      </div>
    );
  }

  const handleTimestampClick = (startSec: number) => {
    if (onSelectTimestamp) {
      onSelectTimestamp(startSec);
    } else {
      const url = `https://www.youtube.com/watch?v=${videoId}&t=${Math.floor(startSec)}s`;
      window.open(url, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-3 before:bottom-3 before:w-0.5 before:bg-slate-200 dark:before:bg-slate-800">
      {chapters.map((chap, idx) => (
        <div key={idx} className="relative group">
          {/* Timeline Node Dot */}
          <div className="absolute -left-6 top-1.5 w-4 h-4 rounded-full border-2 border-blue-500 bg-white dark:bg-slate-950 group-hover:scale-110 group-hover:bg-blue-500 transition-all flex items-center justify-center">
            <div className="w-1.5 h-1.5 rounded-full bg-blue-500 group-hover:bg-white transition-colors" />
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xs hover:shadow-xs transition-shadow">
            {/* Header / Timestamp */}
            <div className="flex items-center justify-between gap-2 mb-2">
              <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{chap.title}</h4>
              <button
                type="button"
                onClick={() => handleTimestampClick(chap.start_seconds)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono font-medium rounded-md bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors cursor-pointer"
                title={`Jump to ${formatSeconds(chap.start_seconds)}`}
              >
                <span>⏱️</span>
                <span>
                  {formatSeconds(chap.start_seconds)} - {formatSeconds(chap.end_seconds)}
                </span>
                <span className="text-[10px]">↗</span>
              </button>
            </div>

            {/* Bullets */}
            {chap.bullets && chap.bullets.length > 0 && (
              <ul className="space-y-1.5 mb-3">
                {chap.bullets.map((bullet, bIdx) => (
                  <li key={bIdx} className="text-xs text-slate-700 dark:text-slate-300 flex items-start gap-2">
                    <span className="text-blue-500 shrink-0">•</span>
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            )}

            {/* Evidence Citations */}
            {chap.evidence_ids && chap.evidence_ids.length > 0 && (
              <div className="flex items-center gap-1.5 pt-2 border-t border-slate-100 dark:border-slate-800">
                <span className="text-[11px] text-slate-400">Cited Evidence:</span>
                <div className="flex flex-wrap gap-1">
                  {chap.evidence_ids.map((eid) => (
                    <button
                      key={eid}
                      type="button"
                      onClick={() => onSelectEvidence && onSelectEvidence(eid)}
                      className="px-1.5 py-0.5 text-[10px] font-mono font-semibold rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 hover:bg-amber-200 transition-colors cursor-pointer"
                    >
                      {eid}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
