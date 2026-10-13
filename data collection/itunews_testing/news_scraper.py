"""ITU news: discover archive URLs, visit EACH article, export full text.

pip install playwright
playwright install chromium
python news_scraper_full.py --max-articles 10
python news_scraper_full.py

To reuse an existing CSV of article URLs:
python news_scraper_full.py --input itu_news_articles.csv
"""
import argparse
import asyncio
import csv
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
NEWS = 'https://en.itu.dk/About-ITU/Press/News'
PATH = re.compile(r'^/About-ITU/Press/News-from-ITU/\d{4}/[^/]+/?$', re.I)
FIELDS = ['title', 'date', 'author', 'summary', 'content', 'url', 'content_chars', 'status', 'keywords']
BYLINE = re.compile(r'\bWritten\s+(\d{1,2}\s+[A-Za-z]+,?\s+\d{4}(?:\s+\d{1,2}:\d{2})?)\s+by\s+([^\n]+)', re.I)


def canonical(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path.rstrip('/'), '', ''))


def clean(text):
    text = (text or '').replace('\xa0', ' ').replace('\r', '')
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(s.strip() for s in text.splitlines())).strip()


async def discover(page, max_pages):
    found = []
    seen = set()
    for n in range(1, max_pages + 1):
        listing = NEWS if n == 1 else f'{NEWS}?page={n}'
        print(f'ARCHIVE {n}: {listing}', flush=True)
        response = await page.goto(listing, wait_until='domcontentloaded', timeout=60000)
        if response and response.status >= 400:
            break
        await page.locator('a[href]').first.wait_for(timeout=15000)
        await page.wait_for_timeout(900)
        links = await page.locator('a[href]').evaluate_all('els => els.map(a => a.href)')
        new = []
        for link in links:
            p = urlsplit(link)
            if p.hostname == 'en.itu.dk' and PATH.fullmatch(p.path):
                url = canonical(link)
                if url not in seen:
                    seen.add(url)
                    new.append(url)
        print(f'  New article links: {len(new)}', flush=True)
        if not new:
            break
        found.extend(new)
    return found


