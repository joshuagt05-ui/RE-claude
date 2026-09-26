#!/usr/bin/env python3
"""Render the illustrated plates for DOWNSTREAM as two-tone "linocut" SVGs.

    python3 art/render_plates.py        # writes art/out/plate01.svg ...

Each plate is drawn from simple shapes plus seeded procedural texture
(stars, grass, cottonwood canopies), so re-running gives the same picture.
"""
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"

INK = "#14181a"
NIGHT = "#1f272b"
TREE = "#0c0f10"
PAPER = "#ece8dc"
PAPER_DIM = "#b9b6ab"
GRASS_DARK = "#2b3437"


def inside(x, y, poly):
    hit = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            hit = not hit
    return hit


def canopy(rng, cx, base, height, width):
    """A cottonwood: a trunk and a pile of overlapping circles."""
    out = [f'<path d="M{cx-4},{base} L{cx-2},{base-height*0.45} L{cx+3},{base-height*0.45} L{cx+5},{base} Z" fill="{TREE}"/>']
    for _ in range(int(width / 5)):
        a = rng.uniform(0, math.pi)
        r = rng.uniform(0.2, 1.0)
        x = cx + math.cos(a) * width * 0.5 * r
        y = base - height * 0.45 - math.sin(a) * height * 0.55 * r
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rng.uniform(8, 20):.1f}" fill="{TREE}"/>')
    return out


# The steer, facing right, head down, in a 180 x 112 box. Drawn once, placed with a transform.
STEER = (
    "M10,40 C5,45 3,60 8,72 L12,79 L14,110 L22,110 L25,86 L31,86 L34,110 L42,110 L43,83 "
    "C60,89 90,89 104,83 L107,110 L115,110 L117,82 L121,82 L125,110 L133,110 L131,77 "
    "C137,75 143,77 149,83 L161,95 C167,101 173,103 177,99 L179,91 C178,85 173,79 167,77 "
    "L161,71 L152,69 L157,74 C150,66 141,48 126,30 C110,22 60,22 30,28 C20,30 14,34 10,40 Z"
)
STEER_FACE = "M167,79 C173,81 177,89 178,96 C173,100 167,99 163,93 C162,88 163,83 167,79 Z"
STEER_TAIL = "M9,44 C3,60 2,80 5,97"


