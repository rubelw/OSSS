export async function GET(request) {
  console.log(JSON.stringify({
    level: 'info',
    msg: 'hit /api/foo',
    path: request.url
  }));

  return new Response(
    JSON.stringify({ ok: true }),
    {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    }
  );
}
