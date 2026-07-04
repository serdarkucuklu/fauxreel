"""
FauxReel / Faceless Video Studio — render engine.

render_video(job, out_path) -> mp4 : a self-serve, 100% keyless faceless short.
Pipeline (all free sources): edge-tts voiceover + word-timed captions (burned) +
Pollinations FLUX stills with Ken Burns motion + numpy synth (or incompetech) music,
composited to a vertical 1080x1920 h264+aac clip via raw ffmpeg.

Reuses the proven idioms from 02-auto-poster-agent/generate_cinematic_reels.py +
agent.py (VO/SRT) + 11-cocuk-cizgi-film (SSL/keyless). No API keys required.
"""
import sys, os, io, json, time, math, subprocess, tempfile, shutil, urllib.parse, asyncio, hashlib

# Windows cp1252 console -> utf-8 (Turkish/emoji safe)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
# Corporate-proxy SSL: use OS trust store, keep verification ON (never verify=False).
try:
    import truststore; truststore.inject_into_ssl()
except Exception as e:
    print(f"[warn] truststore: {e}")
try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except Exception:
    pass

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import edge_tts

W, H, FPS = 1080, 1920, 30
XF = 0.6  # crossfade seconds
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(HERE, "assets", "Montserrat-Bold.ttf")


def _ff():
    return shutil.which("ffmpeg") or "ffmpeg"

def _ffprobe():
    return shutil.which("ffprobe") or "ffprobe"

def run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (rc={p.returncode}): {cmd[0]}\n"
                           + p.stderr.decode("utf-8", "replace")[-1600:])

def probe_dur(path):
    out = subprocess.run([_ffprobe(), "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nk=1:nw=1", path], stdout=subprocess.PIPE).stdout.decode().strip()
    try:
        return float(out)
    except Exception:
        return 0.0


# ── visuals ──────────────────────────────────────────────────────────────────
def pollinations_still(prompt, seed, out_png, attempts=6):
    q = urllib.parse.quote(prompt + ", cinematic, vertical 9:16, high detail")
    for a in range(attempts):
        s = seed + 1000 * a
        url = f"https://image.pollinations.ai/prompt/{q}?width={W}&height={H}&nologo=true&model=flux&enhance=false&seed={s}"
        try:
            r = requests.get(url, timeout=90)
            if r.status_code == 200 and len(r.content) > 8000:
                with open(out_png, "wb") as f:
                    f.write(r.content)
                return True
        except Exception:
            pass
        time.sleep(min(2 + a * 2, 10))
    return False

def picsum_still(seed, out_png):
    try:
        r = requests.get(f"https://picsum.photos/seed/fr{seed}/{W}/{H}", timeout=45)
        if r.status_code == 200 and len(r.content) > 8000:
            with open(out_png, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False

def kenburns_clip(still, out, seconds, zoom_in=True):
    frames = max(1, int(seconds * FPS))
    if zoom_in:
        z = "min(zoom+0.0010,1.18)"
    else:
        z = "if(lte(zoom,1.0),1.18,max(1.001,zoom-0.0010))"
    vf = (f"scale={W*2}:{H*2},zoompan=z='{z}':d={frames}:"
          f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},setsar=1")
    run([_ff(), "-y", "-loop", "1", "-i", still, "-vf", vf, "-t", f"{seconds:.3f}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-r", str(FPS), out])

def xfade_chain(clips, seconds, out):
    if len(clips) == 1:
        shutil.copyfile(clips[0], out)
        return
    cur = clips[0]
    cur_len = seconds
    trans = ["fade", "slideright", "fade", "slideup"]
    for k in range(1, len(clips)):
        nxt = out if k == len(clips) - 1 else out + f".{k}.mp4"
        off = cur_len - XF
        t = trans[(k - 1) % len(trans)]
        run([_ff(), "-y", "-i", cur, "-i", clips[k], "-filter_complex",
             f"[0][1]xfade=transition={t}:duration={XF}:offset={off:.3f},format=yuv420p[v]",
             "-map", "[v]", "-c:v", "libx264", "-crf", "18", "-r", str(FPS), nxt])
        cur = nxt
        cur_len += seconds - XF


# ── audio ────────────────────────────────────────────────────────────────────
def synth_music(out_wav, seconds, mood="calm"):
    sr = 44100
    n = int(seconds * sr)
    t = np.linspace(0, seconds, n, endpoint=False)
    chords = {"calm": [220, 277.18, 329.63], "drive": [246.94, 311.13, 369.99], "bright": [261.63, 329.63, 392.0]}
    freqs = chords.get(mood, chords["calm"])
    sig = np.zeros(n)
    for i, f in enumerate(freqs):
        sig += (0.28 / (i + 1)) * np.sin(2 * np.pi * f * t + i)
    lfo = 0.55 + 0.45 * np.sin(2 * np.pi * 0.08 * t)
    sig *= lfo
    sig /= (np.max(np.abs(sig)) + 1e-6)
    sig *= 0.5
    pcm = (sig * 32767).astype(np.int16)
    import wave
    with wave.open(out_wav, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())


async def _tts(text, voice, rate, mp3, srt):
    # boundary="WordBoundary" -> word-timed captions (edge-tts 7.x defaults to SentenceBoundary,
    # which would leave get_srt() empty if we only listen for WordBoundary). Feed both to be safe.
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, boundary="WordBoundary")
    submaker = edge_tts.SubMaker()
    with open(mp3, "wb") as fp:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fp.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                submaker.feed(chunk)
    with open(srt, "w", encoding="utf-8") as f:
        f.write(submaker.get_srt())

