export default {
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/healthz") {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return new Response(null, {
          status: 405,
          headers: { allow: "GET, HEAD" },
        });
      }

      return new Response(
        request.method === "HEAD"
          ? null
          : JSON.stringify({
              status: "ok",
              service: "ki-edge-preview",
              dataMode: "synthetic-only",
              backendConnected: false,
            }),
        {
          headers: {
            "content-type": "application/json; charset=utf-8",
            "cache-control": "no-store",
            "x-content-type-options": "nosniff",
          },
        },
      );
    }

    if (url.pathname === "/api" || url.pathname.startsWith("/api/")) {
      return new Response(
        JSON.stringify({ error: "not_found", backendConnected: false }),
        {
          status: 404,
          headers: {
            "content-type": "application/json; charset=utf-8",
            "cache-control": "no-store",
            "x-content-type-options": "nosniff",
          },
        },
      );
    }

    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
