#!/usr/bin/env python3
"""Build the book-style reader page for DOWNSTREAM.

Stitches the manuscript, then the bible and outline ("the Notebook"), into
one HTML page with the maps and illustrated plates inline, so the whole
project reads top to bottom like a book.

    pip install markdown
    python3 reader/build.py [out.html]      # default: reader/downstream.html
"""
import base64
import re
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
MAPS = ROOT / "maps" / "out"
ART = ROOT / "art" / "out"

# The novel: parts, and in each part its chapters. Each chapter opens with its
# map; plates go directly before the chapter's last scene break unless placed
# elsewhere.
NOVEL = [
    {
        "id": "part-one", "label": "Part One", "title": "Boil Order",
        "dates": "Day 0 – Day 31 · September 25 – October 26",
        "chapters": [
            {"id": "ch01", "src": "manuscript/part-1/ch01-homecoming.md", "map": "ch01",
             "map_caption": "Map 1 · Day 0, Friday night. The contamination front reaches the Mercer farm.",
             "plates": [("before-last-break", "plate01", "Plate 1 · “It wants the river.”")]},
        ],
    },
]

SECTIONS = [
    ("premise", "The Premise", "What happens after the screen goes black.", None),
    ("world", "The World", "The rules: the virus, the water, the Turned, Umbrella, the seasons.", "bible/world.md"),
    ("people", "The People", "The Mercers, their town, and who they meet on the road.", "bible/characters.md"),
    ("places", "The Places", "Real and fictional geography, and the road west.", "bible/setting.md"),
    ("timeline", "The Timeline", "The whole world, Day −4 to Day 365.", "bible/chronology.md"),
    ("book", "The Book", "Five parts, twelve Dispatches, and the decisions still open.", "outline/book-plan.md"),
]

# (section id, heading text that the map goes directly before or after, map id, caption)
FIGURES = [
    ("world", "before", "4. Water", "ref-watershed",
     "The Watershed. How the water carries it from Raccoon City to the Gulf of Mexico in 31 days."),
    ("book", "after", "PART ONE: BOIL ORDER", "ch01",
     "Map 1 · Chapter 1, “Homecoming.” Day 0, the same night as the movie."),
    ("book", "before", "The Dispatches: glimpses of the whole world", "dispatch01",
     "Dispatch map I · “Departures.” Day 3, the flights out of Denver."),
]

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]


def map_img(map_id, caption, folder=MAPS, kind="plate"):
    svg = (folder / f"{map_id}.svg").read_bytes()
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg).decode()
    return (f'<figure class="{kind}"><img src="{uri}" alt="{caption}" loading="lazy">'
            f"<figcaption>{caption}</figcaption></figure>")


def chapter_html(ch, number):
    text = (ROOT / ch["src"]).read_text()
    title = re.search(r"^# Chapter \d+: (.*)$", text, re.M).group(1)
    dayline = re.search(r"^\*(Day .*)\*$", text, re.M).group(1)
    body = text.split("\n---\n", 1)[1]
    html = markdown.markdown(body)
    html = html.replace("<p>⁂</p>", '<p class="break" aria-label="Scene break">⁂</p>')
    for where, plate, caption in ch.get("plates", []):
        fig = map_img(plate, caption, ART, "art")
        if where == "before-last-break":
            i = html.rfind('<p class="break"')
            html = html[:i] + fig + html[i:]
    opener = (f'<header class="ch-opener"><div class="num">Chapter {number}</div><h3>{title}</h3>'
              f'<p class="dayline">{dayline}</p></header>')
    return title, (f'<article class="chapter" id="{ch["id"]}">{opener}'
                   f'{map_img(ch["map"], ch["map_caption"])}<div class="novel">{html}</div></article>')


