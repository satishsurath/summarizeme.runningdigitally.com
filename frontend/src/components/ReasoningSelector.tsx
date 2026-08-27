"use client";

import type { ReasoningEffort } from "../types/models";

interface ReasoningSelectorProps {
  value: ReasoningEffort;
  onChange: (effort: ReasoningEffort) => void;
  disabled?: boolean;
}

const EFFORT_OPTIONS: { id: ReasoningEffort; label: string; description: string; badge: string }[] = [
  {
    id: "disabled",
    label: "Disabled",
    description: "Fastest response. Standard direct generation without thought traces.",
    badge: "Fastest",
  },
  {
    id: "low",
    label: "Low",
    description: "Brief planning and step structuring before generation.",
    badge: "~1K tokens",
  },
  {
    id: "medium",
    label: "Medium",
    description: "Balanced deep reasoning, citation verification, and quote extraction.",
    badge: "Recommended",
  },
  {
    id: "xhigh",
    label: "Extended High",
    description: "Maximum reasoning depth for complex technical architectures and proofs.",
    badge: "Deepest",
  },
];

export function ReasoningSelector({ value, onChange, disabled = false }: ReasoningSelectorProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
          <span>🧠</span>
          <span>Reasoning Effort Level</span>
        </label>
        <span className="text-[11px] text-slate-400 dark:text-slate-500">Controls Qwen3.8 internal CoT depth</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {EFFORT_OPTIONS.map((opt) => {
          const isSelected = value === opt.id;
          return (
            <button
              key={opt.id}
              type="button"
              disabled={disabled}
              onClick={() => onChange(opt.id)}
              className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between gap-1.5 ${
                isSelected
                  ? "border-purple-500 bg-purple-50/70 dark:bg-purple-950/40 text-purple-900 dark:text-purple-100 shadow-xs ring-1 ring-purple-400"
                  : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-700"
              } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
              title={opt.description}
            >
              <div className="flex items-center justify-between w-full">
                <span className="text-xs font-bold">{opt.label}</span>
                <span
                  className={`text-[9px] px-1.5 py-0.2 rounded font-semibold ${
                    isSelected
                      ? "bg-purple-200 dark:bg-purple-800 text-purple-900 dark:text-purple-100"
                      : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400"
                  }`}
                >
                  {opt.badge}
                </span>
              </div>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 line-clamp-2 leading-tight">
                {opt.description}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
