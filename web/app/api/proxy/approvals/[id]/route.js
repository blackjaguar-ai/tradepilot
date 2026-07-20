const BACKEND_URL = process.env.BACKEND_URL;

export async function POST(request, { params }) {
  const { id } = params;
  try {
    const body = await request.json();
    const res = await fetch(`${BACKEND_URL}/agent/approvals/${id}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch (err) {
    return Response.json(
      { error: "No se pudo conectar con el backend", detail: String(err) },
      { status: 502 }
    );
  }
}