def md_to_html(text):
    text = re.sub(r"^# .*\n", "", text, count=1)  # the section opener replaces each file's H1
    text = re.sub(r"\A\s*> \*The missile.*\n", "", text)  # the cover already carries the tagline
    html = markdown.markdown(text, extensions=["tables", "sane_lists"])
    html = re.sub(r"<table>", '<div class="table-wrap"><table>', html)
    html = html.replace("</table>", "</table></div>")
    html = re.sub(r"<strong>\(open(?:, recommended)?\)</strong>|\(open\)",
                  '<span class="open">open</span>', html)
    html = re.sub(r"<code>((?:bible|outline|maps)/[^<]*|book-plan\.md|setting\.md|world\.md)</code>",
                  r'<span class="ref">\1</span>', html)
    return html


def place_figures(sec_id, html):
    for sid, where, heading, map_id, caption in FIGURES:
        if sid != sec_id:
            continue
        m = re.search(r"<h([23])>" + re.escape(heading).replace("\\ ", " ") + r"</h\1>", html)
        if not m:
            raise SystemExit(f"figure anchor not found: {heading}")
        fig = map_img(map_id, caption)
        if where == "before":
            html = html[: m.start()] + fig + html[m.start():]
        else:
            end = html.find("</p>", m.end())
            end = end + 4 if end != -1 else m.end()
            html = html[:end] + fig + html[end:]
    return html


def premise_html():
    readme = (ROOT / "README.md").read_text()
    body = readme.split("## What's here")[0]
    body = re.sub(r"^# .*\n", "", body)
    body = re.sub(r"^\*A Resident Evil story.*\n", "", body, flags=re.M)
    body = re.sub(r"^> .*\n", "", body, flags=re.M)
    return markdown.markdown(body.strip())


