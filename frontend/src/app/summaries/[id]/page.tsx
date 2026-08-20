/**
 * Summary page — tabbed view of summary sections.
 * Replaces templates/summary_v2.html
 */

"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { sanitizeHtml } from "@/lib/sanitize";
import { getTranscript } from "@/lib/api";

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function ShareIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
    </svg>
  );
}
function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SummaryData {
  id: number;
  video_id: string;
  video_title: string;
  model_name: string;
  date_generated: string | null;
  concise_summary: string;
  key_topics: string;
  important_takeaways: string;
  comprehensive_notes: string;
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function SummaryPage() {
  const params = useParams();
  const summaryId = params.id as string;

  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("summary");
  const [copied, setCopied] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [transcriptError, setTranscriptError] = useState<string | null>(null);

  // Fetch summary data
  useEffect(() => {
    const fetchSummary = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/summaries/${summaryId}`);
        if (!res.ok) {
          throw new Error(`Failed to load summary: ${res.statusText}`);
        }
        const data = await res.json();
        setSummary(data);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load summary");
      } finally {
        setLoading(false);
      }
    };

    fetchSummary();
  }, [summaryId]);

  // Fetch the real transcript for the quick view (once the summary is known)
  useEffect(() => {
    if (!summary?.video_id) return;
    let cancelled = false;
    getTranscript(summary.video_id)
      .then((res) => {
        if (!cancelled) setTranscript(res.status === "ok" ? res.transcript : "");
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setTranscriptError(err instanceof Error ? err.message : "Failed to load transcript");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [summary?.video_id]);

  const tabs = [
    { id: "summary", label: "Concise Summary", icon: "📝", content: summary?.concise_summary || "" },
    { id: "topics", label: "Key Topics", icon: "📊", content: summary?.key_topics || "" },
    { id: "takeaways", label: "Important Takeaways", icon: "🎯", content: summary?.important_takeaways || "" },
    { id: "notes", label: "Comprehensive Notes", icon: "📖", content: summary?.comprehensive_notes || "" },
  ];

  const activeTabData = tabs.find((t) => t.id === activeTab) || tabs[0];

  const copyContent = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(activeTab);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      /* ignore */
    }
  };

  const downloadContent = (content: string, filename: string) => {
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const shareSummary = () => {
    if (navigator.share) {
      navigator.share({
        title: `Summary ${summaryId}`,
        url: window.location.href,
      });
    } else {
      navigator.clipboard.writeText(window.location.href);
      setCopied("share");
      setTimeout(() => setCopied(null), 2000);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/3" />
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4" />
          <div className="h-64 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="text-red-700 dark:text-red-300">{error}</p>
        </div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <p className="text-gray-500 dark:text-gray-400">Summary not found.</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link
            href="/"
            className="text-sm text-gray-500 dark:text-gray-400 hover:text-blue-500 transition-colors"
          >
            ← Back to Home
          </Link>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white mt-2">
            {summary.video_title}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {summary.model_name} · {summary.date_generated ? new Date(summary.date_generated).toLocaleDateString() : "Unknown date"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => copyContent(activeTabData.content)}
            className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 hover:text-blue-500 transition-colors"
            title="Copy"
          >
            <CopyIcon className="w-4 h-4" />
          </button>
          <button
            onClick={() => downloadContent(activeTabData.content, `summary-${summaryId}.md`)}
            className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 hover:text-blue-500 transition-colors"
            title="Download"
          >
            <DownloadIcon className="w-4 h-4" />
          </button>
          <button
            onClick={shareSummary}
            className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 hover:text-blue-500 transition-colors"
            title="Share"
          >
            <ShareIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 px-4 py-2.5 rounded-md text-sm font-medium transition-colors whitespace-nowrap ${
              activeTab === tab.id
                ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm"
                : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
        <div className="prose dark:prose-invert max-w-none">
          {activeTabData.content ? (
            <div dangerouslySetInnerHTML={{ __html: sanitizeHtml(activeTabData.content) }} />
          ) : (
            <p className="text-gray-500 dark:text-gray-400 italic">No content available.</p>
          )}
        </div>
      </div>

      {/* Transcript quick view */}
      <details className="mt-6 bg-white dark:bg-gray-800 rounded-xl shadow-lg overflow-hidden">
        <summary className="px-6 py-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors flex items-center justify-between">
          <span className="font-medium text-gray-900 dark:text-white">Transcript (quick view)</span>
          <ChevronDownIcon className="w-5 h-5 text-gray-400" />
        </summary>
        <div className="px-6 pb-4">
          {transcriptError ? (
            <p className="text-sm text-red-600 dark:text-red-400">{transcriptError}</p>
          ) : transcript ? (
            <pre className="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap font-sans">{transcript}</pre>
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">
              Transcript not available for this video.
            </p>
          )}
        </div>
      </details>

      {copied && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 bg-green-500 text-white rounded-lg text-sm shadow-lg">
          Copied to clipboard!
        </div>
      )}
    </div>
  );
}
