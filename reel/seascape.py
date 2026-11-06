"""Pale crocodile-hide diamond grid for the Japanese reel.

Each scale is one diamond. The lattice does not move. Each diamond breathes
through cyan, cobalt, and violet on its own clock, so the color change has
no direction and nothing slides toward a corner. No green, red, orange,
pink, or yellow. The field stays milky so type on clear glass remains
readable. Every cycle closes in 4 seconds.
"""

import math

import cairo

# Cool hide. Distinct enough to read as a color change, still pale.
CYAN = (0.42, 0.86, 1.00)
COBALT = (0.58, 0.70, 1.00)
VIOLET = (0.78, 0.66, 1.00)
WHITE = (1.0, 1.0, 1.0)
CRACK = (0.36, 0.50, 0.78)
# Resting mix toward white. A short flash lifts a diamond further.
MILK = 0.28
# One full color cycle every 4 seconds, which divides the clip.
CYCLE = 4.0


def mix(a, b, t):
    return tuple(a[i] * (1.0 - t) + b[i] * t for i in range(3))


def tone(color, lift):
    return tuple(min(1.0, max(0.0, channel + lift)) for channel in color)


def phase(c, r):
    # Irregular offsets so neighbors do not flash together.
    return ((c * 5 + r * 3) * 47 % 360) / 360.0


def hue_at(c, r, t):
    """One diamond, cycling cyan -> cobalt -> violet -> cyan."""
    turn = ((t / CYCLE) + phase(c, r)) % 1.0
    if turn < 1.0 / 3.0:
        return mix(CYAN, COBALT, turn * 3.0)
    if turn < 2.0 / 3.0:
        return mix(COBALT, VIOLET, (turn - 1.0 / 3.0) * 3.0)
    return mix(VIOLET, CYAN, (turn - 2.0 / 3.0) * 3.0)


def lift_at(c, r, t):
    """A short flash toward white. Neighbors do not peak together."""
    turn = ((t / CYCLE) + phase(c, r) + 0.17) % 1.0
    wave = max(0.0, math.cos(turn * math.tau))
    return wave ** 4


def paint(ctx, w, h, t=0.0):
    step = 72.0 if h >= w else 84.0
    row_h = step * 0.56
    half_w = step * 0.5

    ctx.set_source_rgb(0.91, 0.95, 1.00)
    ctx.paint()

    cols = int(w / step) + 4
    rows = int(h / row_h) + 4
    ctx.set_line_join(cairo.LINE_JOIN_MITER)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for r in range(-1, rows):
        for c in range(-1, cols):
            cx = c * step + (half_w if r % 2 else 0.0)
            cy = r * row_h
            lift = lift_at(c, r, t)
            milk = min(0.78, MILK + 0.28 * lift)
            base = hue_at(c, r, t)
            color = mix(base, WHITE, milk)
            top = tone(color, 0.045 + 0.04 * lift)
            bot = tone(color, -0.03)

            ctx.new_path()
            ctx.move_to(cx, cy - row_h)
            ctx.line_to(cx + half_w, cy)
            ctx.line_to(cx, cy + row_h)
            ctx.line_to(cx - half_w, cy)
            ctx.close_path()
            shade = cairo.LinearGradient(cx, cy - row_h, cx, cy + row_h)
            shade.add_color_stop_rgb(0.0, *top)
            shade.add_color_stop_rgb(0.5, *color)
            shade.add_color_stop_rgb(1.0, *bot)
            ctx.set_source(shade)
            ctx.fill_preserve()
            ctx.set_source_rgba(*CRACK, 0.22 + 0.28 * (1.0 - lift))
            ctx.set_line_width(1.15 + 0.45 * (1.0 - lift))
            ctx.stroke()
