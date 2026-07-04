# FauxReel — go-live checklist (free architecture)

Everything below runs on **free tiers**. The engine + worker + frontend are built and verified locally.
These steps need your accounts. Design: static frontend (Vercel) → dispatch function → **GitHub Actions
render farm** (public repo = unlimited free minutes) → **GitHub Release asset** (public URL) → frontend polls.

## 1. Render-farm repo (GitHub)
1. Push this `13-faceless-video-studio/` folder to a **public** GitHub repo (public = unlimited Actions minutes).
2. The workflow `.github/workflows/render.yml` runs on `repository_dispatch` (event `render`) and publishes
   each result to a Release tagged `renders` as `render-<id>.mp4` (public download URL).
3. Repo secrets (Settings → Secrets → Actions):
   - `GEMINI_API_KEY` — *optional*, free tier; enables "topic → script". Without it a curated fallback is used.
   - (`GITHUB_TOKEN` is provided automatically to the workflow — nothing to add.)

## 2. Frontend + dispatch function (Vercel)
1. Import the same repo on Vercel. Set **Root Directory = `web`** (so Vercel serves `web/` and the
   `web/api/generate.js` function; the Python engine at repo root is ignored by Vercel).
2. Vercel env vars:
   - `GH_REPO` = `youruser/yourrepo` (the render-farm repo above)
   - `GH_TOKEN` = a **fine-grained PAT** scoped to that repo with **Contents: read/write** (needed for
     `repository_dispatch`). Never commit it — it lives only in Vercel env.
3. Deploy → `https://<name>.vercel.app`. The generate button now dispatches a real render; the page polls
   the Release URL and plays the video when it appears (usually ~1-3 min).

## 3. Freemium (LemonSqueezy) — same pattern as FauxPost
- Create a "FauxReel Pro" product (license keys on). Pro = no watermark + HD + more renders.
- The frontend sends `{ pro:true }` when a valid license is stored; `api/generate.js` then sets the brand
  watermark to empty. Port `12-fake-post-studio/shared/pro.js` for the license-validate UI + set the
  checkout URL in `web/app.js`.

## 4. Performance notes (free, best-effort)
- Public repo → unlimited Actions minutes; jobs run in parallel (default ~20 concurrent).
- The workflow caches pip; ffmpeg installs via apt (~15s). A 15s reel renders in ~1-3 min (Pollinations is
  the slow part). If you outgrow this, swap the worker for a small always-on box — the engine is unchanged.

## Local dev / test
- Render one video without any cloud: `python worker.py --job job.json` where job.json is
  `{"id":"x","text":"your topic","mode":"topic","voice":"en-US-JennyNeural","mood":"drive"}`.
- Use the repo's shared venv for deps, or `pip install -r requirements.txt` in a fresh `.venv`.
