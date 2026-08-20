/**
 * Typed API client for SummarizeMe backend.
 *
 * All API calls go through this module for consistent error handling,
 * type safety, and configurable base URL.
 */

// Backend base URL — use direct URL for streaming to avoid Next.js proxy buffering
const FLASK_URL = process.env.NEXT_PUBLIC_FLASK_URL || "";
const API_BASE = "";

function apiPath(path: string): string {
  // Use direct Flask URL for streaming endpoints if publicly accessible,
  // otherwise fallback to Next.js proxy route to prevent internal Docker DNS errors.
  if (path.includes("/stream")) {
    if (
      FLASK_URL &&
      !FLASK_URL.includes("://app:") &&
      !FLASK_URL.includes("://app/")
    ) {
      return `${FLASK_URL}${path}`;
    }
    return path;
  }
  return `${API_BASE}${path}`;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Video {
  video_id: string;
  title: string;
  upload_date: string;
  summaries_v2: SummaryMeta[];
}

export interface SummaryMeta {
  id: number;
  model_name: string;
  date_generated: string | null;
}

export interface ChannelMeta {
  folder_name: string;
  original_playlist_id: string;
}

export interface VideoListResponse {
  total: number;
  page: number;
  page_size: number;
  videos: Video[];
}

export interface TaskStatus {
  status: string;
  processed: number;
  total: number;
  errors: string[];
}

export interface TaskInfo {
  task_id: string;
  task_type: string;
  status: string;
  created_at: number;
  updated_at: number;
  total: number;
  processed: number;
  errors: string[];
  metadata: Record<string, unknown>;
  progress_percent: number;
}

export interface ChatResponse {
  answer: string;
}

export interface ApiResponse<T> {
  status: string;
  data?: T;
  message?: string;
  task_id?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function fetchJson<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      message: response.statusText,
    }));
    throw new Error(
      error.message || `API error ${response.status}: ${response.statusText}`,
    );
  }

  return response.json() as T;
}

// ---------------------------------------------------------------------------
// Channels
// ---------------------------------------------------------------------------

export async function listChannels(): Promise<ChannelMeta[]> {
  return fetchJson<ChannelMeta[]>(apiPath("/api/channels"));
}

export async function startChannelDownload(
  channelUrl: string,
): Promise<ApiResponse<null>> {
  return fetchJson<ApiResponse<null>>(apiPath("/api/channel/start"), {
    method: "POST",
    body: JSON.stringify({ channel_url: channelUrl }),
  });
}

export async function renameChannel(
  oldName: string,
  newName: string,
): Promise<ApiResponse<{ old_name: string; new_name: string }>> {
  return fetchJson<ApiResponse<{ old_name: string; new_name: string }>>(
    apiPath("/api/channels/rename"),
    {
      method: "POST",
      body: JSON.stringify({ old_name: oldName, new_name: newName }),
    },
  );
}