def generate_voiceover(text, voice, rate, mp3, srt):
    asyncio.run(_tts(text, voice, rate, mp3, srt))


# ── karaoke captions (word-by-word pop, Hormozi/TikTok style) ────────────────
def _srt_to_events(srt_path):
    """Parse an SRT into [(start_sec, end_sec, word), ...]."""
    def ts(t):
        t = t.strip().replace(",", ".")
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    events, block = [], []
    with open(srt_path, encoding="utf-8") as f:
        raw = f.read().strip()
    for chunk in raw.split("\n\n"):
        lines = [l for l in chunk.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        tl = next((l for l in lines if "-->" in l), None)
        if not tl:
            continue
        a, b = tl.split("-->")
        text = " ".join(lines[lines.index(tl) + 1:]).strip()
        if text:
            events.append((ts(a), ts(b), text))
    return events

def _ass_time(sec):
    cs = int(round(sec * 100))
    h = cs // 360000; cs -= h * 360000
    m = cs // 6000; cs -= m * 6000
    s = cs // 100; cs -= s * 100
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

def srt_to_karaoke_ass(srt_path, ass_path, accent="&H0033CCFF", fontsize=120, margin_v=0):
    """Write an ASS where each word pops in big, centered — the modern faceless look.
       accent = ASS BGR hex for the highlight tint (default gold). margin_v shifts from center."""
    events = _srt_to_events(srt_path)
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Pop,Montserrat,{fontsize},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        f"-1,0,0,0,100,100,0,0,1,7,3,5,60,60,{margin_v},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = []
    for (a, b, word) in events:
        dur = max(0.05, b - a)
        popn = int(min(120, dur * 1000 * 0.35))
        # pop-in scale 55->112->100 + slight upward drift; whole word tinted on the "hit"
        eff = (r"{\an5\fad(40,40)\fscx55\fscy55"
               r"\t(0," + str(popn) + r",\fscx112\fscy112)"
               r"\t(" + str(popn) + r"," + str(popn + 60) + r",\fscx100\fscy100)}")
        lines.append(f"Dialogue: 0,{_ass_time(a)},{_ass_time(b)},Pop,,0,0,0,,{eff}{word.upper()}")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")


# ── brand overlay ────────────────────────────────────────────────────────────
def make_brand_png(text, out_png):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 34)
    except Exception:
        font = ImageFont.load_default()
    tw = d.textlength(text, font=font)
    d.text(((W - tw) / 2, H - 70), text, font=font, fill=(255, 255, 255, 210))
    img.save(out_png)


