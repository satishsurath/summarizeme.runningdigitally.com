/** Catch-all proxy route — forwards all /api/* requests to the Flask backend. */

import { type NextRequest } from "next/server";

const BACKEND_URL = process.env.NEXT_API_URL || "http://app:5000";

async function forwardRequest(request: NextRequest, method: string) {
  try {
    const url = new URL(request.url);
    const backendPath = `${BACKEND_URL}${url.pathname}`;

    const fetchInit: RequestInit = { method };
    if (method === "POST") {
      fetchInit.headers = { "Content-Type": "application/json" };
      fetchInit.body = JSON.stringify(await request.json());
    }

    const resp = await fetch(backendPath, fetchInit);

    // Check if the backend is streaming
    const contentType = resp.headers.get("content-type") || "";
    if (contentType.includes("text/event-stream")) {
      return new Response(resp.body, {
        status: resp.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        },
      });
    }

    // Non-streaming: parse and forward JSON
    const data = await resp.json();
    return Response.json(data, { status: resp.status });
  } catch {
    return Response.json({ error: "Backend unavailable" }, { status: 502 });
  }
}

export async function GET(request: NextRequest) {
  return forwardRequest(request, "GET");
}

export async function POST(request: NextRequest) {
  return forwardRequest(request, "POST");
}
