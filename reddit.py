"""
Reddit post-card renderer (the iconic story-video hook).
Draws a clean r/... post card as a transparent PNG to overlay on the background
during the hook while the voiceover reads the title. PIL only (no network).
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "assets", "Montserrat-Bold.ttf")

THEMES = {
    "dark":  {"card": (26, 26, 27, 255), "title": (215, 218, 220), "meta": (129, 131, 132),
              "up": (255, 69, 0), "chip": (52, 53, 54)},
    "light": {"card": (255, 255, 255, 255), "title": (26, 26, 27), "meta": (120, 124, 126),
              "up": (255, 69, 0), "chip": (237, 239, 241)},
}


def _font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_reddit_card(out_png, title, subreddit="AmItheAsshole", username="throwaway_9281",
                     upvotes="24.5k", comments="1.2k", theme="dark", width=980):
    t = THEMES.get(theme, THEMES["dark"])
    pad = 44
    inner = width - pad * 2
    f_meta = _font(30)
    f_title = _font(50)
    f_stat = _font(30)

    # measure title
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    lines = _wrap(tmp, title, f_title, inner)
    title_lh = f_title.getbbox("Ay")[3] + 12
    title_h = len(lines) * title_lh

    top_h = 60          # subreddit row (avatar 48)
    stats_h = 54
    gaps = 26 + 30
    height = pad + top_h + gaps + title_h + stats_h + pad

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, width - 1, height - 1], radius=28, fill=t["card"])

    x = pad
    y = pad
    # avatar (subreddit) — filled circle with white glyph
    d.ellipse([x, y, x + 48, y + 48], fill=t["up"])
    gl = subreddit[0].upper()
    gb = d.textbbox((0, 0), gl, font=_font(28))
    d.text((x + 24 - (gb[2] - gb[0]) / 2, y + 24 - (gb[3] - gb[1]) / 2 - gb[1]), gl, font=_font(28), fill=(255, 255, 255))
    # subreddit + user + time
    d.text((x + 62, y + 2), f"r/{subreddit}", font=f_meta, fill=t["title"])
    sw = d.textlength(f"r/{subreddit}", font=f_meta)
    d.text((x + 62, y + 30), f"u/{username} · 5h", font=_font(24), fill=t["meta"])

    # title
    y += top_h + 26
    for ln in lines:
        d.text((pad, y), ln, font=f_title, fill=t["title"])
        y += title_lh

    # stats row: upvote ▲ count  · comment count · share
    y += 30
    cx = pad
    # up arrow (triangle)
    d.polygon([(cx, y + 26), (cx + 22, y + 26), (cx + 11, y + 6)], fill=t["up"])
    cx += 32
    d.text((cx, y + 2), upvotes, font=f_stat, fill=t["meta"]); cx += d.textlength(upvotes, font=f_stat) + 40
    # comment bubble (rounded rect outline)
    d.rounded_rectangle([cx, y + 4, cx + 30, y + 26], radius=7, outline=t["meta"], width=3)
    cx += 40
    d.text((cx, y + 2), comments, font=f_stat, fill=t["meta"]); cx += d.textlength(comments, font=f_stat) + 40
    d.text((cx, y + 2), "Share", font=f_stat, fill=t["meta"])

    img.save(out_png)
    return out_png, (width, height)


if __name__ == "__main__":
    out = os.path.join(HERE, "output", "reddit_card.png")
    make_reddit_card(out, "AITA for telling my sister she can't bring her dog to my wedding?",
                     upvotes="31.2k", comments="4.8k", theme="dark")
    print("OUT=" + out)
