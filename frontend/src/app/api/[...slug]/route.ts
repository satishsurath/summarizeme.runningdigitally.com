/** Catch-all proxy route — forwards all /api/* requests to the Flask backend. */

import { type NextRequest } from "next/server";

const BACKEND_URL = process.env.NEXT_API_URL || "http://app:5000";

async function forwardRequest(request: NextRequest, method: string) {
  try {
    const url = new URL(request.url);
    const baseUrl = BACKEND_URL.replace(/\/+$/, "");
    const backendPath = `${baseUrl}${url.pathname}${url.search}`;

    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.delete("content-length");

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

    const responseHeaders = new Headers(resp.headers);
    responseHeaders.delete("content-encoding");

    // Check if the backend is streaming
    const responseContentType = resp.headers.get("content-type") || "";
    if (responseContentType.includes("text/event-stream")) {
      responseHeaders.set("Content-Type", "text/event-stream");
      responseHeaders.set("Cache-Control", "no-cache, no-transform");
      responseHeaders.set("Connection", "keep-alive");
      responseHeaders.set("X-Accel-Buffering", "no");
    }

    return new Response(resp.body, {
      status: resp.status,
      headers: responseHeaders,
    });
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
