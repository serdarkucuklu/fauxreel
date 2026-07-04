"""
worker — the render step that runs inside GitHub Actions (or locally).
Reads a job from the repository_dispatch client_payload (CI) or --job file (local),
fills gaps with scriptgen, renders with engine, writes output/render-<id>.mp4.
"""
import os, sys, json
import scriptgen, engine, story


def load_raw():
    if "--job" in sys.argv:
        with open(sys.argv[sys.argv.index("--job") + 1], encoding="utf-8") as f:
            return json.load(f)
    ev = os.environ.get("GITHUB_EVENT_PATH")
    if ev and os.path.exists(ev):
        with open(ev, encoding="utf-8") as f:
            return (json.load(f).get("client_payload") or {})
    raise SystemExit("no job (set --job <file> or run under GitHub Actions)")


def main():
    raw = load_raw()
    job_id = str(raw.get("id") or "local")
    os.makedirs(os.path.join(engine.HERE, "output"), exist_ok=True)
    out = os.path.join(engine.HERE, "output", f"render-{job_id}.mp4")

    if (raw.get("format") or "").lower() == "reddit":
        job = scriptgen.finalize_reddit_job(raw)
        print(f"[worker] id={job_id} REDDIT r/{job['subreddit']} title={job['title'][:60]}…")
        path = story.render_reddit_story(job, out)
    else:
        job = scriptgen.finalize_job(raw)
        print(f"[worker] id={job_id} REEL voice={job['voice']} mood={job['mood']} scenes={len(job['scenes'])}")
        path = engine.render_video(job, out)
    print("OUT=" + path)
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"video={path}\n")
            f.write(f"id={job_id}\n")


if __name__ == "__main__":
    main()
