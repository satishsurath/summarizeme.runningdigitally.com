"use client";

import { useState } from "react";
import type { StructuredSummaryV3 } from "../types/summary";
import { ChapterTimeline } from "./ChapterTimeline";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { SummaryNavigation } from "./SummaryNavigation";
import { ThinkingBlock } from "./ThinkingBlock";

interface SummaryViewerProps {
  summary: StructuredSummaryV3;
  title?: string;
  channelName?: string;
  durationSeconds?: number;
  videoId?: string;
  reasoningContent?: string | null;
}

export function SummaryViewer({
  summary,
  title,
  channelName,
  durationSeconds,
  videoId = "",
  reasoningContent,
}: SummaryViewerProps) {
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);

  const handleSelectEvidence = (evidenceId: string) => {
    setSelectedEvidenceId(evidenceId);
    const el = document.getElementById("evidence");
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <div className="flex flex-col lg:flex-row gap-8 max-w-7xl mx-auto px-4 py-6">
      {/* Left Column: Sticky Navigation */}
      <aside className="w-full lg:w-64 shrink-0">
        <SummaryNavigation
          evidenceCount={summary.evidence?.length || 0}
          chapterCount={summary.chapters?.length || 0}
        />
      </aside>

      {/* Right Column: 9-Section Content */}
      <main className="flex-1 space-y-12 min-w-0">
        {/* Title & Metadata Banner */}
        <div className="bg-gradient-to-r from-blue-900 to-indigo-900 text-white rounded-2xl p-6 sm:p-8 shadow-md">
          <div className="flex items-center gap-2 text-xs font-semibold text-blue-200 uppercase tracking-wider mb-2">
            <span>Video Architecture Analysis</span>
            {channelName && (
              <>
                <span>•</span>
                <span>{channelName}</span>
              </>
            )}
          </div>
          <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight mb-4 leading-snug">
            {title || summary.main_thesis?.statement || "Structured Video Summary"}
          </h1>
          <div className="flex flex-wrap items-center gap-4 text-xs text-blue-200">
            {durationSeconds ? (
              <span>⏱️ Duration: {Math.floor(durationSeconds / 60)} mins</span>
            ) : null}
            <span>🔍 Citations: {summary.evidence?.length || 0} excerpts</span>
            <span>✨ Schema: v{summary.schema_version}</span>
          </div>
        </div>

        {/* 1. Executive Overview */}
        <section id="overview" className="scroll-mt-24 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
            <span className="text-xl">📋</span>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">1. Executive Overview</h2>
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-2xs space-y-4">
            {summary.executive_overview?.text && (
              <div>
                <p className="text-sm text-slate-800 dark:text-slate-200 font-medium leading-relaxed">
                  {summary.executive_overview.text}
                </p>
                {summary.executive_overview.evidence_ids && summary.executive_overview.evidence_ids.length > 0 && (
                  <div className="flex items-center gap-1.5 pt-3 border-t border-slate-100 dark:border-slate-800">
                    <span className="text-[10px] text-slate-400">Evidence:</span>
                    {summary.executive_overview.evidence_ids.map((eid: string) => (
                      <button
                        key={eid}
                        type="button"
                        onClick={() => handleSelectEvidence(eid)}
                        className="px-1.5 py-0.2 text-[10px] font-mono font-semibold rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 hover:bg-amber-200 transition-colors cursor-pointer"
                      >
                        {eid}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        {/* 2. Main Thesis & Key Topics */}
        <section id="topics" className="scroll-mt-24 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
            <span className="text-xl">💡</span>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">2. Main Thesis & Key Topics</h2>
          </div>

          {summary.main_thesis?.statement && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xs">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1">
                Core Thesis
              </h3>
              <p className="text-sm text-slate-800 dark:text-slate-200 font-medium leading-relaxed">
                {summary.main_thesis.statement}
              </p>
              {summary.main_thesis.evidence_ids && summary.main_thesis.evidence_ids.length > 0 && (
                <div className="flex items-center gap-1.5 pt-2 mt-2 border-t border-slate-100 dark:border-slate-800">
                  <span className="text-[10px] text-slate-400">Evidence:</span>
                  {summary.main_thesis.evidence_ids.map((eid: string) => (
                    <button
                      key={eid}
                      type="button"
                      onClick={() => handleSelectEvidence(eid)}
                      className="px-1.5 py-0.2 text-[10px] font-mono font-semibold rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 hover:bg-amber-200 transition-colors cursor-pointer"
                    >
                      {eid}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {summary.topics && summary.topics.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {summary.topics.map((topic, idx: number) => (
                <div
                  key={idx}
                  className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xs flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{topic.topic}</h3>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                          topic.importance === "high"
                            ? "bg-rose-100 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300"
                            : topic.importance === "medium"
                              ? "bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300"
                              : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                        }`}
                      >
                        {topic.importance}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed mb-3">
                      {topic.summary}
                    </p>
                  </div>

                  {topic.evidence_ids && topic.evidence_ids.length > 0 && (
                    <div className="flex items-center gap-1.5 pt-2 border-t border-slate-100 dark:border-slate-800">
                      <span className="text-[10px] text-slate-400">Evidence:</span>
                      {topic.evidence_ids.map((eid: string) => (
                        <button
                          key={eid}
                          type="button"
                          onClick={() => handleSelectEvidence(eid)}
                          className="px-1.5 py-0.2 text-[10px] font-mono font-semibold rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 hover:bg-amber-200 transition-colors cursor-pointer"
                        >
                          {eid}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* 3. Chapter Timeline */}
        <section id="chapters" className="scroll-mt-24 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
            <span className="text-xl">⏱️</span>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">3. Chapter Breakdown</h2>
          </div>

          <ChapterTimeline
            videoId={videoId}
            chapters={summary.chapters || []}
            onSelectEvidence={handleSelectEvidence}
          />
        </section>

        {/* 4. Technical Details & Important Facts */}
        <section id="details" className="scroll-mt-24 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
            <span className="text-xl">⚙️</span>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">4. Technical Details & Facts</h2>
          </div>

          {summary.important_details && summary.important_details.length > 0 && (
            <div className="space-y-3">
              {summary.important_details.map((detail, idx: number) => (
                <div
                  key={idx}
                  className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xs"
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                      {detail.speaker ? `Speaker: ${detail.speaker}` : `Detail #${idx + 1}`}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 uppercase">
                      {detail.classification}
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap mb-2">
                    {detail.statement}
                  </p>
                  {detail.evidence_ids && detail.evidence_ids.length > 0 && (
                    <div className="flex items-center gap-1.5 pt-2 border-t border-slate-100 dark:border-slate-800">
                      <span className="text-[10px] text-slate-400">Cited:</span>
                      {detail.evidence_ids.map((eid: string) => (
                        <button
                          key={eid}
                          type="button"
                          onClick={() => handleSelectEvidence(eid)}
                          className="px-1.5 py-0.2 text-[10px] font-mono font-semibold rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 hover:bg-amber-200 transition-colors cursor-pointer"
                        >
                          {eid}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* 5. Decisions & Recommendations */}
        <section id="recommendations" className="scroll-mt-24 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
            <span className="text-xl">🎯</span>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">5. Decisions & Recommendations</h2>
          </div>

          <div className="space-y-4">
            {/* Decisions */}
            {summary.decisions && summary.decisions.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  Decisions
                </h3>
                {summary.decisions.map((dec, idx: number) => (
                  <div
                    key={idx}
                    className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xs"
                  >
                    <p className="text-xs font-bold text-slate-900 dark:text-slate-100">{dec.decision}</p>
                    {dec.rationale && (
                      <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 italic">
                        Rationale: {dec.rationale}
                      </p>
                    )}
                    {dec.evidence_ids && dec.evidence_ids.length > 0 && (
                      <div className="flex items-center gap-1.5 pt-2 mt-2 border-t border-slate-100 dark:border-slate-800">
                        <span className="text-[10px] text-slate-400">Cited:</span>
                        {dec.evidence_ids.map((eid: string) => (
                          <button
                            key={eid}
                            type="button"
                            onClick={() => handleSelectEvidence(eid)}
                            className="px-1.5 py-0.2 text-[10px] font-mono font-semibold rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 hover:bg-amber-200 transition-colors cursor-pointer"
                          >
                            {eid}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Recommendations */}
            {summary.recommendations && summary.recommendations.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  Recommendations
                </h3>
                {summary.recommendations.map((rec, idx: number) => (
                  <div
                    key={idx}
                    className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xs"
                  >
                    <p className="text-xs font-bold text-slate-900 dark:text-slate-100">{rec.recommendation}</p>
                    {rec.target_audience && (
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                        Target Audience: {rec.target_audience}
                      </p>
                    )}
                    {rec.evidence_ids && rec.evidence_ids.length > 0 && (
                      <div className="flex items-center gap-1.5 pt-2 mt-2 border-t border-slate-100 dark:border-slate-800">
                        <span className="text-[10px] text-slate-400">Cited:</span>
                        {rec.evidence_ids.map((eid: string) => (
                          <button
                            key={eid}
                            type="button"
                            onClick={() => handleSelectEvidence(eid)}
                            className="px-1.5 py-0.2 text-[10px] font-mono font-semibold rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 hover:bg-amber-200 transition-colors cursor-pointer"
                          >
                            {eid}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Action Items */}
            {summary.action_items && summary.action_items.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  Action Items
                </h3>
                {summary.action_items.map((item, idx: number) => (
                  <div
                    key={idx}
                    className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xs flex items-center justify-between"
                  >
                    <div>
                      <p className="text-xs font-semibold text-slate-900 dark:text-slate-100">{item.action}</p>
                      {item.owner && (
                        <span className="text-[11px] text-slate-500 dark:text-slate-400">Owner: {item.owner}</span>
                      )}
                    </div>
                    {item.due_date && (
                      <span className="text-[10px] font-mono bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded text-slate-600 dark:text-slate-400">
                        {item.due_date}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* 6. Glossary & Terminology */}
        {summary.glossary && summary.glossary.length > 0 && (
          <section id="glossary" className="scroll-mt-24 space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
              <span className="text-xl">📖</span>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">6. Glossary & Definitions</h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {summary.glossary.map((g, idx: number) => (
                <div
                  key={idx}
                  className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3.5 shadow-2xs"
                >
                  <div className="text-xs font-bold text-slate-900 dark:text-slate-100 mb-1">{g.term}</div>
                  <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed mb-1.5">
                    {g.definition}
                  </p>
                  {g.evidence_ids && g.evidence_ids.length > 0 && (
                    <div className="flex items-center gap-1 mt-1">
                      <span className="text-[10px] text-slate-400">Cited:</span>
                      {g.evidence_ids.map((eid: string) => (
                        <button
                          key={eid}
                          type="button"
                          onClick={() => handleSelectEvidence(eid)}
                          className="px-1 py-0.2 text-[9px] font-mono rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 hover:bg-amber-200 cursor-pointer"
                        >
                          {eid}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 7. Open Questions & Caveats */}
        {((summary.open_questions && summary.open_questions.length > 0) ||
          (summary.caveats && summary.caveats.length > 0)) && (
          <section id="caveats" className="scroll-mt-24 space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
              <span className="text-xl">⚠️</span>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">7. Caveats & Open Questions</h2>
            </div>

            <div className="space-y-3">
              {summary.caveats?.map((cav, idx: number) => (
                <div
                  key={`cav-${idx}`}
                  className="p-3.5 bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 rounded-xl text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2.5"
                >
                  <span className="text-amber-600 shrink-0 font-bold">⚠️</span>
                  <div className="flex-1">
                    <span>{cav.statement}</span>
                    {cav.evidence_ids && cav.evidence_ids.length > 0 && (
                      <div className="flex items-center gap-1 mt-1.5">
                        <span className="text-[10px] text-amber-700 dark:text-amber-400">Cited:</span>
                        {cav.evidence_ids.map((eid: string) => (
                          <button
                            key={eid}
                            type="button"
                            onClick={() => handleSelectEvidence(eid)}
                            className="px-1 py-0.2 text-[9px] font-mono font-semibold rounded bg-amber-200 dark:bg-amber-900/80 text-amber-900 dark:text-amber-100 hover:bg-amber-300 transition-colors cursor-pointer"
                          >
                            {eid}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {summary.open_questions?.map((q, idx: number) => (
                <div
                  key={`q-${idx}`}
                  className="p-3.5 bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/40 rounded-xl text-xs text-blue-900 dark:text-blue-200 flex items-start gap-2.5"
                >
                  <span className="text-blue-600 shrink-0 font-bold">❓</span>
                  <div className="flex-1">
                    <span>{q.question}</span>
                    {q.evidence_ids && q.evidence_ids.length > 0 && (
                      <div className="flex items-center gap-1 mt-1.5">
                        <span className="text-[10px] text-blue-700 dark:text-blue-400">Cited:</span>
                        {q.evidence_ids.map((eid: string) => (
                          <button
                            key={eid}
                            type="button"
                            onClick={() => handleSelectEvidence(eid)}
                            className="px-1 py-0.2 text-[9px] font-mono font-semibold rounded bg-blue-200 dark:bg-blue-900/80 text-blue-900 dark:text-blue-100 hover:bg-blue-300 transition-colors cursor-pointer"
                          >
                            {eid}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 8. Evidence Drawer */}
        <section id="evidence" className="scroll-mt-24 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
            <span className="text-xl">🔍</span>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">8. Cited Evidence Repository</h2>
          </div>

          <EvidenceDrawer
            evidence={summary.evidence || []}
            selectedEvidenceId={selectedEvidenceId}
          />
        </section>

        {/* 9. Model Reasoning */}
        {reasoningContent && (
          <section id="reasoning" className="scroll-mt-24 space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
              <span className="text-xl">🧠</span>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">9. Model Thought Process</h2>
            </div>

            <ThinkingBlock thinking={reasoningContent} />
          </section>
        )}
      </main>
    </div>
  );
}
