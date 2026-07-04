"""
scriptgen — turn a bare TOPIC into a {script, scenes[]} job, or fill in missing
scene prompts for a user-supplied SCRIPT. Gemini free-tier when GEMINI_API_KEY is
set; otherwise a curated keyless fallback so a render never blocks on the LLM.
"""
import os, re, json, hashlib
try:
    import truststore; truststore.inject_into_ssl()
except Exception:
    pass
try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except Exception:
    pass
import requests

GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]

# Generic cinematic scene prompts reused when we can't derive better ones (keyless).
GENERIC_SCENES = [
    "cinematic wide shot, lone figure walking toward the horizon at sunrise, volumetric light, 9:16",
    "close-up of focused hands working, dramatic rim light, shallow depth of field, cinematic 9:16",
    "sweeping aerial of a vast landscape at golden hour, aspirational, cinematic color grade, 9:16",
    "slow push-in on a calm determined face, soft window light, film grain, cinematic 9:16",
]


def _extract_json(text):
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _gemini(topic, want_script):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    if want_script:
        instr = ("Write a punchy 30-45 word first-person motivational/educational voiceover script for a "
                 f"faceless vertical short about: \"{topic}\". Then 4 vivid English AI image prompts (cinematic, "
                 "vertical 9:16) that illustrate it. Return STRICT JSON: "
                 '{"script":"...","scenes":[{"prompt":"..."},{"prompt":"..."},{"prompt":"..."},{"prompt":"..."}]}')
    else:
        instr = (f"For this short-video script: \"{topic}\" — return 4 vivid English AI image prompts "
                 "(cinematic, vertical 9:16) that illustrate it, as STRICT JSON: "
                 '{"scenes":[{"prompt":"..."},{"prompt":"..."},{"prompt":"..."},{"prompt":"..."}]}')
    body = {"contents": [{"parts": [{"text": instr}]}]}
    for model in GEMINI_MODELS:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            r = requests.post(url, json=body, timeout=45)
            if r.status_code != 200:
                continue
            txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            data = _extract_json(txt)
            if data and (data.get("scenes")):
                return data
        except Exception:
            continue
    return None


def _fallback_script(topic):
    t = topic.strip().rstrip(".")
    return (f"Here's the truth about {t}. Most people overthink it and never begin. "
            f"But momentum only comes from action. Start small, start today, and let consistency do the rest.")


def finalize_job(raw):
    """
    raw = { text, mode: "topic"|"script", voice?, rate?, mood?, brand?, scenes?:[str|{prompt}] }
    -> job = { script, voice, rate, brand, mood, scenes:[{prompt}] }
    """
    text = (raw.get("text") or "").strip()
    mode = raw.get("mode") or ("topic" if len(text.split()) <= 8 else "script")

    # normalize any user-provided scene prompts
    scenes = []
    for s in (raw.get("scenes") or []):
        p = s.get("prompt") if isinstance(s, dict) else str(s)
        if p and p.strip():
            scenes.append({"prompt": p.strip()})

    script = text if mode == "script" else ""

    # need a script (topic mode) and/or scenes -> try Gemini, then fallback
    if mode == "topic" or not scenes:
        g = _gemini(text, want_script=(mode == "topic"))
        if g:
            if mode == "topic" and g.get("script"):
                script = g["script"].strip()
            if not scenes and g.get("scenes"):
                scenes = [{"prompt": (x.get("prompt") if isinstance(x, dict) else str(x)).strip()} for x in g["scenes"] if x]

    if not script:
        script = _fallback_script(text or "getting started")
    if not scenes:
        # deterministic pick from the generic pool so different topics vary a little
        seed = int(hashlib.md5((text or script).encode()).hexdigest()[:4], 16)
        rot = seed % len(GENERIC_SCENES)
        scenes = [{"prompt": GENERIC_SCENES[(rot + i) % len(GENERIC_SCENES)]} for i in range(3)]

    return {
        "script": script,
        "voice": raw.get("voice") or "en-US-JennyNeural",
        "rate": raw.get("rate") or "+0%",
        "brand": raw.get("brand", "fauxreel.vercel.app"),
        "mood": raw.get("mood") or "drive",
        "scenes": scenes[:5],
    }


if __name__ == "__main__":
    import sys
    demo = {"text": sys.argv[1] if len(sys.argv) > 1 else "discipline beats motivation", "mode": "topic"}
    print(json.dumps(finalize_job(demo), indent=2, ensure_ascii=False))
