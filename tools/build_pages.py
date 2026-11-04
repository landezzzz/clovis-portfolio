#!/usr/bin/env python3
"""Build step (runs on Netlify, output in dist/).

index.html is the single source: every <div data-page="..."> carries data-title / data-desc.
For each page this writes dist/<page>/index.html containing only that page (plus header, footer
and shared viewers), with its own title, description and canonical address, so Google sees one
clear page per address. tools/fr.json adds French versions of home, services and contact under /fr/.
"""
import re, html, os, sys, json, shutil
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'dist')
SITE = 'https://clovisnkwawir.com'
NOINDEX = {'brief'}
COPY = ['img', 'icons', 'fonts', 'js', 'docs', 'robots.txt', 'favicon.ico']

src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
FRD = json.load(open(os.path.join(ROOT, 'tools', 'fr.json'), encoding='utf-8'))
FR_PAGES = FRD['pages']

starts = [(m.start(), m.group(1)) for m in re.finditer(r'<div data-page="([^"]+)"', src)]
end_all = src.index('<footer')
blocks = {}
for i, (a, name) in enumerate(starts):
    b = starts[i + 1][0] if i + 1 < len(starts) else src.rindex('</div>', a, end_all) + len('</div>')
    blocks[name] = (a, b)
first, last = starts[0][0], blocks[starts[-1][1]][1]
meta = {n: (html.unescape(t), html.unescape(d)) for n, t, d in re.findall(r'<div data-page="([^"]+)" data-title="([^"]*)" data-desc="([^"]*)"', src)}

def url(page, fr=False):
    return SITE + '/' + ('fr/' if fr else '') + ('' if page == 'home' else page + '/')

def path(page, fr=False):
    return '/' + ('fr/' if fr else '') + ('' if page == 'home' else page + '/')

def attr(t):
    return html.escape(t, quote=True)

