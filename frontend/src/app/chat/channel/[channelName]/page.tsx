/**
 * Chat page — AI-powered Q&A over channel content.
 * Replaces templates/chat.html
 */

"use client";

import { useState, useRef, useEffect } from "react";
import { useParams } from "next/navigation";
import { chatChannel } from "@/lib/api";

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

// ---------------------------------------------------------------------------
// Message types
// ---------------------------------------------------------------------------

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ChatPage() {
  const params = useParams();
  const channelName = params.channelName as string;

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      role: "assistant",
      content: `Hello! I can answer questions about "${channelName}". What would you like to know?`,
      timestamp: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [dataType, setDataType] = useState("comprehensive_notes");
  const [modelName, setModelName] = useState("nemo-qwen3.6-35b-a3b-nvfp4");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg: Message = {
      id: Date.now(),
      role: "user",
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response = await chatChannel(channelName, userMsg.content, dataType, modelName);
      const botMsg: Message = {
        id: Date.now() + 1,
        role: "assistant",
        content: response.answer,
      timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err: unknown) {
      const errorMsg: Message = {
        id: Date.now() + 1,
        role: "assistant",
        content: `Error: ${err instanceof Error ? err.message : "Failed to get response"}`,
      timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-4xl mx-auto">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
          Chat: {channelName}
        </h1>
        <div className="flex items-center gap-3 mt-2">
          <select
            value={dataType}
            onChange={(e) => setDataType(e.target.value)}
            className="px-2 py-1 rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-xs"
          >
            <option value="comprehensive_notes">Comprehensive Notes</option>
            <option value="concise_summary">Concise Summary</option>
            <option value="key_topics">Key Topics</option>
            <option value="important_takeaways">Important Takeaways</option>
          </select>
          <select
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            className="px-2 py-1 rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-xs"
          >
            <option value="nemo-qwen3.6-35b-a3b-nvfp4">Qwen 3.6 35B</option>
            <option value="nemo-qwen2.5-72b-instruct">Qwen 2.5 72B</option>
          </select>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center shrink-0">
                <BotIcon className="w-4 h-4 text-purple-600 dark:text-purple-400" />
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-xl px-4 py-3 ${
                msg.role === "user"
                  ? "bg-blue-500 text-white"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              }`}
            >
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              <span className={`text-xs mt-1 block ${
                msg.role === "user" ? "text-blue-200" : "text-gray-400"
              }`}>
                {new Date(msg.timestamp).toLocaleTimeString(undefined, { hour12: true })}
              </span>
            </div>
            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0">
                <UserIcon className="w-4 h-4 text-blue-600 dark:text-blue-400" />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center shrink-0">
              <BotIcon className="w-4 h-4 text-purple-600 dark:text-purple-400" />
            </div>
            <div className="bg-gray-100 dark:bg-gray-700 rounded-xl px-4 py-3">
              <div className="flex items-center gap-1.5">
                <SparkleIcon className="w-4 h-4 text-purple-500 animate-pulse" />
                <span className="text-sm text-gray-500 dark:text-gray-400">Thinking...</span>
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
            placeholder="Ask a question..."
            className="flex-1 px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-6 py-2.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <SendIcon className="w-5 h-5" />
          </button>
        </div>
      </form>
    </div>
  );
}