export async function deleteChannel(name: string): Promise<ApiResponse<null>> {
  return fetchJson<ApiResponse<null>>(apiPath("/api/channels/delete"), {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function refreshChannel(
  channelName: string,
): Promise<ApiResponse<null>> {
  return fetchJson<ApiResponse<null>>(apiPath("/api/channels/refresh"), {
    method: "POST",
    body: JSON.stringify({ channel_name: channelName }),
  });
}

// ---------------------------------------------------------------------------
// Videos
// ---------------------------------------------------------------------------

export async function listVideos(
  channelName: string,
  options?: {
    page?: number;
    page_size?: number;
    sort_by?: string;
    sort_order?: string;
    filter?: string;
  },
): Promise<VideoListResponse> {
  const params = new URLSearchParams();
  if (options) {
    params.set("page", String(options.page ?? 1));
    params.set("page_size", String(options.page_size ?? 50));
    if (options.sort_by) params.set("sort_by", options.sort_by);
    if (options.sort_order) params.set("sort_order", options.sort_order);
    if (options.filter) params.set("filter", options.filter);
  }
  return fetchJson<VideoListResponse>(
    apiPath(`/api/videos/${channelName}?${params}`),
  );
}

// ---------------------------------------------------------------------------
// Summarization
// ---------------------------------------------------------------------------

export async function summarizeVideos(
  channelName: string,
  videoIds: string[],
  model?: string,
): Promise<ApiResponse<null>> {
  return fetchJson<ApiResponse<null>>(apiPath("/api/summarize_v2"), {
    method: "POST",
    body: JSON.stringify({
      channel_name: channelName,
      video_ids: videoIds,
      model: model ?? "nemo-qwen3.6-35b-a3b-nvfp4",
    }),
  });
}

export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  return fetchJson<TaskStatus>(apiPath(`/api/summarize_v2/status/${taskId}`));
}

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

export async function listActiveTasks(): Promise<TaskInfo[]> {
  return fetchJson<TaskInfo[]>(apiPath("/api/active-tasks"));
}

export async function listAllTasks(): Promise<TaskInfo[]> {
  return fetchJson<TaskInfo[]>(apiPath("/api/all-tasks"));
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export async function chatChannel(
  channelName: string,
  query: string,
  dataType?: string,
  modelName?: string,
): Promise<ChatResponse> {
  return fetchJson<ChatResponse>(
    apiPath(`/api/chat-channel/${channelName}`),
    {
      method: "POST",
      body: JSON.stringify({
        query,
        data_type: dataType ?? "comprehensive_notes",
        model_name: modelName ?? "nemo-qwen3.6-35b-a3b-nvfp4",
      }),
    },
  );
}

export async function chatVideo(
  videoId: string,
  query: string,
  dataType?: string,
  modelName?: string,
): Promise<ChatResponse> {
  return fetchJson<ChatResponse>(apiPath(`/api/chat-video/${videoId}`), {
    method: "POST",
    body: JSON.stringify({
      query,
      data_type: dataType ?? "comprehensive_notes",
      model_name: modelName ?? "nemo-qwen3.6-35b-a3b-nvfp4",
    }),
  });
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export async function healthCheck(): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(apiPath("/health"));
}

// ---------------------------------------------------------------------------
// Transcript
// ---------------------------------------------------------------------------

export interface TranscriptResponse {
  status: string;
  video_id: string;
  title: string;
  transcript: string;
}

export async function getTranscript(videoId: string): Promise<TranscriptResponse> {
  return fetchJson<TranscriptResponse>(
    apiPath(`/api/transcript/${encodeURIComponent(videoId)}`),
  );
}

// ---------------------------------------------------------------------------
// Streaming Chat (SSE)
// ---------------------------------------------------------------------------

export interface ChatStreamCallbacks {
  onDelta: (delta: string) => void;
  onDone: (answer: string) => void;
  onError: (error: string) => void;
}

async function parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  callbacks: ChatStreamCallbacks,
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "message";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const rawLine of lines) {
        const line = rawLine.trimEnd();
        if (!line) {
          // Empty line indicates end of an SSE event frame: reset default event
          currentEvent = "message";
          continue;
        }

        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
          continue;
        }

        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            if (currentEvent === "loading") {
              // Loading event acknowledgment
            } else if (currentEvent === "error") {
              callbacks.onError(data.error || "Unknown error");
            } else if (data.error) {
              callbacks.onError(data.error);
            } else if (data.delta) {
              callbacks.onDelta(data.delta);
            } else if (data.answer && (data.done || currentEvent === "done")) {
              // Terminal frame: either the normal final frame (done: true) or an
              // explicit "done" event (e.g. no relevant content found).
              callbacks.onDone(data.answer);
            }
          } catch {
            // skip malformed JSON
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function chatChannelStream(
  channelName: string,
  query: string,
  dataType: string,
  modelName: string,
  callbacks: ChatStreamCallbacks,
): Promise<void> {
  const response = await fetch(
    apiPath(`/api/chat-channel/${channelName}/stream`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        data_type: dataType,
        model_name: modelName,
      }),
    },
  );

  if (!response.ok) {
    callbacks.onError(`HTTP ${response.status}: ${response.statusText}`);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError("No response body");
    return;
  }

  await parseSSEStream(reader, callbacks);
}

export async function chatVideoStream(
  videoId: string,
  query: string,
  dataType: string,
  modelName: string,
  callbacks: ChatStreamCallbacks,
): Promise<void> {
  const response = await fetch(
    apiPath(`/api/chat-video/${videoId}/stream`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        data_type: dataType,
        model_name: modelName,
      }),
    },
  );

  if (!response.ok) {
    callbacks.onError(`HTTP ${response.status}: ${response.statusText}`);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError("No response body");
    return;
  }

  await parseSSEStream(reader, callbacks);
}