def set_meta(doc, title, desc, canon):
    doc = re.sub(r'<title>.*?</title>', lambda m: f'<title>{html.escape(title, quote=False)}</title>', doc, count=1)
    subs = [(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{attr(desc)}">'),
            (r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{canon}">'),
            (r'<meta property="og:url" content="[^"]*">', f'<meta property="og:url" content="{canon}">'),
            (r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{attr(title)}">'),
            (r'<meta name="twitter:title" content="[^"]*">', f'<meta name="twitter:title" content="{attr(title)}">'),
            (r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{attr(desc)}">'),
            (r'<meta name="twitter:description" content="[^"]*">', f'<meta name="twitter:description" content="{attr(desc)}">')]
    for pat, rep in subs:
        doc = re.sub(pat, lambda m: rep, doc, count=1)
    return doc

def translate(chunk):
    for en, fr in FRD['html']:
        chunk = chunk.replace(en, fr)
    S = FRD['strings']
    def tnode(m):
        t = m.group(1); k = ' '.join(html.unescape(t).split())
        if k in S:
            lead = t[:len(t) - len(t.lstrip())]; trail = t[len(t.rstrip()):]
            return '>' + lead + html.escape(S[k], quote=False) + trail + '<'
        return m.group(0)
    def tattr(m):
        k = html.unescape(m.group(2))
        return f'{m.group(1)}="{attr(S[k])}"' if k in S else m.group(0)
    parts = re.split(r'(<script\b.*?</script>|<style\b.*?</style>|<svg\b.*?</svg>)', chunk, flags=re.S)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r'>([^<>]+)<', tnode, parts[i])
        parts[i] = re.sub(r'\b(placeholder|aria-label|alt)="([^"]*)"', tattr, parts[i])
    return ''.join(parts)

def build(page, fr=False):
    a, b = blocks[page]
    block = src[a:b].replace(' hidden>', '>', 1) if src[a:b].startswith(f'<div data-page="{page}"') else src[a:b]
    block = re.sub(r'^(<div data-page="[^"]+")([^>]*?) hidden>', r'\1\2>', block, count=1)
    head, tail = src[:first], src[last:].replace('var ALLP=PAGES;/*ALLP*/', 'var ALLP=' + json.dumps(list(meta)) + ';')
    doc = head + block + '\n' + tail
    title, desc = FRD['meta'][page] if fr else meta[page]
    doc = set_meta(doc, title, desc, url(page, fr))
    if page in NOINDEX:
        doc = doc.replace('<base href="/">', '<base href="/">\n<meta name="robots" content="noindex">', 1)
    # language versions
    has_fr = page in FR_PAGES
    if has_fr:
        alt = (f'<link rel="alternate" hreflang="en" href="{url(page)}">\n<link rel="alternate" hreflang="fr" href="{url(page, True)}">\n'
               f'<link rel="alternate" hreflang="x-default" href="{url(page)}">\n')
        doc = re.sub(r'(<link rel="canonical"[^>]*>\n)', lambda m: m.group(1) + alt, doc, count=1)
    if fr:
        doc = doc.replace('<html lang="en">', '<html lang="fr">', 1)
        doc = re.sub(r'<div data-page="([^"]+)" data-title="[^"]*" data-desc="[^"]*"',
                     lambda m: f'<div data-page="{m.group(1)}" data-title="{attr(title)}" data-desc="{attr(desc)}"', doc, count=1)
        hs, he = doc.index('<header'), doc.index('</header>')
        fs, fe = doc.index('<footer'), doc.index('</footer>')
        ps = doc.index('<div data-page=')
        tail_js = doc[fe:]
        for en, frs in FRD.get('js', []):
            tail_js = tail_js.replace(en, frs)
        doc = doc[:hs] + translate(doc[hs:he]) + doc[he:ps] + translate(doc[ps:fs]) + translate(doc[fs:fe]) + translate(tail_js)
        # shared viewers (lightbox, catalog, video) sit after the footer: translate their labels too
        for p in FR_PAGES:
            doc = doc.replace(f'<a href="{path(p)}"', f'<a href="{path(p, True)}"').replace(f' href="{path(p)}" class=', f' href="{path(p, True)}" class=')
            doc = re.sub(rf'(<a\b[^>]*?) href="{re.escape(path(p))}"', lambda m: m.group(1) + f' href="{path(p, True)}"', doc)
        doc = doc.replace('href="/#process"', 'href="/fr/#process"').replace('href="/#about"', 'href="/fr/#about"')
        doc = re.sub(r'<a class="lang-btn"[^>]*>FR</a>', lambda m: f'<a class="lang-btn" id="langBtn" href="{path(page)}" hreflang="en" lang="en" aria-label="English version">EN</a>', doc, count=1)
        doc = doc.replace('<meta property="og:type" content="website">', '<meta property="og:type" content="website">\n<meta property="og:locale" content="fr_FR">', 1)
    else:
        target = path(page, True) if has_fr else '/fr/'
        doc = re.sub(r'(<a class="lang-btn" id="langBtn" href=")[^"]*', lambda m: m.group(1) + target, doc, count=1)
    return doc

def write(rel, doc):
    out = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write(doc)

if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)
for c in COPY:
    s = os.path.join(ROOT, c)
    if os.path.isdir(s): shutil.copytree(s, os.path.join(OUT, c))
    elif os.path.exists(s): shutil.copy2(s, OUT)

urls = []
for page in meta:
    rel = 'index.html' if page == 'home' else f'{page}/index.html'
    write(rel, build(page))
    if page not in NOINDEX:
        urls.append((url(page), '1.0' if page == 'home' else '0.9' if '/' not in page else '0.7'))
for page in FR_PAGES:
    rel = 'fr/index.html' if page == 'home' else f'fr/{page}/index.html'
    write(rel, build(page, True))
    urls.append((url(page, True), '0.9'))
write('404.html', build('home').replace('<base href="/">', '<base href="/">\n<meta name="robots" content="noindex">', 1))

today = date.today().isoformat()
sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
sm += [f'  <url><loc>{u}</loc><lastmod>{today}</lastmod><priority>{p}</priority></url>' for u, p in urls]
sm.append('</urlset>')
open(os.path.join(OUT, 'sitemap.xml'), 'w', encoding='utf-8').write('\n'.join(sm) + '\n')
print(f'built {len(urls)} indexable pages into dist/')
