#!/usr/bin/env python3
"""Still of the Japanese video update background."""

import os
import sys

import cairo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reel.seascape import paint

ROOT = os.path.dirname(os.path.abspath(__file__))


def write(name, w, h):
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    ctx = cairo.Context(surface)
    paint(ctx, w, h, 0.6)
    path = os.path.join(ROOT, name)
    surface.write_to_png(path)
    print(path)


if __name__ == "__main__":
    write("japanese-sea.png", 1080, 1920)
    write("japanese-sea-wide.png", 1920, 1080)
