# Faceless Video Studio — architecture (second big project)

Working name: **FauxReel** (pairs with FauxPost; rename freely).

## What it is
A self-serve SaaS: user types a **topic or script** → picks a voice/style → gets a finished
**vertical short-form video** (TTS voiceover + AI visuals + word-timed captions + music) to post on
TikTok / Reels / Shorts. Proven paid category (Opus Clip, Submagic, InVideo — $20-50/mo).

## Honest cost reality (differs from FauxPost)
FauxPost was $0 forever because it renders in the browser. **Video rendering needs ffmpeg = real compute**,
so this project is *not* zero-cost the same way. It's **near-zero** if we pick the render worker well.
The engine itself uses **only free/keyless sources** (edge-tts, Pollinations FLUX, numpy/incompetech music,
ffmpeg) → no per-render API bill. The only cost is where ffmpeg runs.

## The engine (BUILT + VERIFIED)
`engine.py` → `render_video(job, out_path)`. Reuses the proven idioms from
`02-auto-poster-agent/generate_cinematic_reels.py` + `agent.py` (VO/SRT) + `11-cocuk-cizgi-film` (SSL).
- **VO + captions:** edge-tts `Communicate` + `SubMaker` → mp3 + **word-timed SRT**, burned with libass.
- **Visuals:** Pollinations FLUX stills (keyless, retry+backoff) → Ken Burns (`zoompan`) → `xfade` chain.
  Pexels footage optional (if key). picsum + last-good-frame fallbacks so a render never fails on images.
- **Music:** numpy synth bed (default, offline) or incompetech Kevin MacLeod CC-BY (optional).
- **Output:** 1080×1920 h264+aac, `+faststart`. Duration follows the voiceover length.
- **job schema:** `{ script, voice, rate, brand, mood, scenes:[{prompt}] }`.

## The SaaS around the engine (to build next)
```
[ Static frontend on Vercel (free) ]  --submit job-->  [ Job queue ]  -->  [ Render worker (ffmpeg) ]
   topic/script, voice, style pick                     (a JSON file /        runs engine.py, uploads
   poll for result, preview, download                   simple store)         mp4 to storage, marks done
```
- **Frontend:** static (same stack as FauxPost) — form + poll + preview. Free on Vercel.
- **Script step (optional):** turn a bare *topic* into a script + scene prompts. Free via Gemini
  free-tier (reuse `reels_story.py` pattern) with a curated fallback — keyless.
- **Worker options (the one decision that forks cost):**
  1. **GitHub Actions as a render farm** — free minutes, exactly how the existing IG/YT bots already run.
     Async (a render takes minutes), but genuinely ~$0. Best MVP fit.
  2. **A small always-on box** (Render/Railway/Fly/VPS) — faster, ~$5-7/mo, real-time-ish.
  3. **User's own machine** for early manual fulfillment (validate demand before paying for infra).
- **Storage/delivery:** commit the mp4 to a repo/raw URL (bot pattern) or a free object store; frontend polls.

## Monetization
- **Freemium credits:** N free renders/month with a watermark; **Pro** = more/HD/no-watermark via
  **LemonSqueezy** (same client-side license pattern as FauxPost `shared/pro.js`). Direct payment = the
  reliable leg. Global USD.
- Optional: a **RapidAPI** "generate short video" endpoint later (async job API).

## Status & next
- [x] Engine built, reuses existing pipeline, **verified with a real local render**.
- [x] Frontend (static, Vercel) — form + poll-by-loading-video + demo fallback. **Verified.**
- [x] Topic→script step (`scriptgen.py`, Gemini free + curated fallback). **Verified (fallback).**
- [x] Worker (`worker.py`) + **GitHub Actions render farm** (`.github/workflows/render.yml`) +
      dispatch function (`web/api/generate.js`). Worker path **verified end-to-end locally**
      (topic → script → scenes → mp4). Cloud round-trip verifies at deploy (needs repo + secrets).
- [ ] Freemium (LemonSqueezy) full license UI — `{pro:true}` already removes the watermark server-side;
      port `12-fake-post-studio/shared/pro.js` for the validate flow.
- [ ] Optional: RapidAPI async endpoint; AI-generated scene prompts by default; grouped multi-word captions.

## Chosen architecture (free, best-for-free)
Public GitHub repo → **unlimited free Actions minutes**, parallel jobs. Frontend on Vercel (free), one tiny
dispatch function (free), delivery via public GitHub Release assets (free). No always-on server, no per-render
API bill. Upgrade path (if revenue): swap the worker for a $5-7/mo box — the engine is unchanged. See `SETUP.md`.