CSS = r"""
:root{
  --paper:#f5f6f2; --paper-2:#eceee8; --ink:#1c2124; --ink-2:#4a5357; --ink-3:#6d777a;
  --rule:#d5d9d2; --red:#b3261e; --blue:#2f6f93; --plate:#e6e8e1; --chip:#f9e3e1;
  --display:'Big Shoulders Display','Oswald','Arial Narrow',Impact,sans-serif;
  --body:'Literata',Georgia,'Iowan Old Style','Times New Roman',serif;
  --mono:'IBM Plex Mono',ui-monospace,'SF Mono',Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --paper:#12181b; --paper-2:#182125; --ink:#e1e6e3; --ink-2:#b3bcbc; --ink-3:#8b9696;
    --rule:#2c373b; --red:#e2584d; --blue:#7fb3cf; --plate:#1c2629; --chip:#3a1c1a;
    color-scheme:dark;
  }
}
:root[data-theme="dark"]{
  --paper:#12181b; --paper-2:#182125; --ink:#e1e6e3; --ink-2:#b3bcbc; --ink-3:#8b9696;
  --rule:#2c373b; --red:#e2584d; --blue:#7fb3cf; --plate:#1c2629; --chip:#3a1c1a;
  color-scheme:dark;
}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion: reduce){html{scroll-behavior:auto}}
body{overflow-wrap:break-word;background:var(--paper);color:var(--ink);font-family:var(--body);font-size:18px;line-height:1.68;
  padding-inline:20px;padding-block:0 96px;font-optical-sizing:auto;-webkit-font-smoothing:antialiased}
.progress{position:fixed;left:0;top:0;height:3px;width:0;background:var(--red);z-index:10;
  margin-top:env(safe-area-inset-top,0px)}
.col{max-width:40rem;margin-inline:auto}

/* cover */
.cover{max-width:40rem;margin-inline:auto;padding-block:14vh 10vh;display:grid;gap:22px}
.cover .kicker{font-family:var(--mono);font-size:12.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-3)}
.cover h1{font-family:var(--display);font-weight:800;font-size:clamp(48px,13vw,140px);line-height:.86;
  letter-spacing:.01em;margin:0;text-transform:uppercase;white-space:nowrap;max-width:100%}
.cover .river{width:100%;height:46px;display:block}
.cover .river path{fill:none;stroke:var(--red);stroke-width:3;stroke-linecap:round}
.cover .river path.clean{stroke:var(--blue)}
.cover .tagline{font-style:italic;font-size:clamp(20px,4vw,25px);line-height:1.4;margin:0;text-wrap:balance}
.cover .meta{font-family:var(--mono);font-size:13px;color:var(--ink-2);line-height:1.8}

/* contents */
.contents{max-width:40rem;margin-inline:auto;padding-block:8px 40px;border-top:1px solid var(--rule)}
.contents h2{font-family:var(--mono);font-size:12.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-3);font-weight:500;margin:22px 0 10px}
.contents ol{list-style:none;padding:0;margin:0;display:grid;gap:2px}
.contents a{display:grid;grid-template-columns:3.2rem 1fr;gap:4px 12px;padding:10px 0;color:inherit;text-decoration:none;border-bottom:1px dotted var(--rule)}
.contents a:hover .t,.contents a:focus-visible .t{color:var(--red)}
.contents .n{font-family:var(--mono);font-size:14px;color:var(--red);padding-top:4px}
.contents .t{font-family:var(--display);font-size:27px;font-weight:700;text-transform:uppercase;line-height:1.1;letter-spacing:.02em}
.contents .d{grid-column:2;font-size:15.5px;color:var(--ink-2);line-height:1.45}

/* section opener */
section.part{padding-top:72px}
.opener{max-width:40rem;margin:0 auto 34px;padding-bottom:18px;border-bottom:3px solid var(--ink)}
.opener .num{font-family:var(--mono);font-size:13px;letter-spacing:.16em;color:var(--red);text-transform:uppercase}
.opener h2{font-family:var(--display);font-weight:800;font-size:clamp(46px,10vw,78px);line-height:.95;
  text-transform:uppercase;margin:6px 0 10px;letter-spacing:.01em;text-wrap:balance}
.opener p{margin:0;font-style:italic;color:var(--ink-2);font-size:19px}

/* prose */
.prose{max-width:40rem;margin-inline:auto}
.prose p{margin:0 0 1.05em}
.prose h2{font-family:var(--display);font-weight:700;font-size:31px;line-height:1.1;text-transform:uppercase;
  letter-spacing:.02em;margin:2.1em 0 .55em;text-wrap:balance}
.prose h3{font-size:20px;font-weight:700;margin:1.8em 0 .5em;text-wrap:balance}
.prose ul,.prose ol{padding-left:1.25em;margin:0 0 1.1em}
.prose li{margin:.28em 0}
.prose li::marker{color:var(--ink-3)}
.prose strong{font-weight:700}
.prose hr{border:0;border-top:1px solid var(--rule);margin:2.6em 0}
.prose blockquote{margin:1.4em 0;padding:.2em 0 .2em 1.1em;border-left:3px solid var(--red);font-style:italic;font-size:21px;color:var(--ink)}
.prose blockquote p{margin:0}
.prose code{font-family:var(--mono);font-size:.84em;background:var(--paper-2);padding:.1em .35em;border-radius:3px}
.prose a{color:var(--blue)}
.open{font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;
  color:var(--red);background:var(--chip);padding:2px 7px;border-radius:3px;vertical-align:2px;white-space:nowrap}
.ref{font-family:var(--mono);font-size:.8em;color:var(--ink-3)}

/* tables */
.table-wrap{overflow-x:auto;margin:1.3em 0 1.6em;border-top:2px solid var(--ink);border-bottom:1px solid var(--rule)}
table{border-collapse:collapse;width:100%;font-size:15.5px;line-height:1.5;font-variant-numeric:tabular-nums}
th{font-family:var(--mono);font-size:11.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);text-align:left;padding:10px 12px 8px 0;vertical-align:bottom}
td{padding:9px 12px 9px 0;border-top:1px solid var(--rule);vertical-align:top}
td:first-child{white-space:nowrap}
th:empty{padding:0}
thead tr:has(th:empty:first-child){display:none}

/* map plates */
.plate{margin:2.2em auto;max-width:min(1120px,100%);padding:10px;background:var(--plate);border-radius:4px}
.plate img{display:block;width:100%;height:auto;border-radius:2px}
.plate figcaption{font-family:var(--mono);font-size:12.5px;color:var(--ink-2);padding:10px 4px 2px;line-height:1.5}
.prose .plate{margin-inline:calc(50% - min(560px,50vw - 20px));max-width:none;width:min(1120px,calc(100vw - 40px))}

/* the novel */
.part-opener{max-width:40rem;margin:0 auto;padding-block:80px 30px;text-align:center}
.part-opener .num{font-family:var(--mono);font-size:13px;letter-spacing:.2em;text-transform:uppercase;color:var(--red)}
.part-opener h2{font-family:var(--display);font-weight:800;font-size:clamp(56px,13vw,104px);line-height:.9;text-transform:uppercase;margin:10px 0 12px;text-wrap:balance}
.part-opener p{margin:0;font-family:var(--mono);font-size:13px;color:var(--ink-2)}
.chapter{padding-top:48px}
.ch-opener{max-width:40rem;margin:0 auto 8px}
.ch-opener .num{font-family:var(--mono);font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:var(--red)}
.ch-opener h3{font-family:var(--display);font-weight:800;font-size:clamp(40px,8vw,60px);line-height:1;text-transform:uppercase;margin:6px 0 8px}
.ch-opener .dayline{margin:0;font-family:var(--mono);font-size:13.5px;color:var(--ink-2)}
.novel{max-width:36rem;margin-inline:auto;font-size:19px;line-height:1.72}
.novel p{margin:0;text-indent:1.6em}
.novel > p:first-child,.novel .break + p,.novel figure + p{text-indent:0}
.novel > p:first-child::first-letter{font-family:var(--display);font-weight:800;float:left;font-size:4.1em;line-height:.8;padding:.08em .08em 0 0;color:var(--red)}
.novel .break{text-align:center;text-indent:0;margin:1.6em 0;color:var(--ink-3);letter-spacing:.4em}
.novel strong{font-weight:700}
.novel p:has(> strong:only-child),.novel p:has(> strong + br){text-indent:0;text-align:center;margin:1em 0;font-family:var(--mono);font-size:15px;line-height:1.5}
.art{margin:2em auto;padding:0;max-width:min(1120px,100%)}
.art img{display:block;width:100%;height:auto}
.art figcaption{font-family:var(--mono);font-size:12.5px;color:var(--ink-2);padding:10px 2px 0;text-align:center}
.novel .art,.novel .plate{margin-inline:calc(50% - min(560px,50vw - 20px));width:min(1120px,calc(100vw - 40px));max-width:none}
.notebook-opener{max-width:40rem;margin:120px auto 0;padding-top:36px;border-top:3px double var(--rule);text-align:center}
.notebook-opener .num{font-family:var(--mono);font-size:13px;letter-spacing:.2em;text-transform:uppercase;color:var(--ink-3)}
.notebook-opener h2{font-family:var(--display);font-weight:800;font-size:clamp(48px,11vw,84px);text-transform:uppercase;margin:8px 0 10px;line-height:.95}
.notebook-opener p{margin:0 auto;max-width:32rem;font-style:italic;color:var(--ink-2)}
.contents .group{font-family:var(--mono);font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-3);padding:18px 0 4px;border-bottom:1px solid var(--rule)}
.to-top{position:fixed;right:16px;bottom:calc(16px + env(safe-area-inset-bottom,0px));font-family:var(--mono);font-size:12px;
  letter-spacing:.1em;text-transform:uppercase;text-decoration:none;color:var(--ink);background:var(--paper);
  border:1px solid var(--rule);padding:8px 12px;border-radius:3px}
.to-top:hover,.to-top:focus-visible{border-color:var(--red);color:var(--red)}
a:focus-visible{outline:2px solid var(--red);outline-offset:3px}
.end{max-width:40rem;margin:80px auto 0;text-align:center;font-family:var(--mono);font-size:12.5px;letter-spacing:.16em;color:var(--ink-3);text-transform:uppercase}
@media (max-width:520px){
  body{font-size:17px}
  .contents .t{font-size:23px}
  .prose h2{font-size:26px}
  table{font-size:14.5px}
}
"""

