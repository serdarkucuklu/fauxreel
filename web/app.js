/* FauxReel frontend. POST a job to /api/generate (which triggers the GitHub Actions
   render farm), then poll the returned public Release URL by trying to load the video.
   With no worker wired (static preview), it degrades to playing the bundled sample. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const DEMO_SRC = "sample.mp4";

  function job() {
    const text = $("script").value.trim();
    const scenes = $("scenes").value.split("\n").map((s) => s.trim()).filter(Boolean).map((p) => ({ prompt: p }));
    return {
      text,
      mode: text.split(/\s+/).length > 8 ? "script" : "topic",
      voice: $("voice").value,
      mood: $("mood").value,
      scenes,
      pro: !!localStorage.getItem("fauxreel_pro"),
    };
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
      $("demo-banner").textContent = "Preview mode: showing a real sample rendered by the engine. Deploy the render worker (ARCHITECTURE.md) to generate from your own script.";
      setTimeout(() => showVideo(DEMO_SRC), 1400);
    } finally {
      btn.disabled = false;
    }
  }

  $("gen").addEventListener("click", generate);
  $("regen").addEventListener("click", generate);
  $("prolink").addEventListener("click", () => {
    // Freemium: same LemonSqueezy license pattern as FauxPost (wire the checkout URL when live).
    // Pro removes the watermark (server honors { pro:true }) and unlocks more/HD renders.
    window.open("https://fauxreel.lemonsqueezy.com/buy/PLACEHOLDER-PRODUCT-ID", "_blank");
  });
})();
