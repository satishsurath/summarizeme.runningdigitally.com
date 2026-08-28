"use client";

import { useState, useRef, useEffect } from "react";
import { useParams } from "next/navigation";
import {
  chatChannelStream,
  listModels,
  getUserPreference,
  type ModelInfo,
  type SourceReference,
} from "@/lib/api";
import { sanitizeHtml } from "@/lib/sanitize";
import { ThinkingBlock } from "@/components/ThinkingBlock";
import { CopyMessageMenu } from "@/components/CopyMessageMenu";
import { parseThinkingContent } from "@/lib/thinking";

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function SendIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

function BotIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="11" width="18" height="10" rx="2" />
      <circle cx="12" cy="5" r="2" />
      <path d="M12 7v4" />
      <line x1="8" y1="16" x2="8" y2="16" />
      <line x1="16" y1="16" x2="16" y2="16" />
    </svg>
  );
}

function UserIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function SparkleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z" />
    </svg>
  );
}

function PlayIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Message types
// ---------------------------------------------------------------------------

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  reasoning_content?: string;
  sources?: SourceReference[];
  timestamp: string;
  formattedTime: string;
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, { hour12: true });
  } catch {
    return "";
  }
}

export default function ChatPage() {
  const params = useParams();
  const channelName = params.channelName as string;

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      role: "assistant",
      content: `Hello! I can answer questions about "${channelName}". What would you like to know?`,
      timestamp: "",
      formattedTime: "",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [dataType, setDataType] = useState("automatic");
  const [modelName, setModelName] = useState("nemo-qwen3.8-27b-nvfp4");
  const [reasoningEffort, setReasoningEffort] = useState("medium");
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const [streamingMsgId, setStreamingMsgId] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load models and user preference
  useEffect(() => {
    listModels()
      .then((res) => {
        if (res.models && res.models.length > 0) {
          setAvailableModels(res.models);
          const defaultModel = res.models.find((m) => m.is_default);
          if (defaultModel) setModelName(defaultModel.model_id);
        }
      })
      .catch(() => { /* fallback */ });

    getUserPreference()
      .then((pref) => {
        if (pref.preferred_gen_model) setModelName(pref.preferred_gen_model);
        if (pref.preferred_reasoning_effort) setReasoningEffort(pref.preferred_reasoning_effort);
      })
      .catch(() => { /* fallback */ });
  }, []);

  // Scroll to bottom on new messages or streaming updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingMsgId]);

  // Stamp the seed message with a client-side time after mount.
  useEffect(() => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === 0 && !m.timestamp
          ? { ...m, timestamp: new Date().toISOString(), formattedTime: formatTime(new Date().toISOString()) }
          : m,
      ),
    );
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg: Message = {
      id: Date.now(),
      role: "user",
      content: input.trim(),
      timestamp: new Date().toISOString(),
      formattedTime: formatTime(new Date().toISOString()),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    const streamMsgId = Date.now() + 1;
    setMessages((prev) => [
      ...prev,
      {
        id: streamMsgId,
        role: "assistant" as const,
        content: "",
        timestamp: new Date().toISOString(),
        formattedTime: "",
      },
    ]);
    setStreamingMsgId(streamMsgId);

    try {
      await chatChannelStream(
        channelName,
        userMsg.content,
        dataType,
        modelName,
        {
          onSources: (sources: SourceReference[]) => {
            setMessages((prev) =>
              prev.map((m) => (m.id === streamMsgId ? { ...m, sources } : m)),
            );
          },
          onReasoningDelta: (delta: string) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamMsgId
                  ? { ...m, reasoning_content: (m.reasoning_content || "") + delta }
                  : m,
              ),
            );
          },
          onAnswerDelta: (delta: string) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamMsgId ? { ...m, content: m.content + delta } : m,
              ),
            );
          },
          onDone: (data) => {
            if (data.conversation_id) {
              setConversationId(data.conversation_id);
            }
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamMsgId
                  ? {
                      ...m,
                      content: data.answer || m.content,
                      reasoning_content: data.thinking || m.reasoning_content,
                      formattedTime: formatTime(new Date().toISOString()),
                    }
                  : m,
              ),
            );
            setStreamingMsgId(null);
          },
          onError: (error: string) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamMsgId
                  ? { ...m, content: `Error: ${error}`, formattedTime: formatTime(new Date().toISOString()) }
                  : m,
              ),
            );
            setStreamingMsgId(null);
          },
        },
        conversationId,
        reasoningEffort,
      );
    } catch (err: unknown) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === streamMsgId
            ? {
                ...m,
                content: `Error: ${err instanceof Error ? err.message : "Failed to get response"}`,
                formattedTime: formatTime(new Date().toISOString()),
              }
            : m,
        ),
      );
      setStreamingMsgId(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-5xl mx-auto">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
          Chat: {channelName}
        </h1>
        <div className="flex flex-wrap items-center gap-3 mt-2">
          <div>
            <label className="text-[10px] uppercase font-bold text-gray-400 block mb-0.5">Grounding</label>
            <select
              value={dataType}
              onChange={(e) => setDataType(e.target.value)}
              className="px-2 py-1 rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-xs"
            >
              <option value="automatic">Automatic (Hybrid RRF)</option>
              <option value="transcript">Full Transcripts</option>
              <option value="comprehensive_notes">Comprehensive Notes</option>
              <option value="key_topics">Key Topics</option>
              <option value="concise_summary">Concise Summary</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] uppercase font-bold text-gray-400 block mb-0.5">Model</label>
            <select
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              className="px-2 py-1 rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-xs font-mono"
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
            <label className="text-[10px] uppercase font-bold text-gray-400 block mb-0.5">Reasoning Effort</label>
            <select
              value={reasoningEffort}
              onChange={(e) => setReasoningEffort(e.target.value)}
              className="px-2 py-1 rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-xs"
            >
              <option value="disabled">Disabled (Fastest)</option>
              <option value="low">Low</option>
              <option value="medium">Medium (Balanced)</option>
              <option value="xhigh">Extra High (Deep Reasoning)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.map((msg) => {
          const isAssistant = msg.role === "assistant";
          const parsed = isAssistant
            ? parseThinkingContent(msg.content, msg.id === streamingMsgId)
            : null;
          const displayThinking = msg.reasoning_content || parsed?.thinking;

          return (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {isAssistant && (
                <div className="w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center shrink-0">
                  <BotIcon className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                </div>
              )}
              <div
                className={`max-w-[85%] rounded-xl px-4 py-3 ${
                  msg.role === "user"
                    ? "bg-blue-500 text-white"
                    : "bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                }`}
              >
                {isAssistant && displayThinking && (
                  <ThinkingBlock
                    thinking={displayThinking}
                    isStreaming={msg.id === streamingMsgId && !msg.content}
                  />
                )}
                {isAssistant ? (
                  <div
                    className="text-sm leading-relaxed whitespace-pre-wrap font-sans"
                    dangerouslySetInnerHTML={{ __html: sanitizeHtml(parsed?.answer || msg.content) }}
                  />
                ) : (
                  <div className="text-sm leading-relaxed whitespace-pre-wrap font-sans">{msg.content}</div>
                )}

                {/* Grounding Source Citations */}
                {isAssistant && msg.sources && msg.sources.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-black/5 dark:border-white/10">
                    <span className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider block mb-1.5">
                      Grounding Sources
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.sources.map((s, idx) => (
                        <a
                          key={idx}
                          href={s.youtube_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 text-[11px] font-mono hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors"
                          title={s.excerpt}
                        >
                          <PlayIcon className="w-2.5 h-2.5" />
                          {s.video_id} {s.start_seconds !== undefined ? `(${Math.floor(s.start_seconds)}s)` : ""}
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between mt-2 pt-1 border-t border-black/5 dark:border-white/5 gap-4">
                  <span
                    className={`text-xs ${
                      msg.role === "user" ? "text-blue-200" : "text-gray-400"
                    }`}
                  >
                    {msg.formattedTime}
                  </span>
                  <CopyMessageMenu
                    content={msg.content}
                    thinking={displayThinking}
                    answer={parsed?.answer || msg.content}
                    role={msg.role}
                  />
                </div>
              </div>
              {msg.role === "user" && (
                <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0">
                  <UserIcon className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                </div>
              )}
            </div>
          );
        })}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center shrink-0">
              <BotIcon className="w-4 h-4 text-purple-600 dark:text-purple-400" />
            </div>
            <div className="bg-gray-100 dark:bg-gray-700 rounded-xl px-4 py-3">
              <div className="flex items-center gap-1.5">
                <SparkleIcon className="w-4 h-4 text-purple-500 animate-pulse" />
                <span className="text-sm text-gray-500 dark:text-gray-400">Retrieving & generating...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
      >
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about this channel..."
            className="flex-1 px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-6 py-2.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            <SendIcon className="w-5 h-5" />
          </button>
        </div>
      </form>
    </div>
  );
}
