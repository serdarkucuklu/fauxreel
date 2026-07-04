"""
Reddit-story render: card hook -> story over looping background + karaoke captions.
render_reddit_story(job, out) -> mp4. Reuses engine.py helpers + reddit.py card.
Background: Pexels portrait footage (if PEXELS_API_KEY) else keyless Pollinations fallback.
"""
import os, tempfile, shutil
import requests
import engine, reddit

W, H, FPS = engine.W, engine.H, engine.FPS


def _pexels_portrait(query, out_mp4, key):
    """Pexels Videos API — pick a vertical mp4 nearest 1080x1920 (avoid huge 4K downloads)."""
    try:
        r = requests.get("https://api.pexels.com/videos/search",
                         params={"query": query, "orientation": "portrait", "size": "large", "per_page": 30},
                         headers={"Authorization": key}, timeout=30)
        for v in r.json().get("videos", []):
            files = [f for f in v.get("video_files", [])
                     if f.get("file_type") == "video/mp4" and (f.get("height") or 0) > (f.get("width") or 0)]
            # prefer height >= 1080, then closest to 1920
            files.sort(key=lambda f: ((f.get("height") or 0) < 1080, abs((f.get("height") or 0) - 1920)))
            for f in files:
                if f.get("link"):
                    d = requests.get(f["link"], timeout=120)
                    if d.status_code == 200 and len(d.content) > 100000:
                        with open(out_mp4, "wb") as fp:
                            fp.write(d.content)
                        return True
    except Exception:
        pass
    return False


def _bg_fallback(query, out_mp4, seconds):
    still = out_mp4 + ".png"
    if not engine.pollinations_still(query + " abstract satisfying flowing gradient texture, motion", 777, still):
        engine.picsum_still(777, still)
    engine.kenburns_clip(still, out_mp4, min(8.0, max(4.0, seconds)), zoom_in=True)


def _bg_loop(src, out, seconds):
    engine.run([engine._ff(), "-y", "-stream_loop", "-1", "-i", src, "-t", f"{seconds:.3f}",
                "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1",
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-r", str(FPS), out])


def render_reddit_story(job, out_path):
    """
    job = { title, story, subreddit?, username?, upvotes?, comments?,
            voice?, rate?, mood?, brand?, bg_query?, pexels_key? }
    """
    work = tempfile.mkdtemp(prefix="rs_")
    try:
        voice = job.get("voice", "en-US-JennyNeural")
        rate = job.get("rate", "+0%")
        title = job["title"].strip()
        story = (job.get("story") or "").strip() or title

        # 1) two VO passes: title (hook) + body -> know the hook boundary exactly
        tvo = os.path.join(work, "t.mp3"); tsrt = os.path.join(work, "t.srt")
        engine.generate_voiceover(title, voice, rate, tvo, tsrt)
        hook = engine.probe_dur(tvo)
        bvo = os.path.join(work, "b.mp3"); bsrt = os.path.join(work, "b.srt")
        engine.generate_voiceover(story, voice, rate, bvo, bsrt)
        body_len = engine.probe_dur(bvo)
        total = hook + body_len + 0.3

        vo = os.path.join(work, "vo.mp3")
        engine.run([engine._ff(), "-y", "-i", tvo, "-i", bvo,
                    "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]", "-map", "[a]", vo])

        # 2) karaoke captions for the BODY, offset so they start when the body audio starts
        ass = os.path.join(work, "subs.ass")
        engine.srt_to_karaoke_ass(bsrt, ass, offset=hook)
        shutil.copy(engine.FONT_PATH, os.path.join(work, "Montserrat-Bold.ttf"))

        # 3) reddit card hook
        card = os.path.join(work, "card.png")
        reddit.make_reddit_card(card, title, job.get("subreddit", "AmItheAsshole"),
                                job.get("username", "throwaway_9281"), job.get("upvotes", "24.5k"),
                                job.get("comments", "1.2k"), theme="dark", width=980)

        # 4) background loop
        raw = os.path.join(work, "bg_raw.mp4"); bg = os.path.join(work, "bg.mp4")
        key = job.get("pexels_key") or os.environ.get("PEXELS_API_KEY")
        q = job.get("bg_query", "satisfying")
        if not (key and _pexels_portrait(q, raw, key)):
            _bg_fallback(q, raw, total)
        _bg_loop(raw, bg, total)

        # 5) music + brand
        music = os.path.join(work, "m.wav"); engine.synth_music(music, total + 1.0, job.get("mood", "drive"))
        brand = os.path.join(work, "brand.png"); engine.make_brand_png(job.get("brand", "fauxreel.vercel.app"), brand)

        # 6) composite: bg + card[0..hook, fade] + karaoke(body) + brand + VO + music
        fc = (
            f"[1:v]format=rgba,fade=t=out:st={max(0.1, hook - 0.35):.2f}:d=0.35:alpha=1[card];"
            f"[0:v][card]overlay=(W-w)/2:(H-h)/2:enable='lte(t,{hook:.2f})'[bv];"
            f"[bv]ass=subs.ass:fontsdir=.[cv];"
            f"[cv][2:v]overlay=0:0[v];"
            f"[3:a]volume=1.0[voa];[4:a]volume=0.12[bgm];"
            f"[voa][bgm]amix=inputs=2:duration=first:dropout_transition=0,afade=t=in:st=0:d=0.6,"
            f"loudnorm=I=-14:TP=-1.5:LRA=11[a]"
        )
        out_abs = os.path.abspath(out_path)
        cmd = [engine._ff(), "-y",
               "-i", os.path.abspath(bg),
               "-loop", "1", "-framerate", str(FPS), "-t", f"{total:.3f}", "-i", os.path.abspath(card),
               "-loop", "1", "-framerate", str(FPS), "-t", f"{total:.3f}", "-i", os.path.abspath(brand),
               "-i", os.path.abspath(vo), "-i", os.path.abspath(music),
               "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-r", str(FPS),
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}",
               "-movflags", "+faststart", out_abs]
        engine.run(cmd, cwd=work)
        return out_abs
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    demo = {
        "title": "AITA for telling my sister she can't bring her dog to my wedding?",
        "story": "My sister has a golden retriever she treats like her child. When I said no dogs at the venue, she called me heartless. Now half my family is texting me that I ruined her month. I just wanted one clean ceremony.",
        "upvotes": "31.2k", "comments": "4.8k", "voice": "en-US-JennyNeural", "mood": "drive",
    }
    out = os.path.join(engine.HERE, "output", "reddit_story.mp4")
    print("OUT=" + render_reddit_story(demo, out))
    print("DUR=" + str(engine.probe_dur(out)))
