#!/usr/bin/env python3
"""Render the chapter maps for DOWNSTREAM.

Every chapter (and every Dispatch) gets a map spec in maps/specs/*.json.
This script turns each spec into an SVG in maps/out/. Standard library only.

    python3 maps/render.py                 # render every spec
    python3 maps/render.py ch01 dispatch01 # render specific specs

Base geography is Natural Earth (public domain) via the sane-topojson and
us-atlas packages, vendored in maps/data/. Fictional places (Raccoon City,
Merritt, the Arklay River) live in the specs themselves.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SPECS = HERE / "specs"
OUT = HERE / "out"

# ---------------------------------------------------------------- palette ---
C = {
    "paper": "#f4eddc",
    "frame": "#2a241c",
    "ocean": "#c9d9dc",
    "land": "#efe6cf",
    "lake": "#c9d9dc",
    "coast": "#7f8f8f",
    "border": "#8a7d66",
    "state": "#b0a288",
    "bg_river": "#8fb2bd",
    "clean": "#2f6f93",
    "red": "#b3261e",
    "red_fill": "#b3261e",
    "ink": "#2a241c",
    "ink_soft": "#5b5245",
    "halo": "#f4eddc",
}
SERIF = "Georgia, 'Iowan Old Style', 'Palatino Linotype', 'Times New Roman', serif"
SANS = "'Helvetica Neue', Helvetica, Arial, sans-serif"


# --------------------------------------------------------------- topojson ---
def load_topo(name):
    topo = json.loads((DATA / name).read_text())
    tf = topo.get("transform")
    arcs = []
    for arc in topo["arcs"]:
        if tf:
            (sx, sy), (tx, ty) = tf["scale"], tf["translate"]
            x = y = 0
            pts = []
            for dx, dy in arc:
                x += dx
                y += dy
                pts.append((x * sx + tx, y * sy + ty))
        else:
            pts = [tuple(p) for p in arc]
        arcs.append(pts)
    topo["_arcs"] = arcs
    return topo


def _arc(topo, i):
    a = topo["_arcs"][i if i >= 0 else ~i]
    return a if i >= 0 else a[::-1]


def _line(topo, idxs):
    pts = []
    for i in idxs:
        a = _arc(topo, i)
        pts.extend(a if not pts else a[1:])
    return pts


def geometries(topo, obj, where=None):
    """Yield (kind, parts, geom) where kind is 'poly' or 'line'.

    For polygons, parts is a list of polygons, each a list of rings.
    For lines, parts is a list of polylines.
    """
    for g in topo["objects"][obj]["geometries"]:
        if where and not where(g):
            continue
        t = g["type"]
        if t == "Polygon":
            yield "poly", [[_line(topo, r) for r in g["arcs"]]], g
        elif t == "MultiPolygon":
            yield "poly", [[_line(topo, r) for r in p] for p in g["arcs"]], g
        elif t == "LineString":
            yield "line", [_line(topo, g["arcs"])], g
        elif t == "MultiLineString":
            yield "line", [_line(topo, l) for l in g["arcs"]], g


# ------------------------------------------------------------- projection ---
def make_projection(spec):
    p = spec.get("projection", {"type": "equirect"})
    t = p["type"]
    if t == "equirect":
        ext = spec["extent"]
        lat0 = math.radians(p.get("lat0", (ext[1] + ext[3]) / 2))
        k = math.cos(lat0)
        return lambda lon, lat: (lon * k, -lat)
    if t == "albers":
        lon0 = math.radians(p.get("lon0", -96))
        lat0 = math.radians(p.get("lat0", 37.5))
        p1, p2 = math.radians(p.get("lat1", 29.5)), math.radians(p.get("lat2", 45.5))
        n = (math.sin(p1) + math.sin(p2)) / 2
        cc = math.cos(p1) ** 2 + 2 * n * math.sin(p1)
        rho0 = math.sqrt(cc - 2 * n * math.sin(lat0)) / n

        def albers(lon, lat):
            rho = math.sqrt(max(cc - 2 * n * math.sin(math.radians(lat)), 0)) / n
            th = n * (math.radians(lon) - lon0)
            return rho * math.sin(th), -(rho0 - rho * math.cos(th))

        return albers
    if t == "natural_earth":

        def ne(lon, lat):
            l, f = math.radians(lon), math.radians(lat)
            f2 = f * f
            f4 = f2 * f2
            x = l * (0.870700 - 0.131979 * f2 - 0.013791 * f4 + f4 * f4 * f2 * (0.003971 - 0.001529 * f2))
            y = f * (1.007226 + f2 * (0.015085 + f4 * (-0.044475 + 0.028874 * f2 - 0.005916 * f4)))
            return x, -y

        return ne
    raise ValueError(f"unknown projection {t}")


class Frame:
    """Projection plus the fit into the SVG drawing box."""

    def __init__(self, spec):
        self.W, self.H = spec.get("size", [1200, 800])
        self.proj = make_projection(spec)
        lo0, la0, lo1, la1 = spec["extent"]
        xs, ys = [], []
        for i in range(41):
            for j in range(41):
                x, y = self.proj(lo0 + (lo1 - lo0) * i / 40, la0 + (la1 - la0) * j / 40)
                xs.append(x)
                ys.append(y)
        self.x0, self.x1, self.y0, self.y1 = min(xs), max(xs), min(ys), max(ys)
        m = spec.get("margin", 18)
        self.box = (m, m, self.W - m, self.H - m)
        bw, bh = self.box[2] - self.box[0], self.box[3] - self.box[1]
        pick = min if spec.get("fit") == "contain" else max  # default: cover the box
        self.k = pick(bw / (self.x1 - self.x0), bh / (self.y1 - self.y0))
        cx, cy = (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2
        self.ox = (self.box[0] + self.box[2]) / 2 - cx * self.k
        self.oy = (self.box[1] + self.box[3]) / 2 - cy * self.k

    def __call__(self, lon, lat):
        x, y = self.proj(lon, lat)
        return x * self.k + self.ox, y * self.k + self.oy

    def km_per_px(self, lon, lat):
        a = self(lon - 0.5, lat)
        b = self(lon + 0.5, lat)
        return 111.32 * math.cos(math.radians(lat)) / math.hypot(b[0] - a[0], b[1] - a[1])


# ------------------------------------------------------------------ paths ---
def project_pts(fr, pts, tol=0.6):
    out = []
    for lon, lat in pts:
        p = fr(lon, lat)
        if out and abs(p[0] - out[-1][0]) < tol and abs(p[1] - out[-1][1]) < tol:
            continue
        out.append(p)
    return out


def visible(fr, pts, pad=40):
    if not pts:
        return False
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    b = fr.box
    return not (max(xs) < b[0] - pad or min(xs) > b[2] + pad or max(ys) < b[1] - pad or min(ys) > b[3] + pad)


def d_attr(rings, close):
    parts = []
    for r in rings:
        if len(r) < 2:
            continue
        s = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in r)
        parts.append(s + ("Z" if close else ""))
    return "".join(parts)


def layer_polys(fr, topo, obj, where=None):
    out = []
    for kind, parts, _ in geometries(topo, obj, where):
        if kind != "poly":
            continue
        for poly in parts:
            rings = []
            for r in poly:
                rings.extend(unwrap_ring(fr, project_pts(fr, r)))
            if rings and any(visible(fr, r) for r in rings):
                out.append(d_attr([r for r in rings if len(r) > 2], True))
    return [d for d in out if d]


def unwrap_ring(fr, pts):
    """A ring that crosses the antimeridian becomes one ring per side of the map."""
    segs, cur = [], []
    for p in pts:
        if cur and abs(p[0] - cur[-1][0]) > fr.W / 3:
            segs.append(cur)
            cur = []
        cur.append(p)
    segs.append(cur)
    if len(segs) == 1:
        return segs
    segs[0] = segs.pop() + segs[0]
    mid = (fr.box[0] + fr.box[2]) / 2
    left = [p for sg in segs if sum(q[0] for q in sg) / len(sg) < mid for p in sg]
    right = [p for sg in segs if sum(q[0] for q in sg) / len(sg) >= mid for p in sg]
    return [r for r in (left, right) if len(r) > 2]


def split_jumps(fr, pts):
    """Break a projected line wherever it jumps across the map (the antimeridian)."""
    segs, cur = [], []
    for p in pts:
        if cur and abs(p[0] - cur[-1][0]) > fr.W / 3:
            segs.append(cur)
            cur = []
        cur.append(p)
    segs.append(cur)
    return [sg for sg in segs if len(sg) > 1]


def layer_lines(fr, topo, obj, where=None, rings_too=False):
    out = []
    for kind, parts, _ in geometries(topo, obj, where):
        lines = parts if kind == "line" else ([r for p in parts for r in p] if rings_too else [])
        for ln in lines:
            for pts in split_jumps(fr, project_pts(fr, ln)):
                if visible(fr, pts):
                    out.append(d_attr([pts], False))
    return out


def great_circle(a, b, n=64):
    def vec(lon, lat):
        lo, la = math.radians(lon), math.radians(lat)
        return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))

    va, vb = vec(*a), vec(*b)
    w = math.acos(max(-1, min(1, sum(x * y for x, y in zip(va, vb)))))
    if w < 1e-9:
        return [a, b]
    pts = []
    for i in range(n + 1):
        t = i / n
        s1, s2 = math.sin((1 - t) * w) / math.sin(w), math.sin(t * w) / math.sin(w)
        x, y, z = (s1 * p + s2 * q for p, q in zip(va, vb))
        pts.append((math.degrees(math.atan2(y, x)), math.degrees(math.atan2(z, math.hypot(x, y)))))
    return pts


def smooth(pts, iters=2):
    """Chaikin smoothing so hand-placed river/route points read as curves."""
    for _ in range(iters):
        if len(pts) < 3:
            return pts
        new = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            new.append((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1))
            new.append((0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))
        new.append(pts[-1])
        pts = new
    return pts


def circle_ring(center, radius_km, n=72):
    lon, lat = center
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        dlat = radius_km / 110.57 * math.sin(a)
        dlon = radius_km / (111.32 * math.cos(math.radians(lat))) * math.cos(a)
        out.append((lon + dlon, lat + dlat))
    return out


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=13, anchor="start", weight="normal", style="normal", fill=None,
         family=SERIF, spacing=0, halo=True, extra=""):
    fill = fill or C["ink"]
    h = f' stroke="{C["halo"]}" stroke-width="3.2" stroke-linejoin="round" paint-order="stroke"' if halo else ""
    ls = f' letter-spacing="{spacing}"' if spacing else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
            f'text-anchor="{anchor}" font-weight="{weight}" font-style="{style}" fill="{fill}"{ls}{h}{extra}>'
            f"{esc(s)}</text>")


# ------------------------------------------------------------------ render ---
def render(spec):
    fr = Frame(spec)
    W, H = fr.W, fr.H
    b = fr.box
    base = spec.get("base", "north-america")
    svg = []
    used = set()

    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
    svg.append(f"<title>{esc(spec.get('title', spec['id']))}</title>")
    svg.append(
        "<defs>"
        f'<clipPath id="clip"><rect x="{b[0]}" y="{b[1]}" width="{b[2]-b[0]}" height="{b[3]-b[1]}"/></clipPath>'
        '<pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        f'<line x1="0" y1="0" x2="0" y2="7" stroke="{C["red"]}" stroke-width="1.4" stroke-opacity="0.55"/></pattern>'
        '<marker id="arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{C["ink"]}"/></marker>'
        '<marker id="arrow-red" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{C["red"]}"/></marker>'
        "</defs>"
    )
    svg.append(f'<rect width="{W}" height="{H}" fill="{C["paper"]}"/>')
    svg.append('<g clip-path="url(#clip)">')
    svg.append(f'<rect x="{b[0]}" y="{b[1]}" width="{b[2]-b[0]}" height="{b[3]-b[1]}" fill="{C["ocean"]}"/>')

    # base geography
    if base == "north-america":
        na = load_topo("north-america_50m.json")
        land = layer_polys(fr, na, "land")
        lakes = layer_polys(fr, na, "lakes")
        rivers = layer_lines(fr, na, "rivers") if spec.get("bg_rivers", True) else []
        borders = layer_lines(fr, na, "countries", rings_too=True)
        coast = layer_lines(fr, na, "coastlines")
        states = []
        if spec.get("states", True):
            us = load_topo("us-states-10m.json")
            states = layer_lines(fr, us, "states", rings_too=True)
    else:
        w = load_topo("world_50m.json" if spec.get("detail") == "50m" else "world_110m.json")
        land = layer_polys(fr, w, "land")
        lakes = layer_polys(fr, w, "lakes")
        rivers = layer_lines(fr, w, "rivers") if spec.get("bg_rivers", True) else []
        borders = layer_lines(fr, w, "countries", rings_too=True) if spec.get("countries", True) else []
        coast = layer_lines(fr, w, "coastlines")
        states = []

    for d in land:
        svg.append(f'<path d="{d}" fill="{C["land"]}" fill-rule="evenodd"/>')
    for d in states:
        svg.append(f'<path d="{d}" fill="none" stroke="{C["state"]}" stroke-width="0.9" stroke-dasharray="5 3"/>')
    for d in borders:
        svg.append(f'<path d="{d}" fill="none" stroke="{C["border"]}" stroke-width="1.1"/>')
    for d in lakes:
        svg.append(f'<path d="{d}" fill="{C["lake"]}" stroke="{C["coast"]}" stroke-width="0.5"/>')
    for d in rivers:
        svg.append(f'<path d="{d}" fill="none" stroke="{C["bg_river"]}" stroke-width="1" stroke-linejoin="round"/>')
    for d in coast:
        svg.append(f'<path d="{d}" fill="none" stroke="{C["coast"]}" stroke-width="0.8"/>')

    # mountains: scattered peak marks inside a polygon
    for m in spec.get("mountains", []):
        poly = [fr(*pt) for pt in m["points"]]
        xs = [q[0] for q in poly]
        ys = [q[1] for q in poly]
        step = m.get("spacing", 26)
        marks = []
        row = 0
        y = min(ys)
        while y < max(ys):
            x = min(xs) + (step / 2 if row % 2 else 0)
            while x < max(xs):
                jx = ((int(x * 7 + y * 13) % 9) - 4) * 1.2
                jy = ((int(x * 11 + y * 5) % 7) - 3) * 1.2
                px, py = x + jx, y + jy
                if inside(px, py, poly):
                    sz = 5 + (int(px + py) % 3)
                    marks.append(f"M{px-sz:.1f},{py+sz*0.6:.1f}L{px:.1f},{py-sz*0.7:.1f}L{px+sz:.1f},{py+sz*0.6:.1f}")
                x += step
            y += step * 0.8
            row += 1
        svg.append(f'<path d="{"".join(marks)}" fill="none" stroke="#9c8a6c" stroke-width="1.1" stroke-linejoin="round"/>')
        used.add("mountains")

    for rd in spec.get("roads", []):
        pts = project_pts(fr, rd["points"], tol=0.3)
        d = d_attr([pts], False)
        svg.append(f'<path d="{d}" fill="none" stroke="#d9cdb0" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>')
        svg.append(f'<path d="{d}" fill="none" stroke="#8c7a5a" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>')
        used.add("road")
        for at in rd.get("shields", []):
            x, y = fr(*at)
            w = 9 + 7 * len(rd["name"])
            svg.append(f'<rect x="{x-w/2:.1f}" y="{y-8:.1f}" width="{w}" height="16" rx="4" fill="{C["paper"]}" stroke="#8c7a5a" stroke-width="1.2"/>')
            svg.append(text(x, y + 4, rd["name"], 10.5, "middle", weight="bold", family=SANS, halo=False, fill="#5b4a2e"))

    # infected zones
    for z in spec.get("zones", []):
        ring = circle_ring(z["center"], z["radius_km"]) if z.get("type", "circle") == "circle" else z["points"]
        pts = project_pts(fr, ring, tol=0.2)
        d = d_attr([pts], True)
        op = {"hot": 0.30, "warm": 0.16, "rumor": 0.0}.get(z.get("level", "hot"), 0.2)
        dash = ' stroke-dasharray="4 4"' if z.get("level") == "rumor" else ""
        svg.append(f'<path d="{d}" fill="{C["red_fill"]}" fill-opacity="{op}"/>')
        svg.append(f'<path d="{d}" fill="url(#hatch)" stroke="{C["red"]}" stroke-width="1.2"{dash}/>')
        used.add("zone_rumor" if z.get("level") == "rumor" else "zone")
        if z.get("label"):
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            lx, ly = z.get("label_offset", [0, 0])
            svg.append(text(cx + lx, cy + ly, z["label"], 12, "middle", style="italic", fill=C["red"]))

    # story rivers
    for r in spec.get("rivers", []):
        pts = project_pts(fr, smooth(r["points"], 3), tol=0.3)
        red = r.get("status") == "red"
        col = C["red"] if red else C["clean"]
        wdt = r.get("width", 2.6)
        svg.append(f'<path d="{d_attr([pts], False)}" fill="none" stroke="{C["halo"]}" stroke-width="{wdt+2.5}" stroke-linecap="round" stroke-linejoin="round" stroke-opacity="0.7"/>')
        svg.append(f'<path d="{d_attr([pts], False)}" fill="none" stroke="{col}" stroke-width="{wdt}" stroke-linecap="round" stroke-linejoin="round"/>')
        used.add("river_red" if red else "river_clean")
        if r.get("label"):
            lab = r["label"]
            x, y = fr(*lab["at"])
            svg.append(text(x, y, r["name"], lab.get("size", 12), lab.get("anchor", "middle"), style="italic",
                            fill=col, extra=f' transform="rotate({lab.get("rotate", 0)} {x:.1f} {y:.1f})"'))

    # routes
    for rt in spec.get("routes", []):
        style = rt.get("style", "travel")
        if style == "flight":
            pts = []
            for a, bb in zip(rt["points"], rt["points"][1:]):
                pts.extend(great_circle(a, bb))
            proj = project_pts(fr, pts, tol=0.3)
            # break the path where it wraps the antimeridian
            segs, cur = [], [proj[0]]
            for p in proj[1:]:
                if abs(p[0] - cur[-1][0]) > W / 2:
                    segs.append(cur)
                    cur = []
                cur.append(p)
            segs.append(cur)
            col = C["red"] if rt.get("status") == "red" else C["ink"]
            mk = "arrow-red" if rt.get("status") == "red" else "arrow"
            for i, s in enumerate(segs):
                end = f' marker-end="url(#{mk})"' if i == len(segs) - 1 else ""
                svg.append(f'<path d="{d_attr([s], False)}" fill="none" stroke="{col}" stroke-width="1.4" stroke-dasharray="2 4" stroke-linecap="round"{end}/>')
            used.add("flight_red" if rt.get("status") == "red" else "flight")
        else:
            pts = project_pts(fr, smooth(rt["points"], 2), tol=0.3)
            done = rt.get("done", True)
            dash = "8 5" if done else "2 5"
            svg.append(f'<path d="{d_attr([pts], False)}" fill="none" stroke="{C["halo"]}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" stroke-opacity="0.8"/>')
            svg.append(f'<path d="{d_attr([pts], False)}" fill="none" stroke="{C["ink"]}" stroke-width="2.2" stroke-dasharray="{dash}" stroke-linecap="round" stroke-linejoin="round" marker-end="url(#arrow)"/>')
            used.add("route" if done else "route_plan")
        if rt.get("label"):
            x, y = fr(*rt["label"]["at"])
            svg.append(text(x, y, rt["label"]["text"], 11.5, rt["label"].get("anchor", "middle"), style="italic",
                            fill=C["ink_soft"]))

    # places
    for p in spec.get("places", []):
        x, y = fr(*p["at"])
        kind = p.get("kind", "town")
        if kind == "home":
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="13" fill="none" stroke="{C["ink"]}" stroke-width="1.2" stroke-dasharray="3 2.5"/>')
            svg.append(f'<path d="{star(x, y, 8, 3.4)}" fill="{C["ink"]}" stroke="{C["halo"]}" stroke-width="1"/>')
            used.add("home")
        elif kind == "ruin":
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{C["paper"]}" stroke="{C["red"]}" stroke-width="2"/>')
            svg.append(f'<path d="M{x-4:.1f},{y-4:.1f}L{x+4:.1f},{y+4:.1f}M{x+4:.1f},{y-4:.1f}L{x-4:.1f},{y+4:.1f}" stroke="{C["red"]}" stroke-width="2"/>')
            used.add("ruin")
        elif kind == "city":
            svg.append(f'<rect x="{x-4.5:.1f}" y="{y-4.5:.1f}" width="9" height="9" fill="{C["red"] if p.get("infected") else C["ink"]}" stroke="{C["halo"]}" stroke-width="1"/>')
            used.add("city_red" if p.get("infected") else "city")
        elif kind == "airport":
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{C["paper"]}" stroke="{C["ink"]}" stroke-width="1.6"/>')
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="{C["ink"]}"/>')
            used.add("airport")
        elif kind == "poi":
            svg.append(f'<path d="M{x:.1f},{y-6:.1f}L{x+6:.1f},{y:.1f}L{x:.1f},{y+6:.1f}L{x-6:.1f},{y:.1f}Z" fill="{C["paper"]}" stroke="{C["ink"]}" stroke-width="1.5"/>')
            used.add("poi")
        else:
            fill = C["red"] if p.get("infected") else C["ink"]
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="{fill}" stroke="{C["halo"]}" stroke-width="1"/>')
            used.add("town_red" if p.get("infected") else "town")
        pos = p.get("label_pos", "right")
        size = {"home": 16, "city": 14, "ruin": 14}.get(kind, 12.5)
        gap = {"home": 18, "ruin": 11}.get(kind, 8)
        dx, dy, anchor = {"right": (gap, 4.5, "start"), "left": (-gap, 4.5, "end"),
                          "above": (0, -gap - 2, "middle"), "below": (0, gap + 11, "middle")}[pos]
        weight = "bold" if kind in ("home", "city", "ruin") else "normal"
        col = C["red"] if (p.get("infected") or kind == "ruin") else C["ink"]
        svg.append(text(x + dx, y + dy, p["name"], size, anchor, weight=weight, fill=col,
                        spacing=0.6 if kind in ("city", "ruin") else 0))
        if p.get("note"):
            svg.append(text(x + dx, y + dy + size + 1, p["note"], 11, anchor, style="italic", fill=C["ink_soft"]))

    # annotations (Eli's handwriting)
    for n in spec.get("notes", []):
        x, y = fr(*n["at"])
        col = C["red"] if n.get("red") else C["ink_soft"]
        for i, line in enumerate(n["text"].split("\n")):
            svg.append(text(x, y + i * 15, line, n.get("size", 12.5), n.get("anchor", "start"), style="italic", fill=col))

    svg.append("</g>")

    # frame
    svg.append(f'<rect x="{b[0]}" y="{b[1]}" width="{b[2]-b[0]}" height="{b[3]-b[1]}" fill="none" stroke="{C["frame"]}" stroke-width="1.6"/>')
    svg.append(f'<rect x="{b[0]-6}" y="{b[1]-6}" width="{b[2]-b[0]+12}" height="{b[3]-b[1]+12}" fill="none" stroke="{C["frame"]}" stroke-width="0.6"/>')

    svg.extend(cartouche(spec, b))
    if spec.get("legend", True):
        svg.extend(legend(used, b, spec))
    if spec.get("scale", True):
        svg.extend(scale_bar(fr, spec, b))
    svg.extend(compass(b, spec))
    svg.append(text(b[2] - 8, b[3] - 8, spec.get("credit", "Eli's Atlas"), 10.5, "end", style="italic", fill=C["ink_soft"]))
    svg.append("</svg>")
    return "\n".join(svg)


def inside(x, y, poly):
    hit = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            hit = not hit
    return hit


def star(x, y, r1, r2):
    pts = []
    for i in range(10):
        r = r1 if i % 2 == 0 else r2
        a = -math.pi / 2 + i * math.pi / 5
        pts.append(f"{x + r * math.cos(a):.1f},{y + r * math.sin(a):.1f}")
    return "M" + "L".join(pts) + "Z"


def cartouche(spec, b):
    x, y = b[0] + 16, b[1] + 16
    lines = [(spec.get("kicker", ""), 11, "normal", "normal", SANS, 1.6, C["ink_soft"]),
             (spec.get("title", ""), 22, "bold", "normal", SERIF, 0, C["ink"]),
             (spec.get("subtitle", ""), 13.5, "normal", "italic", SERIF, 0, C["ink_soft"])]
    w = max(len(spec.get("title", "")) * 11.2, len(spec.get("subtitle", "")) * 6.6,
            len(spec.get("kicker", "")) * 7.8) + 30
    h = 84
    out = [f'<rect x="{x}" y="{y}" width="{w:.0f}" height="{h}" fill="{C["paper"]}" fill-opacity="0.94" stroke="{C["frame"]}" stroke-width="1"/>',
           f'<line x1="{x+14}" y1="{y+56}" x2="{x+w-14:.0f}" y2="{y+56}" stroke="{C["state"]}" stroke-width="0.8"/>']
    ys = [y + 22, y + 47, y + 74]
    for (s, size, weight, style, fam, sp, col), yy in zip(lines, ys):
        if s:
            out.append(text(x + 14, yy, s.upper() if fam == SANS else s, size, weight=weight, style=style,
                            family=fam, spacing=sp, fill=col, halo=False))
    return out


LEGEND = [
    ("home", "Where we are"),
    ("route", "Where we went"),
    ("route_plan", "Where we're going"),
    ("city", "City"),
    ("city_red", "City — infected"),
    ("town", "Town"),
    ("town_red", "Town — infected"),
    ("airport", "Airport"),
    ("poi", "Landmark"),
    ("road", "Highway"),
    ("mountains", "Mountains"),
    ("ruin", "Destroyed"),
    ("river_red", "Contaminated water"),
    ("river_clean", "Clean water"),
    ("zone", "Outbreak"),
    ("zone_rumor", "Rumored outbreak"),
    ("flight", "Flight"),
    ("flight_red", "Flight — carrier aboard"),
]


def legend(used, b, spec):
    items = [(k, lab) for k, lab in LEGEND if k in used]
    if not items:
        return []
    w, row = 196, 21
    h = 18 + row * len(items)
    corner = spec.get("legend_corner", "bl")
    x = b[0] + 16 if corner in ("bl", "tl") else b[2] - 16 - w
    y = b[3] - 16 - h if corner in ("bl", "br") else b[1] + 16
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{C["paper"]}" fill-opacity="0.94" stroke="{C["frame"]}" stroke-width="1"/>']
    for i, (k, lab) in enumerate(items):
        cx, cy = x + 22, y + 19 + i * row
        out.append(swatch(k, cx, cy))
        out.append(text(cx + 22, cy + 4.5, lab, 12.5, halo=False))
    return out


def swatch(k, x, y):
    if k == "home":
        return f'<path d="{star(x, y, 7, 3)}" fill="{C["ink"]}"/>'
    if k in ("route", "route_plan"):
        dash = "8 5" if k == "route" else "2 5"
        return f'<line x1="{x-12}" y1="{y}" x2="{x+12}" y2="{y}" stroke="{C["ink"]}" stroke-width="2.2" stroke-dasharray="{dash}" stroke-linecap="round"/>'
    if k in ("city", "city_red"):
        return f'<rect x="{x-4.5}" y="{y-4.5}" width="9" height="9" fill="{C["red"] if k == "city_red" else C["ink"]}"/>'
    if k in ("town", "town_red"):
        return f'<circle cx="{x}" cy="{y}" r="3.6" fill="{C["red"] if k == "town_red" else C["ink"]}"/>'
    if k == "airport":
        return f'<circle cx="{x}" cy="{y}" r="6" fill="{C["paper"]}" stroke="{C["ink"]}" stroke-width="1.6"/><circle cx="{x}" cy="{y}" r="2" fill="{C["ink"]}"/>'
    if k == "road":
        return (f'<line x1="{x-12}" y1="{y}" x2="{x+12}" y2="{y}" stroke="#d9cdb0" stroke-width="5" stroke-linecap="round"/>'
                f'<line x1="{x-12}" y1="{y}" x2="{x+12}" y2="{y}" stroke="#8c7a5a" stroke-width="1.6"/>')
    if k == "mountains":
        return f'<path d="M{x-11},{y+4}L{x-5},{y-4}L{x+1},{y+4}M{x-1},{y+4}L{x+5},{y-5}L{x+11},{y+4}" fill="none" stroke="#9c8a6c" stroke-width="1.1"/>'
    if k == "poi":
        return f'<path d="M{x},{y-6}L{x+6},{y}L{x},{y+6}L{x-6},{y}Z" fill="{C["paper"]}" stroke="{C["ink"]}" stroke-width="1.5"/>'
    if k == "ruin":
        return (f'<circle cx="{x}" cy="{y}" r="7" fill="{C["paper"]}" stroke="{C["red"]}" stroke-width="2"/>'
                f'<path d="M{x-4},{y-4}L{x+4},{y+4}M{x+4},{y-4}L{x-4},{y+4}" stroke="{C["red"]}" stroke-width="2"/>')
    if k in ("river_red", "river_clean"):
        return f'<path d="M{x-12},{y+3} q6,-8 12,-3 t12,-3" fill="none" stroke="{C["red"] if k == "river_red" else C["clean"]}" stroke-width="2.6" stroke-linecap="round"/>'
    if k in ("zone", "zone_rumor"):
        dash = ' stroke-dasharray="4 4"' if k == "zone_rumor" else ""
        op = 0 if k == "zone_rumor" else 0.3
        return (f'<rect x="{x-11}" y="{y-7}" width="22" height="14" fill="{C["red_fill"]}" fill-opacity="{op}"/>'
                f'<rect x="{x-11}" y="{y-7}" width="22" height="14" fill="url(#hatch)" stroke="{C["red"]}" stroke-width="1.2"{dash}/>')
    if k in ("flight", "flight_red"):
        col = C["red"] if k == "flight_red" else C["ink"]
        return f'<line x1="{x-12}" y1="{y}" x2="{x+12}" y2="{y}" stroke="{col}" stroke-width="1.4" stroke-dasharray="2 4" stroke-linecap="round"/>'
    return ""


def scale_bar(fr, spec, b):
    lon = (spec["extent"][0] + spec["extent"][2]) / 2
    lat = (spec["extent"][1] + spec["extent"][3]) / 2
    mi_per_px = fr.km_per_px(lon, lat) / 1.609344
    target = 160 * mi_per_px
    nice = min((n for n in [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000]),
               key=lambda n: abs(n - target))
    px = nice / mi_per_px
    x, y = b[2] - 24 - px, b[3] - 34
    out = [f'<rect x="{x-12}" y="{y-22}" width="{px+24:.1f}" height="38" fill="{C["paper"]}" fill-opacity="0.9"/>',
           f'<rect x="{x}" y="{y}" width="{px/2:.1f}" height="5" fill="{C["ink"]}"/>',
           f'<rect x="{x+px/2:.1f}" y="{y}" width="{px/2:.1f}" height="5" fill="{C["paper"]}" stroke="{C["ink"]}" stroke-width="1"/>',
           text(x, y - 6, "0", 11, "middle", halo=False),
           text(x + px, y - 6, f"{nice:,} mi", 11, "middle", halo=False)]
    return out


def compass(b, spec):
    x, y = b[2] - 40, b[1] + 48
    if spec.get("compass", True) is False:
        return []
    return [f'<circle cx="{x}" cy="{y}" r="22" fill="{C["paper"]}" fill-opacity="0.9" stroke="{C["frame"]}" stroke-width="0.8"/>',
            f'<path d="M{x},{y-18} L{x+6},{y} L{x},{y-3} L{x-6},{y} Z" fill="{C["ink"]}"/>',
            f'<path d="M{x},{y+18} L{x+6},{y} L{x},{y+3} L{x-6},{y} Z" fill="none" stroke="{C["ink"]}" stroke-width="1"/>',
            text(x, y - 25, "N", 12, "middle", weight="bold", halo=False)]


def main(argv):
    OUT.mkdir(exist_ok=True)
    specs = sorted(SPECS.glob("*.json"))
    if argv:
        specs = [SPECS / f"{a}.json" for a in argv]
    for path in specs:
        spec = json.loads(path.read_text())
        spec.setdefault("id", path.stem)
        (OUT / f"{spec['id']}.svg").write_text(render(spec))
        print(f"rendered {spec['id']}.svg")


if __name__ == "__main__":
    main(sys.argv[1:])
