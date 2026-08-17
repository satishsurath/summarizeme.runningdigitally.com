/** Catch-all proxy route — forwards all /api/* requests to the Flask backend. */

import { type NextRequest } from "next/server";

const BACKEND_URL = process.env.NEXT_API_URL || "http://app:5000";

export async function GET(request: NextRequest) {
  try {
    const url = new URL(request.url);
    const backendPath = `${BACKEND_URL}${url.pathname}`;
    const resp = await fetch(backendPath, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    const data = await resp.json();
    return Response.json(data, { status: resp.status });
  } catch {
    return Response.json({ error: "Backend unavailable" }, { status: 502 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const url = new URL(request.url);
    const backendPath = `${BACKEND_URL}${url.pathname}`;
    const body = await request.json();
    const resp = await fetch(backendPath, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    return Response.json(data, { status: resp.status });
  } catch {
    return Response.json({ error: "Backend unavailable" }, { status: 502 });
  }
}
