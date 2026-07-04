/* Vercel serverless function: POST /api/generate
   Holds the GitHub PAT (env) and triggers the render farm via repository_dispatch.
   Returns { id, resultUrl } — a public GitHub Release asset URL the frontend polls
   by trying to load the video (no status endpoint needed). */
const crypto = require("crypto");

module.exports = async (req, res) => {
  if (req.method !== "POST") { res.status(405).json({ error: "POST only" }); return; }
  const repo = process.env.GH_REPO;     // "owner/repo" of the render-farm repo
  const token = process.env.GH_TOKEN;   // fine-grained PAT: this repo, contents + dispatch
  if (!repo || !token) { res.status(500).json({ error: "server not configured (GH_REPO/GH_TOKEN)" }); return; }

  let body = req.body;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch (e) { body = {}; } }
  body = body || {};

  const id = crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  const payload = {
    id,
    format: body.format === "reddit" ? "reddit" : undefined,
    text: String(body.text || "").slice(0, 1200),
    mode: body.mode === "script" || body.mode === "topic" ? body.mode : undefined,
    voice: body.voice, rate: body.rate, mood: body.mood,
    brand: body.pro ? "" : "fauxreel.vercel.app",   // Pro removes the watermark
    scenes: Array.isArray(body.scenes) ? body.scenes.slice(0, 5) : [],
    // Reddit-story fields
    title: body.title ? String(body.title).slice(0, 300) : undefined,
    story: body.story ? String(body.story).slice(0, 3000) : undefined,
    subreddit: body.subreddit ? String(body.subreddit).slice(0, 50) : undefined,
  };

  try {
    const r = await fetch(`https://api.github.com/repos/${repo}/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "fauxreel",
      },
      body: JSON.stringify({ event_type: "render", client_payload: payload }),
    });
    if (r.status !== 204) {
      const t = await r.text();
      res.status(502).json({ error: "dispatch failed", detail: t.slice(0, 200) });
      return;
    }
  } catch (e) {
    res.status(502).json({ error: "dispatch error", detail: String(e).slice(0, 200) });
    return;
  }

  const resultUrl = `https://github.com/${repo}/releases/download/renders/render-${id}.mp4`;
  res.status(200).json({ id, resultUrl });
};
