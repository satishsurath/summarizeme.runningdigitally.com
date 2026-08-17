/**
 * API route to proxy summary requests to the Flask backend.
 */

const API_BASE = process.env.NEXT_API_URL || "http://localhost:5001";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  try {
    const response = await fetch(`${API_BASE}/api/summaries/${id}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: response.statusText }));
      return Response.json(error, { status: response.status });
    }

    const data = await response.json();
    return Response.json(data);
  } catch (err: unknown) {
    return Response.json(
      { error: err instanceof Error ? err.message : "Failed to fetch summary" },
      { status: 500 },
    );
  }
}
