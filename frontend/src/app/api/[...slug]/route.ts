/** Catch-all proxy route — forwards all /api/* requests to the Flask backend. */

import { type NextRequest } from "next/server";

const BACKEND_URL = process.env.NEXT_API_URL || "http://app:5000";

async function forwardRequest(request: NextRequest, method: string) {
  try {
    const url = new URL(request.url);
    const backendPath = `${BACKEND_URL}${url.pathname}${url.search}`;

    const headers = new Headers(request.headers);
    headers.delete("host");

    const fetchInit: RequestInit = {
      method,
      headers,
    };

    if (method !== "GET" && method !== "HEAD") {
      const contentType = request.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        try {
          const bodyText = await request.text();
          if (bodyText) {
            fetchInit.body = bodyText;
          }
        } catch {
          // Empty or unparseable body
        }
      } else {
        fetchInit.body = request.body;
        // @ts-expect-error Node/Next fetch duplex support
        fetchInit.duplex = "half";
      }
    }

    const resp = await fetch(backendPath, fetchInit);

    // Check if the backend is streaming
    const responseContentType = resp.headers.get("content-type") || "";
    if (responseContentType.includes("text/event-stream")) {
      return new Response(resp.body, {
        status: resp.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache, no-transform",
          Connection: "keep-alive",
          "X-Accel-Buffering": "no",
        },
      });
    }

    // Non-streaming: parse and forward JSON or text
    const text = await resp.text();
    try {
      const data = JSON.parse(text);
      return Response.json(data, { status: resp.status });
    } catch {
      return new Response(text, {
        status: resp.status,
        headers: { "Content-Type": responseContentType || "text/plain" },
      });
    }
  } catch (err) {
    return Response.json({ error: "Backend unavailable", details: String(err) }, { status: 502 });
  }
}

export async function GET(request: NextRequest) {
  return forwardRequest(request, "GET");
}

export async function POST(request: NextRequest) {
  return forwardRequest(request, "POST");
}

export async function PUT(request: NextRequest) {
  return forwardRequest(request, "PUT");
}

export async function DELETE(request: NextRequest) {
  return forwardRequest(request, "DELETE");
}

export async function PATCH(request: NextRequest) {
  return forwardRequest(request, "PATCH");
}

export async function OPTIONS(request: NextRequest) {
  return forwardRequest(request, "OPTIONS");
}