# ── main render ──────────────────────────────────────────────────────────────
def render_video(job, out_path):
    """
    job = {
      "script": "spoken narration (drives captions + duration)",
      "voice":  "en-US-JennyNeural",     # any edge-tts voice
      "rate":   "+0%",
      "brand":  "fauxreel.vercel.app",          # burned watermark
      "mood":   "calm"|"drive"|"bright", # synth music color
      "scenes": [ {"prompt": "image prompt"} , ... ]  # visuals
    }
    """
    work = tempfile.mkdtemp(prefix="fr_")
    try:
        voice = job.get("voice", "en-US-JennyNeural")
        rate = job.get("rate", "+0%")
        script = job["script"].strip()
        scenes = job.get("scenes") or [{"prompt": "abstract cinematic background"}]
        seed = int(hashlib.md5(script.encode()).hexdigest()[:6], 16)

        # 1) voiceover + word-timed SRT
        vo = os.path.join(work, "vo.mp3"); srt = os.path.join(work, "subs.srt")
        generate_voiceover(script, voice, rate, vo, srt)
        vo_len = probe_dur(vo)
        total = max(4.0, vo_len + 0.6)
        print(f"[engine] VO {vo_len:.2f}s, total {total:.2f}s, {len(scenes)} scenes")

        # 2) per-scene visuals (Ken Burns), duration split so xfade sums ~= total
        n = len(scenes)
        d_scene = (total + (n - 1) * XF) / n
        clips = []
        last_good = None
        for i, sc in enumerate(scenes):
            still = os.path.join(work, f"s{i}.png")
            ok = pollinations_still(sc["prompt"], seed + i * 37, still) or picsum_still(seed + i * 37, still)
            if not ok and last_good:
                still = last_good
            elif ok:
                last_good = still
            if not os.path.exists(still):
                raise RuntimeError("no image source available (network blocked?)")
            clip = os.path.join(work, f"c{i}.mp4")
            kenburns_clip(still, clip, d_scene, zoom_in=(i % 2 == 0))
            clips.append(clip)

        base = os.path.join(work, "base.mp4")
        xfade_chain(clips, d_scene, base)

        # 3) music bed + brand overlay
        music = os.path.join(work, "music.wav")
        synth_music(music, total + 1.0, job.get("mood", "calm"))
        brand = os.path.join(work, "brand.png")
        make_brand_png(job.get("brand", "fauxreel.vercel.app"), brand)

        # 4) final composite: burn captions (SRT) + brand overlay + VO + music.
        #    subtitles= chokes on Windows paths -> run from work dir, basename ref.
        # Karaoke word-pop captions (ASS, PlayRes 1080x1920). Font via fontsdir (cwd=work).
        ass = os.path.join(work, "subs.ass")
        srt_to_karaoke_ass(srt, ass)
        shutil.copy(FONT_PATH, os.path.join(work, "Montserrat-Bold.ttf"))
        fc = ("[0:v]ass=subs.ass:fontsdir=.[sv];"
              "[sv][1:v]overlay=0:0[v];"
              "[2:a]volume=1.0[voa];[3:a]volume=0.14[bg];"
              "[voa][bg]amix=inputs=2:duration=first:dropout_transition=0,"
              "afade=t=in:st=0:d=0.8,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        out_abs = os.path.abspath(out_path)
        cmd = [_ff(), "-y", "-i", os.path.abspath(base),
               "-loop", "1", "-framerate", str(FPS), "-t", f"{total:.3f}", "-i", os.path.abspath(brand),
               "-i", os.path.abspath(vo), "-i", os.path.abspath(music),
               "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-r", str(FPS),
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}",
               "-movflags", "+faststart", out_abs]
        # subs.srt lives in `work`; run from there so libass gets a bare relative path.
        run(cmd, cwd=work)
        return out_abs
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    demo = {
        "script": "Most people never start. They wait for the perfect moment. But the perfect moment is a myth. You build momentum by beginning, today, right now.",
        "voice": "en-US-JennyNeural",
        "rate": "+0%",
        "brand": "fauxreel.vercel.app",
        "mood": "drive",
        "scenes": [
            {"prompt": "lone figure walking up a misty mountain trail at sunrise, dramatic light"},
            {"prompt": "close up of hands typing on a laptop in a dark room, glowing screen, focused"},
            {"prompt": "city skyline at golden hour from a rooftop, aspirational, cinematic"},
        ],
    }
    out = os.path.join(HERE, "output", "demo_reel.mp4")
    path = render_video(demo, out)
    print("OUT=" + path)
    print("DUR=" + str(probe_dur(path)))
