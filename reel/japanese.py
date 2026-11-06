"""Latest videos from daily Japanese YouTube channels.

Speak Japanese Naturally, its podcast channel, Japanese with Shun, then Ken
(けんさんおかえり Japanese), in that order. The public videos tab is the
source: the guest RSS feed answers 404 from here.
"""

import json
import math
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import cairo
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GdkPixbuf, Pango, PangoCairo

from .core import (
    DATE,
    DUR,
    H,
    INK as _CORE_INK,
    W,
    draw_copyright,
    icon_key,
    layout,
    mix,
    palette_at,
    pretty_date,
    rgb,
    show,
)

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# Order is fixed: Speak Japanese Naturally, its podcast, Shun, Ken. Ken is the
# immersion channel けんさんおかえり Japanese, not the one-video "Japanese
# with ken" handle. Shun is Japanese with Shun. The podcast is the separate
# intermediate/advanced channel, not a playlist on the main one.
CHANNELS = (
    {"name": "Speak Japanese Naturally", "handle": "SpeakJapaneseNaturally"},
    {"name": "Podcast", "handle": "SpeakJapaneseNaturallyPodcast"},
    {"name": "Shun", "handle": "JapanesewithShun"},
    {"name": "Ken", "handle": "kensanokaeri"},
)

CARD_W = 960
CARD_H = 348
PAGE_LIMIT = 4


def page_channel_title(page, handle):
    match = re.search(
        r'"channelMetadataRenderer":\{"title":"((?:\\.|[^"\\])*)"',
        page,
    )
    if not match:
        match = re.search(r'property="og:title" content="([^"]+)"', page)
    if not match:
        raise RuntimeError(f"channel name missing for @{handle}")
    raw = match.group(1)
    name = json.loads(f'"{raw}"') if "\\" in raw else raw
    name = re.sub(r"\s+-\s+YouTube$", "", name).strip()
    if not name:
        raise RuntimeError(f"empty channel name for @{handle}")
    return name


def tokyo_now():
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Asia/Tokyo"))


