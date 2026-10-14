// GitHub login helper for Decap CMS ("Login with GitHub" in /admin/).
// Decap opens /auth in a popup; GitHub sends the user back to /callback with a
// one-time code, which is swapped here for a token (the client secret never
// reaches the browser). The token is handed to the CMS window with
// postMessage, but only if that window is on one of ALLOWED_ORIGINS.
//
// Secrets (set with `npx wrangler secret put …`): GITHUB_CLIENT_ID,
// GITHUB_CLIENT_SECRET. Variable (wrangler.jsonc): ALLOWED_ORIGINS.

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/auth") {
      const state = crypto.randomUUID();
      const github = new URL("https://github.com/login/oauth/authorize");
      github.searchParams.set("client_id", env.GITHUB_CLIENT_ID);
      github.searchParams.set("redirect_uri", `${url.origin}/callback`);
      github.searchParams.set("scope", "public_repo read:user");
      github.searchParams.set("state", state);
      return new Response(null, {
        status: 302,
        headers: {
          Location: github.toString(),
          "Set-Cookie": `oauth_state=${state}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=600`,
        },
      });
    }

    if (url.pathname === "/callback") {
      const code = url.searchParams.get("code");
      const state = url.searchParams.get("state");
      const saved = (request.headers.get("Cookie") || "").match(/(?:^|;\s*)oauth_state=([^;]+)/);
      if (!code || !state || !saved || saved[1] !== state) {
        return reply(env, "error", { message: "The login check failed. Close this window and try again." });
      }
      const res = await fetch("https://github.com/login/oauth/access_token", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json", "User-Agent": "cdpm-decap-oauth" },
        body: JSON.stringify({
          client_id: env.GITHUB_CLIENT_ID,
          client_secret: env.GITHUB_CLIENT_SECRET,
          code,
          redirect_uri: `${url.origin}/callback`,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!data.access_token) {
        return reply(env, "error", { message: data.error_description || "GitHub did not return a token." });
      }
      return reply(env, "success", { token: data.access_token, provider: "github" });
    }

    return new Response("Not found", { status: 404 });
  },
};

// The popup page that passes the result back to the CMS window (Decap's
// "authorizing:github" / "authorization:github:<status>:<json>" handshake).
function reply(env, status, content) {
  const message = `authorization:github:${status}:${JSON.stringify(content)}`;
  const origins = (env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  const js = (v) => JSON.stringify(v).replace(/</g, "\\u003c");
  const html = `<!doctype html><meta charset="utf-8"><title>Signing in…</title>
<p>Signing in… you can close this window if it stays open.</p>
<script>
(function () {
  var allowed = ${js(origins)};
  var message = ${js(message)};
  function receive(e) {
    if (allowed.indexOf(e.origin) === -1) return;
    window.removeEventListener("message", receive);
    window.opener.postMessage(message, e.origin);
  }
  window.addEventListener("message", receive);
  if (window.opener) window.opener.postMessage("authorizing:github", "*");
})();
</script>`;
  return new Response(html, {
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" },
  });
}
