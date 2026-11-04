#!/usr/bin/env python3
"""Build step (runs on Netlify): writes a real HTML file for every page of the site,
so each project/service page has its own address, title and description for Google.

index.html stays the single source. Each <div data-page="..."> carries data-title and data-desc.
Output: <page>/index.html for every page, 404.html and sitemap.xml.
"""
import re, html, os, sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://clovisnkwawir.com'
NOINDEX = {'brief'}

src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
pages = re.findall(r'<div data-page="([^"]+)" data-title="([^"]*)" data-desc="([^"]*)"', src)
if not pages:
    sys.exit('no pages found')

def meta_swap(doc, title, desc, url, noindex=False):
    doc = re.sub(r'<title>.*?</title>', f'<title>{title}</title>', doc, count=1)
    doc = re.sub(r'(<meta name="description" content=")[^"]*', r'\g<1>' + desc.replace('\\', '\\\\'), doc, count=1)
    doc = re.sub(r'(<link rel="canonical" href=")[^"]*', r'\g<1>' + url, doc, count=1)
    doc = re.sub(r'(<meta property="og:url" content=")[^"]*', r'\g<1>' + url, doc, count=1)
    for p in ('og:title', 'twitter:title'):
        doc = re.sub(rf'(<meta (?:property|name)="{p}" content=")[^"]*', r'\g<1>' + title.replace('\\', '\\\\'), doc, count=1)
    for p in ('og:description', 'twitter:description'):
        doc = re.sub(rf'(<meta (?:property|name)="{p}" content=")[^"]*', r'\g<1>' + desc.replace('\\', '\\\\'), doc, count=1)
    if noindex:
        doc = doc.replace('<base href="/">', '<base href="/">\n<meta name="robots" content="noindex">', 1)
    return doc

def show(doc, page):
    # hide home, show the requested page (so the content is in the HTML without JavaScript)
    doc = doc.replace('<div data-page="home"', '<div data-page="home" hidden', 1)
    doc = re.sub(rf'(<div data-page="{re.escape(page)}"[^>]*?) hidden>', r'\1>', doc, count=1)
    return doc

urls = [(SITE + '/', '1.0')]
for page, title, desc in pages:
    if page == 'home':
        continue
    url = f'{SITE}/{page}/'
    doc = show(meta_swap(src, title, desc, url, page in NOINDEX), page)
    out = os.path.join(ROOT, page, 'index.html')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write(doc)
    if page not in NOINDEX:
        urls.append((url, '0.9' if page in ('services', 'work', 'contact', 'case-study') else '0.7'))

# 404: home page, not indexed
open(os.path.join(ROOT, '404.html'), 'w', encoding='utf-8').write(src.replace('<base href="/">', '<base href="/">\n<meta name="robots" content="noindex">', 1))

today = date.today().isoformat()
sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for u, pr in urls:
    sm.append(f'  <url><loc>{u}</loc><lastmod>{today}</lastmod><priority>{pr}</priority></url>')
sm.append('</urlset>')
open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8').write('\n'.join(sm) + '\n')
print(f'built {len(pages) - 1} pages + 404 + sitemap ({len(urls)} urls)')