def fetch_html(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (429, 500, 502, 503):
                raise
            time.sleep(1.2 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(0.8 * (attempt + 1))
    raise last


def initial_data(page):
    match = re.search(r"var ytInitialData = (\{.*?\});</script>", page)
    if not match:
        raise RuntimeError("no ytInitialData")
    return json.loads(match.group(1))


def lockups(data):
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "lockupViewModel" in node:
                found.append(node["lockupViewModel"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return found


def age_phrase(lock):
    meta = lock.get("metadata", {}).get("lockupMetadataViewModel", {})
    rows = (
        meta.get("metadata", {})
        .get("contentMetadataViewModel", {})
        .get("metadataRows", [])
    )
    for row in rows:
        for part in row.get("metadataParts", []):
            text = part.get("text") or {}
            label = text.get("accessibilityLabel") or text.get("content") or ""
            if re.search(r"ago", label, re.I):
                return label
    return ""


def age_seconds(phrase):
    text = re.sub(r"\s+", " ", (phrase or "").lower()).strip()
    units = (
        ("second", 1),
        ("sec", 1),
        ("minute", 60),
        ("min", 60),
        ("hour", 3600),
        ("hr", 3600),
        ("week", 7 * 86400),
        ("month", 30 * 86400),
        ("year", 365 * 86400),
        ("day", 86400),
        ("h", 3600),
        ("d", 86400),
        ("w", 7 * 86400),
        ("m", 60),
        ("s", 1),
    )
    pattern = r"(\d+)\s*(" + "|".join(name for name, _ in units) + r")s?\b"
    match = re.search(pattern, text)
    if match:
        span = dict(units)[match.group(2)]
        return int(match.group(1)) * span
    if "yesterday" in text:
        return 86400
    return None


def badge_label(phrase):
    text = re.sub(r"\s+", " ", phrase or "").strip()
    short = re.fullmatch(r"(\d+)\s*([smhdw])\s*ago", text, re.I)
    if short:
        count = int(short.group(1))
        unit = {"s": "SECOND", "m": "MINUTE", "h": "HOUR", "d": "DAY", "w": "WEEK"}[
            short.group(2).lower()
        ]
        if count != 1:
            unit += "S"
        return f"{count} {unit} AGO"
    return text.upper() if text else "LATEST"


def plain(text):
    cleaned = re.sub(
        r"[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]",
        "",
        text or "",
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def row_font(text):
    if any(ord(ch) > 0x2E80 for ch in text or ""):
        return "Noto Sans CJK HK"
    return "Lato"


def thumb_path(video_id):
    folder = os.path.join(tempfile.gettempdir(), "japanese-yt-thumbs")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{video_id}-hq.jpg")
    if os.path.isfile(path) and os.path.getsize(path) > 400:
        return path
    url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    if not data.startswith(b"\xff\xd8"):
        raise RuntimeError("not a jpeg")
    with open(path, "wb") as handle:
        handle.write(data)
    GdkPixbuf.Pixbuf.new_from_file_at_size(path, 64, 64)
    return path


def mark_path(name):
    folder = os.path.join(tempfile.gettempdir(), "japanese-yt-thumbs")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"mark-{re.sub(r'[^A-Za-z0-9]+', '-', name)}.png")
    if os.path.isfile(path):
        return path
    size = 320
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, 180)
    ctx = cairo.Context(surface)
    hue = palette_at((sum(ord(ch) for ch in name) % 100) / 100.0)
    ctx.set_source_rgb(*mix(hue, (0.12, 0.16, 0.28), 0.35))
    ctx.rectangle(0, 0, size, 180)
    ctx.fill()
    label = name[:2] if len(name) > 2 else name
    lay = layout(ctx, label, 64, "bold", font=row_font(label))
    tw, th = lay.get_pixel_size()
    ctx.set_source_rgb(1, 1, 1)
    ctx.move_to((size - tw) / 2, (180 - th) / 2)
    PangoCairo.show_layout(ctx, lay)
    surface.write_to_png(path)
    return path


def fetch_latest(channel):
    page = fetch_html(f"https://www.youtube.com/@{channel['handle']}/videos")
    title_name = page_channel_title(page, channel["handle"])
    found = lockups(initial_data(page))
    if not found:
        raise RuntimeError("no videos")
    lock = found[0]
    video_id = lock.get("contentId") or ""
    if not re.fullmatch(r"[0-9A-Za-z_-]{11}", video_id):
        raise RuntimeError("no video id")
    title = (
        lock.get("metadata", {})
        .get("lockupMetadataViewModel", {})
        .get("title", {})
        .get("content")
        or channel["name"]
    )
    return {
        "name": channel["name"],
        "channel": title_name,
        "title": plain(title) or channel["name"],
        "ago": age_phrase(lock),
        "id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


def pack(row, now):
    secs = age_seconds(row.get("ago"))
    posted = now - timedelta(seconds=secs) if secs is not None else None
    fresh = bool(posted and posted.date() == now.date())
    yesterday = bool(posted and posted.date() == (now.date() - timedelta(days=1)))
    try:
        icon = thumb_path(row["id"])
    except Exception as exc:
        print(f"japanese: thumb {row['id']} failed: {exc}", flush=True)
        icon = mark_path(row["name"])
    return {
        "name": row["title"],
        "version": row["name"],
        "published": row.get("ago") or "",
        "day": posted.date().isoformat() if posted else now.date().isoformat(),
        "fresh": fresh,
        "yesterday": yesterday,
        "icon": f"yt-{row['id']}",
        "icon_path": icon,
        "channel": row.get("channel") or row["name"],
        "badge": badge_label(row.get("ago")),
        "url": row.get("url") or "",
        "age": secs if secs is not None else 10**12,
        "quiet": False,
    }


def quiet_item(today):
    return {
        "name": "No new videos",
        "version": "YouTube",
        "published": today,
        "day": today,
        "fresh": False,
        "yesterday": False,
        "icon": "yt-quiet",
        "icon_path": mark_path("JP"),
        "channel": "Daily Japanese",
        "badge": "QUIET",
        "url": "",
        "age": 0,
        "quiet": True,
    }


def load_japanese(now=None):
    now = now or tokyo_now()
    today = now.strftime("%Y-%m-%d")
    rows = []
    for channel in CHANNELS:
        row = None
        last = None
        for attempt in range(3):
            try:
                row = fetch_latest(channel)
                break
            except Exception as exc:
                last = exc
                print(f"japanese: {channel['name']} failed: {exc}", flush=True)
                time.sleep(0.8 * (attempt + 1))
        if row:
            rows.append(row)
            print(f"japanese: {row['channel']}  {row['ago'] or 'latest'}", flush=True)
        else:
            print(f"japanese: {channel['name']} skipped: {last}", flush=True)
        time.sleep(0.35)
    if not rows:
        print("japanese: no videos", flush=True)
        return [quiet_item(today)], today
    items = [pack(row, now) for row in rows]
    new = sum(1 for item in items if item["fresh"])
    print(f"japanese: {len(items)} channels, {new} new on {today}", flush=True)
    return items, today


def clip_length(items):
    real = [item for item in items if not item.get("quiet")]
    pages = 1 if len(real) <= PAGE_LIMIT else (len(real) + PAGE_LIMIT - 1) // PAGE_LIMIT
    return max(DUR, pages * 4.0)


def bg(ctx, t):
    from .seascape import paint

    paint(ctx, W, H, t)


def tracked(ctx, text, size, weight, font, spacing):
    lay = layout(ctx, text, size, weight, font=font)
    attrs = Pango.AttrList()
    attrs.insert(Pango.attr_letter_spacing_new(int(spacing * Pango.SCALE)))
    lay.set_attributes(attrs)
    return lay


INK = (0.03, 0.06, 0.16)


def glass_fill(ctx, x, y, w, h, strength=1.0):
    """Clear glass. The pale hide shows through. Type stays solid."""
    ctx.save()
    ctx.rectangle(x + 3, y + 6, w, h)
    ctx.set_source_rgba(0.35, 0.48, 0.72, 0.10 * strength)
    ctx.fill()
    ctx.restore()

    ctx.save()
    ctx.rectangle(x, y, w, h)
    ctx.clip()
    veil = cairo.LinearGradient(x, y, x, y + h)
    veil.add_color_stop_rgba(0.00, 1.00, 1.00, 1.00, 0.16 * strength)
    veil.add_color_stop_rgba(0.42, 0.94, 0.97, 1.00, 0.05 * strength)
    veil.add_color_stop_rgba(1.00, 0.86, 0.92, 1.00, 0.12 * strength)
    ctx.set_source(veil)
    ctx.paint()
    sheen = cairo.LinearGradient(x, y, x, y + h * 0.22)
    sheen.add_color_stop_rgba(0.00, 1, 1, 1, 0.42 * strength)
    sheen.add_color_stop_rgba(1.00, 1, 1, 1, 0.00)
    ctx.set_source(sheen)
    ctx.rectangle(x, y, w, h * 0.22)
    ctx.fill()
    ctx.set_source_rgba(1, 1, 1, 0.85)
    ctx.rectangle(x, y, w, 1.5)
    ctx.fill()
    ctx.restore()

    ctx.rectangle(x + 0.75, y + 0.75, max(0, w - 1.5), max(0, h - 1.5))
    ctx.set_source_rgba(1, 1, 1, 0.72)
    ctx.set_line_width(1.5)
    ctx.stroke()


def show_ink(ctx, lay, x, y):
    """Crisp ink. A short light shadow, not a stroke that fattens the letters."""
    ctx.save()
    rgb(ctx, (1, 1, 1), 0.80)
    ctx.move_to(x + 1, y + 1)
    PangoCairo.show_layout(ctx, lay)
    ctx.move_to(x, y)
    rgb(ctx, INK)
    PangoCairo.show_layout(ctx, lay)
    ctx.restore()


def letter_ink(turn):
    """Saturated jewel. Bright on the pale field, never washed out to white."""
    if turn < 1.0 / 3.0:
        return mix((0.00, 0.38, 0.92), (0.14, 0.16, 0.90), turn * 3.0)
    if turn < 2.0 / 3.0:
        return mix((0.14, 0.16, 0.90), (0.46, 0.06, 0.86), (turn - 1.0 / 3.0) * 3.0)
    return mix((0.46, 0.06, 0.86), (0.00, 0.38, 0.92), (turn - 2.0 / 3.0) * 3.0)


def letter_phase(index):
    """Irregular offsets. Neighbors do not change together, and nothing travels."""
    return ((index * 5 + 3) * 47 % 360) / 360.0


def show_header_title(ctx, lay, x, y, t, size, font):
    """Jewel letters with a diamond facet that walks across the title.

    Resting color stays saturated cyan / cobalt / violet. The motion is a
    bright facet inside the glyphs, the same kind of sweep the other series
    use, clipped so nothing appears around the words.
    """
    text = lay.get_text()
    ctx.save()
    byte = 0
    glyphs = []
    for i, ch in enumerate(text):
        n = len(ch.encode("utf-8"))
        if ch not in " \n":
            glyphs.append((i, ch, lay.index_to_pos(byte)))
        byte += n

    # Three facets on the words at once, a third of the title apart, all
    # walking left to right. They wrap, so the title always shows three.
    sweep = (t / 4.0) % 1.0
    centers = []
    for _i, _ch, rect in glyphs:
        centers.append(rect.x / Pango.SCALE)
    title_w = max(1.0, (centers[-1] - centers[0]) if centers else 1.0)
    reach = max(28.0, title_w * 0.055)
    for i, ch, rect in glyphs:
        phase = letter_phase(i)
        turn = ((t / 4.0) + phase) % 1.0
        ink = letter_ink(turn)
        hi = mix(ink, (1, 1, 1), 0.28)
        lo = mix(ink, (0.02, 0.04, 0.16), 0.38)
        one = layout(ctx, ch, size, "bold", font=font)
        lx = x + rect.x / Pango.SCALE
        ly = y + rect.y / Pango.SCALE
        pix, _logical = one.get_pixel_extents()
        cx = lx + pix.x + pix.width / 2.0
        top = ly + pix.y
        bot = top + max(1.0, pix.height)
        gw = max(8.0, pix.width)

        ctx.push_group()
        ctx.set_source_rgba(1, 1, 1, 1)
        ctx.move_to(lx, ly)
        PangoCairo.show_layout(ctx, one)
        mask = ctx.pop_group()

        edge = mix(ink, (0.02, 0.05, 0.16), 0.78)
        for ox, oy in ((-1.7, 0), (1.7, 0), (0, -1.7), (0, 1.7)):
            ctx.save()
            ctx.translate(ox, oy)
            ctx.set_source_rgba(*edge, 0.92)
            ctx.mask(mask)
            ctx.restore()

        shade = cairo.LinearGradient(cx, top, cx, bot)
        shade.add_color_stop_rgb(0.0, *hi)
        shade.add_color_stop_rgb(0.48, *ink)
        shade.add_color_stop_rgb(1.0, *lo)
        ctx.set_source(shade)
        ctx.mask(mask)

        # Three facets, a third of the title apart, moving left to right together.
        rel = (rect.x / Pango.SCALE) - centers[0]
        hot = 0.0
        for k in range(3):
            pos = (sweep * title_w + k * title_w / 3.0) % title_w
            dist = abs(rel - pos)
            dist = min(dist, title_w - dist)
            hot = max(hot, max(0.0, 1.0 - dist / reach) ** 1.15)
        if hot > 0.04:
            ctx.save()
            # Clip to this glyph so the flash cannot spill into the background.
            ctx.rectangle(lx + pix.x - 1, top - 1, gw + 2, (bot - top) + 2)
            ctx.clip()
            # Diagonal facet, the way a diamond throws light, not a flat wash.
            band = cairo.LinearGradient(cx - gw, top, cx + gw * 0.35, bot)
            gleam = mix(ink, (1, 1, 1), 0.72)
            band.add_color_stop_rgba(0.00, *gleam, 0.0)
            band.add_color_stop_rgba(0.38, *gleam, 0.35 * hot)
            band.add_color_stop_rgba(0.50, 1, 1, 1, 0.92 * hot)
            band.add_color_stop_rgba(0.62, *gleam, 0.35 * hot)
            band.add_color_stop_rgba(1.00, *gleam, 0.0)
            ctx.set_source(band)
            ctx.mask(mask)
            ctx.restore()
    ctx.restore()


def paint_header_gem(ctx, cx, cy, rx, ry, turn, t, phase):
    """A diamond that stays put. Color turns, and a glint walks its edges."""
    ink = gem_color((turn + phase) % 1.0)
    pulse = 0.5 + 0.5 * math.sin((t / 4.0 + phase) * math.tau)
    breathe = 0.84 + 0.16 * pulse
    rx *= breathe
    ry *= breathe
    diamond(ctx, cx, cy, rx, ry)
    top = mix(ink, (1, 1, 1), 0.42)
    bot = mix(ink, (0.04, 0.08, 0.20), 0.28)
    shade = cairo.LinearGradient(cx, cy - ry, cx, cy + ry)
    shade.add_color_stop_rgba(0.0, *top, 0.96)
    shade.add_color_stop_rgba(0.48, *ink, 0.96)
    shade.add_color_stop_rgba(1.0, *bot, 0.96)
    ctx.set_source(shade)
    ctx.fill_preserve()
    ctx.set_source_rgba(*mix(ink, (1, 1, 1), 0.2), 0.95)
    ctx.set_line_width(1.3)
    ctx.stroke()
    spin = (t / 4.0 + phase) % 1.0
    verts = ((cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy))
    for i in range(4):
        dist = abs(spin - i / 4.0)
        dist = min(dist, 1.0 - dist)
        hot = max(0.0, 1.0 - dist * 4.0) ** 1.4
        ctx.move_to(*verts[i])
        ctx.line_to(*verts[(i + 1) % 4])
        ctx.set_source_rgba(1, 1, 1, 0.12 + 0.88 * hot)
        ctx.set_line_width(2.1)
        ctx.stroke()


def diamond(ctx, cx, cy, rx, ry):
    ctx.new_path()
    ctx.move_to(cx, cy - ry)
    ctx.line_to(cx + rx, cy)
    ctx.line_to(cx, cy + ry)
    ctx.line_to(cx - rx, cy)
    ctx.close_path()


def gem_color(turn):
    """Saturated cyan, cobalt, violet. Brighter than the milky hide."""
    if turn < 1.0 / 3.0:
        return mix((0.00, 0.62, 1.00), (0.22, 0.32, 1.00), turn * 3.0)
    if turn < 2.0 / 3.0:
        return mix((0.22, 0.32, 1.00), (0.55, 0.18, 1.00), (turn - 1.0 / 3.0) * 3.0)
    return mix((0.55, 0.18, 1.00), (0.00, 0.62, 1.00), (turn - 2.0 / 3.0) * 3.0)


def draw_header(ctx, today, t, title, new):
    """Open masthead. Title letters and the two diamonds change color in place."""
    turn = (t / 4.0) % 1.0

    gem_rx, gem_ry = 18, 26
    gap = 28
    side = 28 + gem_rx + gap
    max_w = W - side * 2
    size = 68
    font = "Noto Serif CJK JP"
    title_lay = tracked(ctx, title or "", size, "bold", font, 1.4)
    while size > 46 and title_lay.get_pixel_size()[0] > max_w:
        size -= 1
        title_lay = tracked(ctx, title or "", size, "bold", font, 1.4)
    tw, th = title_lay.get_pixel_size()

    title_y = 46
    gem_cy = title_y + th * 0.52
    left_gem = (W - tw) / 2 - gap - gem_rx
    right_gem = (W + tw) / 2 + gap + gem_rx
    ctx.save()
    for i, gx in enumerate((left_gem, right_gem)):
        paint_header_gem(ctx, gx, gem_cy, gem_rx * 1.2, gem_ry * 1.2, turn, t, i * 0.37)
    ctx.restore()
    show_header_title(ctx, title_lay, (W - tw) / 2, title_y, t, size, font)

    date = pretty_date(today)
    d_lay = tracked(ctx, date, 42, "bold", "Lato", 2.6)
    dw, dh = d_lay.get_pixel_size()
    date_y = title_y + th + 14
    show_ink(ctx, d_lay, (W - dw) / 2, date_y)
    return date_y + dh + 18


def ellipsize(ctx, text, size, width, font):
    if layout(ctx, text, size, "bold", font=font).get_pixel_size()[0] <= width:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        trial = text[:mid].rstrip() + "…"
        if layout(ctx, trial, size, "bold", font=font).get_pixel_size()[0] <= width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + "…"


def title_markup(text):
    """Break a full title on its own dividers, never drop characters."""
    parts = [part.strip() for part in re.split(r"\s*[|｜/]\s*", text or "") if part.strip()]
    if len(parts) < 2:
        return text or ""
    return "\n".join(parts)


def wrapped(ctx, text, size, width, font):
    """Full title. Wrap, never cut with an ellipsis."""
    lay = layout(ctx, title_markup(text), size, "bold", width=width, font=font)
    lay.set_wrap(Pango.WrapMode.WORD_CHAR)
    lay.set_ellipsize(Pango.EllipsizeMode.NONE)
    _ink, logical = lay.get_pixel_extents()
    return lay, logical.height


def fit_title(ctx, text, width, max_h, font, start=36, floor=18):
    """Shrink only until every character of the title fits in the card."""
    size = start
    lay, height = wrapped(ctx, text, size, width, font)
    while size > floor and height > max_h:
        size -= 1
        lay, height = wrapped(ctx, text, size, width, font)
    return lay, height, size


def paint_thumb(ctx, pb, x, y, w, h):
    ctx.save()
    ctx.rectangle(x, y, w, h)
    ctx.clip()
    scale = max(w / pb.get_width(), h / pb.get_height())
    tw, th = pb.get_width() * scale, pb.get_height() * scale
    ctx.translate(x + (w - tw) / 2, y + (h - th) / 2)
    ctx.scale(scale, scale)
    Gdk.cairo_set_source_pixbuf(ctx, pb, 0, 0)
    ctx.paint()
    ctx.restore()
    ctx.rectangle(x, y, w, h)
    ctx.set_source_rgba(1, 1, 1, 0.55)
    ctx.set_line_width(1.5)
    ctx.stroke()


def glass_pane(ctx, x, y, w, h):
    """Clear square pane. The pale hide shows through, type stays readable."""
    glass_fill(ctx, x, y, w, h, strength=1.0)


def age_chip_size(ctx, text, size=22):
    lay = layout(ctx, text, size, "bold")
    tw, th = lay.get_pixel_size()
    gem, gap, pad_x, pad_y = 14, 10, 12, 8
    return tw + pad_x + gem + gap + pad_x, max(th, gem) + pad_y * 2


def draw_age_chip(ctx, text, right, y, t, size=22, phase=0.0):
    """Clear age chip. The words stay put. The diamond turns color, and a
    glint travels around it, in the same cyan, cobalt, and violet as the hide.
    """
    lay = layout(ctx, text, size, "bold")
    tw, th = lay.get_pixel_size()
    bw, bh = age_chip_size(ctx, text, size)
    x = right - bw
    glass_fill(ctx, x, y, bw, bh, strength=0.72)

    turn = (t / 2.4 + phase) % 1.0
    if turn < 1.0 / 3.0:
        gem_color = mix((0.28, 0.72, 0.98), (0.34, 0.48, 0.96), turn * 3.0)
    elif turn < 2.0 / 3.0:
        gem_color = mix((0.34, 0.48, 0.96), (0.52, 0.40, 0.92), (turn - 1.0 / 3.0) * 3.0)
    else:
        gem_color = mix((0.52, 0.40, 0.92), (0.28, 0.72, 0.98), (turn - 2.0 / 3.0) * 3.0)
    pulse = 0.5 + 0.5 * math.sin((t / 2.4 + phase) * math.tau)

    ctx.save()
    ctx.rectangle(x, y, bw, bh)
    ctx.clip()
    sweep = (t * 0.42 + phase) % 1.0
    sx = x + (sweep * 1.7 - 0.35) * bw
    shine = cairo.LinearGradient(sx, y, sx + bw * 0.22, y + bh)
    shine.add_color_stop_rgba(0.00, 1, 1, 1, 0.00)
    shine.add_color_stop_rgba(0.50, 1, 1, 1, 0.42)
    shine.add_color_stop_rgba(1.00, 1, 1, 1, 0.00)
    ctx.set_source(shine)
    ctx.paint()
    ctx.restore()

    ctx.save()
    bar = 0.55 + 0.45 * pulse
    ctx.set_source_rgba(gem_color[0], gem_color[1], gem_color[2], bar)
    ctx.set_line_width(2.4)
    ctx.move_to(x, y + 6)
    ctx.line_to(x, y + bh - 6)
    ctx.stroke()

    gem, gap, pad_x = 14, 10, 12
    cx = x + pad_x + gem / 2
    cy = y + bh / 2
    rx = gem / 2 * (0.78 + 0.34 * pulse)
    ry = gem / 2 * (0.78 + 0.34 * pulse)
    ctx.new_path()
    ctx.move_to(cx, cy - ry)
    ctx.line_to(cx + rx, cy)
    ctx.line_to(cx, cy + ry)
    ctx.line_to(cx - rx, cy)
    ctx.close_path()
    ctx.set_source_rgba(*gem_color, 0.34 + 0.38 * pulse)
    ctx.fill_preserve()
    ctx.set_source_rgba(*gem_color, 0.95)
    ctx.set_line_width(1.5)
    ctx.stroke()

    spin = (t * 0.7 + phase) % 1.0
    verts = ((cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy))
    for i in range(4):
        dist = abs(spin - i / 4.0)
        dist = min(dist, 1.0 - dist)
        hot = max(0.0, 1.0 - dist * 4.0) ** 1.6
        ctx.move_to(*verts[i])
        ctx.line_to(*verts[(i + 1) % 4])
        ctx.set_source_rgba(1, 1, 1, 0.15 + 0.80 * hot)
        ctx.set_line_width(1.8)
        ctx.stroke()
    ctx.restore()

    show_ink(ctx, lay, x + pad_x + gem + gap, y + (bh - th) / 2)
    return bh


def fit_line(ctx, text, size, floor, width, font):
    """Shrink until the whole string fits. Never clip a channel name."""
    while size > floor and layout(ctx, text, size, "bold", font=font).get_pixel_size()[0] > width:
        size -= 1
    return size


def draw_card(ctx, item, x, y, w, h, t, icons):
    """Channel name leads, full and uncut. Title sits under it beside the still."""
    ctx.save()
    glass_pane(ctx, x, y, w, h)

    pad = 18
    badge = item.get("badge") or "LATEST"
    bsize = 24
    channel = item.get("channel") or ""
    ch_font = row_font(channel)
    title_font = row_font(item["name"])
    bw, bh = age_chip_size(ctx, badge, bsize)

    band_h = 74
    band_top = y + 12
    ctx.set_source_rgba(0.18, 0.48, 0.92, 0.95)
    ctx.rectangle(x + 14, band_top + 10, 5, band_h - 20)
    ctx.fill()

    name_w = w - pad * 2 - bw - 36
    ch_size = fit_line(ctx, channel, 44, 26, name_w, ch_font)
    ch_lay = layout(ctx, channel, ch_size, "bold", font=ch_font)
    _cw, ch = ch_lay.get_pixel_size()
    show_ink(ctx, ch_lay, x + pad + 14, band_top + (band_h - ch) / 2)
    draw_age_chip(
        ctx,
        badge,
        x + w - pad,
        band_top + (band_h - bh) / 2,
        t,
        size=bsize,
        phase=(y * 0.013) % 1.0,
    )

    rule_y = band_top + band_h + 1
    ctx.set_source_rgba(0.12, 0.22, 0.48, 0.28)
    ctx.set_line_width(1.5)
    ctx.move_to(x + 16, rule_y)
    ctx.line_to(x + w - 16, rule_y)
    ctx.stroke()

    body_top = rule_y + 12
    body_h = max(84, y + h - 14 - body_top)
    thumb_h = body_h
    thumb_w = min(thumb_h * 16 / 9, w * 0.44)
    tx = x + pad
    paint_thumb(ctx, icons[icon_key(item)], tx, body_top, thumb_w, thumb_h)

    title_x = tx + thumb_w + 16
    title_w = max(140, x + w - pad - title_x)
    title_lay, th, _title_size = fit_title(
        ctx, item["name"], title_w, body_h, title_font, start=36, floor=20
    )
    show_ink(ctx, title_lay, title_x, body_top + max(0, (body_h - th) / 2))
    ctx.restore()


def draw_footer(ctx):
    draw_copyright(ctx, INK)


def paint_rows(ctx, items, t, icons):
    n = max(1, len(items))
    top, bottom = 268, 1800
    gap = 16
    card_h = CARD_H
    block = n * card_h + gap * (n - 1)
    y0 = top + max(0, (bottom - top - block) / 2)
    left = (W - CARD_W) / 2
    for i, item in enumerate(items):
        y = y0 + i * (card_h + gap)
        draw_card(ctx, item, left, y, CARD_W, card_h, t, icons)


def draw(ctx, items, today, t, icons, title):
    bg(ctx, t)
    real = [item for item in items if not item.get("quiet")]
    new = sum(1 for item in real if item["fresh"])
    draw_header(ctx, today, t, title, new)
    if len(items) == 1 and items[0].get("quiet"):
        draw_card(ctx, items[0], (W - CARD_W) / 2, 760, CARD_W, CARD_H, t, icons)
        draw_footer(ctx)
        return
    pages = [real[i : i + PAGE_LIMIT] for i in range(0, len(real), PAGE_LIMIT)] or [real]
    span = clip_length(items) / len(pages)
    index = min(len(pages) - 1, int(t / span)) if span else 0
    paint_rows(ctx, pages[index], t, icons)
    draw_footer(ctx)