async def extract(page, url, fallback):
    # IMPORTANT: a fresh navigation to the INDIVIDUAL article URL.
    response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
    if response and response.status >= 400:
        raise RuntimeError(f'HTTP {response.status}')
    await page.locator('h1').first.wait_for(timeout=15000)
    await page.wait_for_timeout(250)
    data = await page.locator('h1').first.evaluate('''h1 => {
        const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
        const meta = n => document.querySelector(`meta[name="${n}"],meta[property="${n}"]`)?.content || '';
        const title = norm(h1.innerText);
        // Prefer the narrowest ancestor containing headline, byline, and substantial article text.
        let el = h1;
        while (el && el !== document.body) {
            const t = el.innerText || '';
            if (/Written\\s+\\d{1,2}\\s+[A-Za-z]+/i.test(t) && t.length > 500) break;
            el = el.parentElement;
        }
        const container = el && el !== document.body ? el : (document.querySelector('main') || document.body);
        const copy = container.cloneNode(true);
        copy.querySelectorAll('script,style,nav,footer,form,button,aside,.breadcrumb,.social,.share,.related-news').forEach(x => x.remove());
        return {title, raw: copy.innerText || '', description: meta('description') || meta('og:description')};
    }''')
    raw = clean(data['raw'])
    title = data['title']
    pos = raw.find(title)
    if pos >= 0:
        raw = clean(raw[pos + len(title):])
    # The page sometimes concatenates tag labels, byline and body text.
    # Read the byline's author link directly from the DOM when possible.
    meta = await page.evaluate(r"""() => {
        const elements = [...document.querySelectorAll('p, div, span, time')];
        const candidates = elements.filter(el => {
            const t = (el.innerText || '').trim();
            return /^Written\s+\d{1,2}\s+[A-Za-z]+/i.test(t) && t.length < 250;
        });
        candidates.sort((a,b) => (a.innerText || '').length - (b.innerText || '').length);
        const el = candidates[0];
        const authorLink = el?.querySelector('a');
        return { bylineText: (el?.innerText || '').trim(),
                 author: (authorLink?.innerText || '').trim() };
    }""")
    # Read keyword/tag links from the article DOM, between the headline and byline.
    # This avoids relying on joined text such as "Researchartificial intelligence".
    tag_data = await page.locator('h1').first.evaluate(r"""h1 => {
        const all = [...document.querySelectorAll('a[href]')];
        const byline = [...document.querySelectorAll('p,div,span,time')]
          .filter(e => /^Written\s+\d{1,2}\s+[A-Za-z]+/i.test((e.innerText || '').trim())
                    && (e.innerText || '').length < 250)
          .sort((a,b) => (a.innerText || '').length - (b.innerText || '').length)[0];
        if (!byline) return [];
        const before = node => !!(node.compareDocumentPosition(byline) & Node.DOCUMENT_POSITION_FOLLOWING);
        const afterTitle = node => !!(h1.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING);
        return all.filter(a => afterTitle(a) && before(a))
          .filter(a => {
             const label = (a.innerText || '').trim();
             const href = a.getAttribute('href') || '';
             return label && label.length <= 55 && !a.closest('nav,header,footer,aside')
               && !href.startsWith('mailto:') && !href.startsWith('tel:');
          })
          .map(a => ({label: (a.innerText || '').replace(/\s+/g,' ').trim(), href:a.getAttribute('href')}));
    }""")
    # Find date boundary even when there are no spaces around the byline.
    marker = re.search(r'Written\s+(\d{1,2}\s+[A-Za-z]+,?\s+\d{4}\s+\d{1,2}:\d{2})\s+by\s+', raw, re.I)
    date = marker.group(1).strip() if marker else ''
    author = meta.get('author', '')
    if not author and marker:
        # A conservative fallback; flag the result for review.
        m = re.match(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})', raw[marker.end():])
        author = m.group(1) if m else ''
    if marker:
        before = clean(raw[:marker.start()])
        remaining = raw[marker.end():]
        if author and remaining.startswith(author):
            content = clean(remaining[len(author):])
        else:
            content = clean(remaining)
    else:
        before = ''
        content = raw
    # The byline follows the summary AND the tag labels. Remove tags from
    # the end of the pre-byline text, longest labels first, without changing
    # the article body. Only accept labels that really form that suffix.
    remainder = before.rstrip()
    candidates = list(dict.fromkeys(x['label'] for x in tag_data))
    keywords = []
    while remainder:
        matched = next((x for x in sorted(candidates, key=len, reverse=True)
                        if remainder.endswith(x)), None)
        if not matched:
            break
        keywords.insert(0, matched)
        remainder = remainder[:-len(matched)].rstrip()
        candidates.remove(matched)
    summary = remainder or fallback.get('summary', '').strip() or data['description']
    status = 'OK' if len(content) >= 300 and marker and author else ('CHECK_SHORT' if len(content) < 300 else 'CHECK_BYLINE')
    return {'title': title or fallback.get('title', ''), 'date': date, 'author': author,
            'summary': summary, 'content': content, 'url': url,
            'content_chars': len(content), 'status': status, 'keywords': '; '.join(keywords)}


async def main(args):
    sources = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not args.show_browser)
        page = await browser.new_page()
        try:
            if args.input:
                with open(args.input, newline='', encoding='utf-8-sig') as f:
                    for row in csv.DictReader(f):
                        url = canonical((row.get('url') or '').strip())
                        if url and PATH.fullmatch(urlsplit(url).path):
                            sources[url] = row
                urls = list(sources)
            else:
                urls = await discover(page, args.max_pages)
            if args.max_articles:
                urls = urls[:args.max_articles]
            print(f'VISITING {len(urls)} individual article pages', flush=True)
            output = HERE / args.output
            with output.open('w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS)
                writer.writeheader()
                for i, url in enumerate(urls, 1):
                    print(f'OPEN ARTICLE [{i}/{len(urls)}]: {url}', flush=True)
                    try:
                        record = await extract(page, url, sources.get(url, {}))
                    except Exception as e:
                        print(f'  ERROR: {e}', flush=True)
                        record = {'url': url, 'status': f'ERROR: {str(e)[:90]}', 'content_chars': 0}
                    writer.writerow(record)
                    f.flush()
                    print(f'  {record.get("status")} | {record.get("content_chars", 0)} chars | {record.get("title", "")}', flush=True)
                    await asyncio.sleep(0.5)
            print(f'CSV saved: {output}', flush=True)
        finally:
            await browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, help='Existing CSV with url column; skip archive discovery')
    parser.add_argument('--output', default='itu_news_full_content.csv')
    parser.add_argument('--max-pages', type=int, default=200)
    parser.add_argument('--max-articles', type=int)
    parser.add_argument('--show-browser', action='store_true')
    asyncio.run(main(parser.parse_args()))
