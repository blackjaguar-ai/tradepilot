const BACKEND_URL = process.env.BACKEND_URL;

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/agent/approvals`, {
      cache: "no-store",
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
