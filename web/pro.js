/* FauxReel — freemium "Pro" unlock via LemonSqueezy license keys (client-side; CORS-verified).
   Pro removes the video watermark (app.js sends { pro:true }, the server omits the brand),
   and is your hook for HD / more renders. The payment provider is the backend — zero infra. */
(function () {
  "use strict";
  const CONFIG = {
    // Set after creating the "FauxReel Pro" LemonSqueezy product (license keys enabled):
    checkoutUrl: "https://fauxreel.lemonsqueezy.com/buy/PLACEHOLDER-PRODUCT-ID",
    validateUrl: "https://api.lemonsqueezy.com/v1/licenses/validate",
  };
  const STORE_KEY = "fauxreel_pro";
  const $ = (id) => document.getElementById(id);

  const isPro = () => !!localStorage.getItem(STORE_KEY);

  function applyState() {
    document.body.classList.toggle("pro", isPro());
    document.querySelectorAll("[data-pro-trigger]").forEach((el) => {
      el.textContent = isPro() ? "✓ Pro active — no watermark, HD" : "🔓 Pro — no watermark, HD, more renders";
    });
  }

  async function validate(key) {
    const res = await fetch(CONFIG.validateUrl, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ license_key: key }),
    });
    const data = await res.json().catch(() => ({}));
    return !!(data && data.valid);
  }

  let built = false;
  function buildModal() {
    if (built) return;
    const wrap = document.createElement("div");
    wrap.className = "pro-overlay";
    wrap.id = "pro-overlay";
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.innerHTML =
      '<div class="pro-modal">' +
      '<button class="pro-close" id="pro-close" type="button" aria-label="Close">&times;</button>' +
      '<h3>Go Pro</h3>' +
      '<p class="pro-sub">Clean exports (no <b>FauxReel</b> mark), HD, and more renders. One-time unlock.</p>' +
      '<a class="btn primary pro-buy" id="pro-buy" href="' + CONFIG.checkoutUrl + '" target="_blank" rel="noopener">Get Pro →</a>' +
      '<div class="pro-divider"><span>already bought?</span></div>' +
      '<div class="pro-activate"><input type="text" id="pro-key" placeholder="Paste your license key" autocomplete="off"><button class="btn" id="pro-activate" type="button">Activate</button></div>' +
      '<p class="pro-msg" id="pro-msg"></p>' +
      "</div>";
    document.body.appendChild(wrap);

    const close = () => wrap.classList.remove("open");
    $("pro-close").addEventListener("click", close);
    wrap.addEventListener("click", (e) => { if (e.target === wrap) close(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && wrap.classList.contains("open")) close(); });
    $("pro-activate").addEventListener("click", async () => {
      const key = $("pro-key").value.trim();
      const msg = $("pro-msg");
      if (!key) { msg.textContent = "Enter your license key."; msg.className = "pro-msg err"; return; }
      msg.textContent = "Checking…"; msg.className = "pro-msg";
      try {
        if (await validate(key)) {
          localStorage.setItem(STORE_KEY, key);
          applyState();
          msg.textContent = "Unlocked ✓ — your next renders are clean & HD."; msg.className = "pro-msg ok";
          setTimeout(close, 1400);
        } else {
          msg.textContent = "That key isn't valid. Check it and try again."; msg.className = "pro-msg err";
        }
      } catch (e) {
        msg.textContent = "Couldn't verify right now — check your connection."; msg.className = "pro-msg err";
      }
    });
    built = true;
  }

  function open() { buildModal(); $("pro-overlay").classList.add("open"); }

  function init() {
    applyState();
    document.querySelectorAll("[data-pro-trigger]").forEach((el) => el.addEventListener("click", open));
  }

  window.FauxReelPro = { init, open, isPro, _grant: (k) => { localStorage.setItem(STORE_KEY, k || "dev"); applyState(); }, _revoke: () => { localStorage.removeItem(STORE_KEY); applyState(); } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
