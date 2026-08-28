"use client";

import { useEffect, useState } from "react";

export interface NavigationItem {
  id: string;
  label: string;
  count?: number;
  icon?: string;
}

const DEFAULT_SECTIONS: NavigationItem[] = [
  { id: "overview", label: "Executive Overview", icon: "📋" },
  { id: "topics", label: "Key Topics", icon: "💡" },
  { id: "chapters", label: "Chapter Timeline", icon: "⏱️" },
  { id: "details", label: "Technical Details", icon: "⚙️" },
  { id: "recommendations", label: "Recommendations", icon: "🎯" },
  { id: "glossary", label: "Glossary & Terms", icon: "📖" },
  { id: "caveats", label: "Caveats & Constraints", icon: "⚠️" },
  { id: "evidence", label: "Cited Evidence", icon: "🔍" },
  { id: "reasoning", label: "Model Reasoning", icon: "🧠" },
];

interface SummaryNavigationProps {
  activeSection?: string;
  onSelectSection?: (id: string) => void;
  evidenceCount?: number;
  chapterCount?: number;
}

export function SummaryNavigation({
  activeSection: initialActive = "overview",
  onSelectSection,
  evidenceCount,
  chapterCount,
}: SummaryNavigationProps) {
  const [activeId, setActiveId] = useState<string>(initialActive);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
            break;
          }
        }
      },
      { rootMargin: "-20% 0px -70% 0px" },
    );

    for (const section of DEFAULT_SECTIONS) {
      const el = document.getElementById(section.id);
      if (el) observer.observe(el);
    }

    return () => observer.disconnect();
  }, []);

  const handleClick = (id: string) => {
    setActiveId(id);
    if (onSelectSection) {
      onSelectSection(id);
    } else {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  };

  return (
    <nav className="sticky top-20 flex flex-col gap-1 p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xs">
      <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-3 py-1">
        Summary Sections
      </div>

      <div className="flex flex-col gap-0.5">
        {DEFAULT_SECTIONS.map((sec) => {
          const isActive = activeId === sec.id;
          let badge: number | undefined;
          if (sec.id === "evidence") badge = evidenceCount;
          if (sec.id === "chapters") badge = chapterCount;

          return (
            <button
              key={sec.id}
              type="button"
              onClick={() => handleClick(sec.id)}
              className={`flex items-center justify-between px-3 py-2 text-xs font-medium rounded-lg transition-all text-left cursor-pointer ${
                isActive
                  ? "bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 font-semibold shadow-xs"
                  : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-100"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-sm shrink-0">{sec.icon}</span>
                <span className="truncate">{sec.label}</span>
              </div>
              {badge !== undefined && badge > 0 && (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono font-semibold ${
                    isActive
                      ? "bg-blue-200 dark:bg-blue-800 text-blue-900 dark:text-blue-100"
                      : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400"
                  }`}
                >
                  {badge}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