def plate01():
    rng = random.Random(925)
    W, H = 1200, 760
    horizon = 300
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
           "<title>Plate 1 · It wants the river</title>",
           "<defs>"
           '<linearGradient id="beam" x1="0" y1="0" x2="1" y2="0">'
           f'<stop offset="0" stop-color="{PAPER}" stop-opacity="0.97"/>'
           f'<stop offset="0.7" stop-color="{PAPER}" stop-opacity="0.8"/>'
           f'<stop offset="1" stop-color="{PAPER}" stop-opacity="0.45"/></linearGradient>'
           '<linearGradient id="haze" x1="0" y1="0" x2="1" y2="0">'
           f'<stop offset="0" stop-color="{PAPER}" stop-opacity="0.28"/>'
           f'<stop offset="1" stop-color="{PAPER}" stop-opacity="0.08"/></linearGradient>'
           "</defs>"]

    # night sky and ground
    svg.append(f'<rect width="{W}" height="{H}" fill="{NIGHT}"/>')
    svg.append(f'<rect y="{horizon}" width="{W}" height="{H-horizon}" fill="{INK}"/>')

    beam = [(-120, 640), (1260, 250), (1260, 900), (-120, 700)]
    beam_ground = [(x, max(y, horizon)) for x, y in beam]

    # stars outside the beam
    for _ in range(260):
        x, y = rng.uniform(0, W), rng.uniform(0, horizon - 40)
        if not inside(x, y, beam):
            r = rng.choice([0.6, 0.8, 0.8, 1.1, 1.6])
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{PAPER}" fill-opacity="{rng.uniform(0.4, 0.95):.2f}"/>')

    # the river's tree line
    trees = []
    x = 380
    while x < W + 60:
        h = rng.uniform(110, 190) * (0.7 + 0.3 * (x - 380) / (W - 380))
        trees += canopy(rng, x, horizon + 6, h, rng.uniform(70, 120))
        x += rng.uniform(55, 95)
    for x in range(-20, 390, 26):
        trees.append(f'<ellipse cx="{x}" cy="{horizon+2}" rx="{rng.uniform(16, 30):.0f}" ry="{rng.uniform(8, 18):.0f}" fill="{TREE}"/>')
    svg += trees

    # headlight: haze in the air, full light on the ground
    pts = " ".join(f"{x},{y}" for x, y in beam)
    svg.append(f'<polygon points="{pts}" fill="url(#haze)"/>')
    pts = " ".join(f"{x},{y}" for x, y in beam_ground)
    svg.append(f'<polygon points="{pts}" fill="url(#beam)"/>')

    # grass: pale strokes in the dark, ink strokes in the light
    strokes_dark, strokes_lit = [], []
    for _ in range(2600):
        x, y = rng.uniform(0, W), rng.uniform(horizon + 4, H)
        ln = 3 + (y - horizon) / 26 + rng.uniform(0, 4)
        lean = rng.uniform(-2.5, 2.5)
        seg = f"M{x:.1f},{y:.1f}l{lean:.1f},{-ln:.1f}"
        (strokes_lit if inside(x, y, beam_ground) else strokes_dark).append(seg)
    svg.append(f'<path d="{"".join(strokes_dark)}" stroke="{GRASS_DARK}" stroke-width="1.1" fill="none"/>')
    svg.append(f'<path d="{"".join(strokes_lit)}" stroke="{INK}" stroke-opacity="0.35" stroke-width="1" fill="none"/>')

    # back fence of the trap
    rails = []
    for ry in (452, 480, 508):
        rails.append(f"M150,{ry} L1070,{ry - 6}")
    posts = "".join(f"M{px},{444 - (px-150)*0.006:.0f} L{px},{540 - (px-150)*0.006:.0f}" for px in (150, 380, 610, 840))
    svg.append(f'<path d="{"".join(rails)}{posts}" stroke="{INK}" stroke-width="7" stroke-linecap="round" fill="none"/>')

    # right-hand fence, bowed where the steer is pushing
    right = []
    for i, ry in enumerate((0, 1, 2)):
        y0, y1 = 446 + ry * 28, 600 + ry * 44
        bow = [18, 30, 22][i]
        right.append(f"M1070,{y0} Q{1120 + bow},{(y0 + y1) / 2 + 6} 1175,{y1}")
    svg.append(f'<path d="{"".join(right)}" stroke="{INK}" stroke-width="8" stroke-linecap="round" fill="none"/>')
    svg.append(f'<path d="M1070,440 L1070,548 M1175,592 L1175,716" stroke="{INK}" stroke-width="10" stroke-linecap="round"/>')
    # the broken weld: a bright crack at the post
    svg.append(f'<path d="M1162,617 l10,-5 l-4,10 l12,-3" stroke="{PAPER}" stroke-width="2" fill="none"/>')

    # stock tank
    tx, ty, rx, ry = 390, 575, 165, 38
    svg.append(f'<path d="M{tx-rx},{ty} L{tx-rx},{ty+52} A{rx},{ry} 0 0 0 {tx+rx},{ty+52} L{tx+rx},{ty} Z" fill="{INK}"/>')
    ribs = "".join(f"M{tx-rx+ i*22},{ty + 8 + 30*math.sin(math.pi*i*22/(2*rx))**0.5:.0f} l0,{36}" for i in range(1, 15))
    svg.append(f'<path d="{ribs}" stroke="{PAPER_DIM}" stroke-opacity="0.35" stroke-width="1.2"/>')
    svg.append(f'<ellipse cx="{tx}" cy="{ty}" rx="{rx}" ry="{ry}" fill="{NIGHT}" stroke="{PAPER}" stroke-width="3"/>')
    ripple = "".join(f'<ellipse cx="{tx+20}" cy="{ty+2}" rx="{rx*k:.0f}" ry="{ry*k:.0f}" fill="none" stroke="{PAPER}" stroke-opacity="{0.5-k*0.4:.2f}" stroke-width="1.3"/>'
                     for k in (0.25, 0.45, 0.65, 0.85))
    svg.append(ripple)
    # float valve and supply pipe, still running
    svg.append(f'<path d="M0,548 L205,548 L205,570" stroke="{INK}" stroke-width="9" fill="none"/>')
    svg.append(f'<path d="M205,572 q4,8 0,14 M211,572 q5,8 1,14" stroke="{PAPER}" stroke-width="1.6" fill="none"/>')

    # the steer, pushing toward the river
    svg.append(f'<g transform="translate(735,392) scale(2.25)">'
               f'<path d="{STEER_TAIL}" stroke="{INK}" stroke-width="3" fill="none" stroke-linecap="round"/>'
               f'<path d="{STEER}" fill="{INK}"/>'
               f'<path d="{STEER_FACE}" fill="{PAPER}" fill-opacity="0.9"/>'
               f'<circle cx="168.5" cy="85" r="2" fill="{PAPER_DIM}" stroke="{INK}" stroke-width="0.8"/>'
               '</g>')
    # steam off its back
    steam = []
    for i in range(9):
        x0 = 815 + i * 34 + rng.uniform(-6, 6)
        y0 = 438 - 12 * math.sin(i / 8 * math.pi)
        d = f"M{x0:.0f},{y0:.0f}"
        x, y = x0, y0
        for k in range(5):
            x += rng.uniform(-10, 14)
            y -= rng.uniform(16, 24)
            d += f" Q{x + rng.uniform(-14, 14):.0f},{y + 8:.0f} {x:.0f},{y:.0f}"
        steam.append(f'<path d="{d}" stroke="{PAPER}" stroke-opacity="{rng.uniform(0.35, 0.7):.2f}" stroke-width="{rng.uniform(1.4, 3):.1f}" fill="none" stroke-linecap="round"/>')
    svg += steam

    # water pouring from its mouth
    svg.append(f'<path d="M1125,616 q3,20 -2,42 M1131,616 q5,22 1,40 M1119,615 q-1,18 -5,34" stroke="{PAPER}" stroke-width="2" fill="none" stroke-opacity="0.9"/>')

    # front fence: we're looking through it
    svg.append(f'<path d="M0,672 L{W},664 M0,712 L{W},706" stroke="{INK}" stroke-width="13" stroke-linecap="butt"/>')
    svg.append(f'<path d="M110,640 L110,{H} M560,634 L560,{H} M1010,628 L1010,{H}" stroke="{INK}" stroke-width="16"/>')

    # frame
    svg.append(f'<rect x="10" y="10" width="{W-20}" height="{H-20}" fill="none" stroke="{PAPER}" stroke-width="2" stroke-opacity="0.8"/>')
    svg.append("</svg>")
    return "\n".join(svg)


PLATES = {"plate01": plate01}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in PLATES.items():
        (OUT / f"{name}.svg").write_text(fn())
        print(f"rendered {name}.svg")