JS = r"""
(function(){
  var h1=document.querySelector('.cover h1');
  function fit(){h1.style.fontSize='';var w=h1.parentNode.clientWidth,s=h1.scrollWidth;
    if(s>w){h1.style.fontSize=(parseFloat(getComputedStyle(h1).fontSize)*w/s*0.98)+'px';}}
  fit();window.addEventListener('resize',fit);
  if(document.fonts&&document.fonts.ready){document.fonts.ready.then(fit);}
  var bar=document.querySelector('.progress');
  function tick(){var h=document.documentElement;var max=h.scrollHeight-h.clientHeight;
    bar.style.width=(max>0?(h.scrollTop/max*100):0)+'%';}
  document.addEventListener('scroll',tick,{passive:true});tick();
  try{var y=+localStorage.getItem('downstream-reader-y');
    if(y>400&&!location.hash){window.scrollTo(0,y);}}catch(e){}
  var t;document.addEventListener('scroll',function(){clearTimeout(t);t=setTimeout(function(){
    try{localStorage.setItem('downstream-reader-y',String(window.scrollY));}catch(e){}},300);},{passive:true});
})();
"""


def build():
    parts = []
    toc = ['<li class="group">The Novel</li>']
    for part in NOVEL:
        chapters = []
        for n, ch in enumerate(part["chapters"], 1):
            title, html = chapter_html(ch, n)
            chapters.append(html)
            toc.append(f'<li><a href="#{ch["id"]}"><span class="n">{n}</span><span class="t">{title}</span>'
                       f'<span class="d">{part["label"]} · {part["title"]}</span></a></li>')
        parts.append(f'<section class="part-novel" id="{part["id"]}"><header class="part-opener">'
                     f'<div class="num">{part["label"]}</div><h2>{part["title"]}</h2><p>{part["dates"]}</p></header>'
                     f'{"".join(chapters)}</section>')
    parts.append('<header class="notebook-opener" id="notebook"><div class="num">Back of the book</div>'
                 '<h2>The Notebook</h2><p>The world rules, people, places, timeline and plan behind the story.</p></header>')
    toc.append('<li class="group">The Notebook</li>')
    for i, (sid, title, desc, src) in enumerate(SECTIONS):
        body = premise_html() if src is None else md_to_html((ROOT / src).read_text())
        body = place_figures(sid, body)
        toc.append(f'<li><a href="#{sid}"><span class="n">{ROMAN[i]}</span><span class="t">{title}</span>'
                   f'<span class="d">{desc}</span></a></li>')
        parts.append(
            f'<section class="part" id="{sid}"><header class="opener"><div class="num">Section {ROMAN[i]}</div>'
            f"<h2>{title}</h2><p>{desc}</p></header><div class=\"prose\">{body}</div></section>")

    river = ('<svg class="river" viewBox="0 0 640 46" preserveAspectRatio="none" aria-hidden="true">'
             '<path d="M2,30 C60,30 70,10 130,12 S210,40 280,30 S380,8 440,16"/>'
             '<path class="clean" d="M440,16 C500,24 540,36 638,22"/></svg>')
    return f"""<title>Downstream</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@700;800&family=IBM+Plex+Mono:wght@400;500;600&family=Literata:ital,opsz,wght@0,7..72,400;0,7..72,700;1,7..72,400&display=swap">
<style>{CSS}</style>
<div class="progress" aria-hidden="true"></div>
<header class="cover" id="top">
  <div class="kicker">A Resident Evil story</div>
  <h1>Downstream</h1>
  {river}
  <p class="tagline">The missile was on time. The river was faster.</p>
  <div class="meta">Part One in progress · Chapter 1<br>One family · One year · Day 0 to Day 365</div>
</header>
<nav class="contents" id="contents" aria-label="Contents"><h2>Contents</h2><ol>{''.join(toc)}</ol></nav>
{''.join(parts)}
<p class="end">End of the notebook · more chapters coming</p>
<a class="to-top" href="#contents">Contents</a>
<script>{JS}</script>
"""


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reader" / "downstream.html"
    out.write_text(build())
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
