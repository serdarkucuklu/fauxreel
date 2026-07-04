/* FauxReel frontend. POST a job to /api/generate (which triggers the GitHub Actions
   render farm), then poll the returned public Release URL by trying to load the video.
   With no worker wired (static preview), it degrades to playing the bundled sample. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let MODE = "reel";
  const DEMO = { reel: "sample.mp4", reddit: "reddit_sample.mp4" };

  function job() {
    const common = { voice: $("voice").value, mood: $("mood").value, pro: !!localStorage.getItem("fauxreel_pro") };
    if (MODE === "reddit") {
      return Object.assign({ format: "reddit", title: $("rs-title").value.trim(),
        story: $("rs-story").value.trim(), subreddit: $("rs-sub").value.trim() }, common);
    }
    const text = $("script").value.trim();
    const scenes = $("scenes").value.split("\n").map((s) => s.trim()).filter(Boolean).map((p) => ({ prompt: p }));
    return Object.assign({ text, mode: text.split(/\s+/).length > 8 ? "script" : "topic", scenes }, common);
  }

  function busy(label) {
    $("video").style.display = "none";
    $("actions").style.display = "none";
    const ph = $("placeholder");
    ph.style.display = "";
    ph.innerHTML = '<div class="spinner"></div>' + (label || "Rendering…");
  }

  function showVideo(url) {
    const v = $("video");
    v.src = url;
    v.style.display = "";
    $("placeholder").style.display = "none";
    $("actions").style.display = "flex";
    $("download").href = url;
    v.play().catch(() => {});
  }

  // Poll a video URL by trying to load it; resolves the url when ready, null on timeout.
  function pollVideo(url, tries, interval) {
    return new Promise((resolve) => {
      let n = 0;
      const probe = () => {
        n++;
        const v = document.createElement("video");
        v.preload = "metadata";
        let done = false;
        v.onloadeddata = () => { if (!done) { done = true; resolve(url); } };
        v.onerror = () => {
          if (done) return;
          done = true;
          if (n >= tries) resolve(null);
          else setTimeout(probe, interval);
        };
        v.src = url + (url.includes("?") ? "&" : "?") + "cb=" + Date.now();
      };
      probe();
    });
  }

  async function generate() {
    const btn = $("gen");
    btn.disabled = true;
    busy("Sending to the render farm…");
    try {
      const res = await fetch("/api/generate", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(job()),
      });
      if (!res.ok) throw new Error("no worker");
      const { resultUrl } = await res.json();
      busy("Rendering your video… this usually takes a couple of minutes.");
      const url = await pollVideo(resultUrl, 160, 5000); // ~13 min ceiling
      if (!url) throw new Error("timed out");
      showVideo(url);
    } catch (e) {
      $("demo-banner").textContent = "Preview: showing a real sample rendered by the engine. Live generation runs on the render worker.";
      setTimeout(() => showVideo(DEMO[MODE] || DEMO.reel), 1400);
    } finally {
      btn.disabled = false;
    }
  }

  $("mode-seg").addEventListener("click", (e) => {
    const b = e.target.closest("[data-mode]"); if (!b) return;
    MODE = b.dataset.mode;
    document.querySelectorAll("#mode-seg .mode-btn").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    document.querySelectorAll(".reel-only").forEach((el) => { el.style.display = MODE === "reel" ? "" : "none"; });
    document.querySelectorAll(".reddit-only").forEach((el) => { el.style.display = MODE === "reddit" ? "" : "none"; });
    $("gen").textContent = MODE === "reddit" ? "👽 Generate Reddit video" : "✨ Generate video";
  });

  $("gen").addEventListener("click", generate);
  $("regen").addEventListener("click", generate);
  // The Pro trigger (watermark removal / HD) is handled by pro.js via [data-pro-trigger].
})();
