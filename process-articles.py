#!/usr/bin/env python3
"""
BrassOps Blog Article Processor
Reads raw articles from raw-articles/, applies all transformations,
writes processed articles to blog/.
"""
import json, re, os, sys
from datetime import datetime

# ── Config ──
RAW_DIR = 'raw-articles'
OUT_DIR = 'blog'
MAPPING_FILE = 'article-mapping.json'

AUTHOR_NAME = "Rich O'Brien"
AUTHOR_INITIALS = "RO"
LINKEDIN_URL = "https://www.linkedin.com/in/richard-o-brien-7493a0402/?isSelfProfile=true"

BREVO_IFRAME = '<div style="max-width:540px;margin:40px auto;"><iframe width="540" height="305" src="https://95e271d5.sibforms.com/serve/MUIFAP6ZnwlLAjy5iaThuqpbE3FXO9Cx5wiid5j27YIrtViQBrgZmNyThiaROf5LiHuOAMnP0hYF4klLfpbshO30CKIqpcYlOpslMBppnltmsxEy1xFeb85Td9-5-tJTfQmb9kzlVa-pzA41ln2_qphx55Uq69IwWeKm2KDI3G6-ghI09VQfMFjVW_YJ8C7nhU1HefEJ66hmkX3iww==" frameborder="0" scrolling="auto" allowfullscreen style="display:block;margin-left:auto;margin-right:auto;max-width:100%;"></iframe></div>'

# ── New CSS (white bg, BrassOps fonts) ──
NEW_CSS = """
  :root { --red: #ef4444; --red-dim: rgba(239,68,68,0.08); --navy: #111111; --text: #1a1a1a; --text-light: #444444; --accent: #ef4444; --border: #e4e4e7; --bg: #ffffff; --green: #16a34a; --brass: #ef4444; --brass-light: #fecaca; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Barlow', sans-serif; color: var(--text); background: var(--bg); line-height: 1.8; font-size: 17px; }
  .breadcrumb { font-family: 'Rajdhani', sans-serif; font-size: 13px; color: #666; max-width: 780px; margin: 0 auto; padding: 76px 24px 0; }
  .breadcrumb a { color: var(--accent); text-decoration: none; } .breadcrumb span { margin: 0 6px; }
  .hero { max-width: 780px; margin: 0 auto; padding: 24px 24px 40px; border-bottom: 3px solid var(--accent); }
  .hero-badge { display: inline-block; font-family: 'Rajdhani', sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; background: var(--accent); color: #fff; padding: 5px 14px; border-radius: 4px; margin-bottom: 20px; }
  .hero h1 { font-family: 'Rajdhani', sans-serif; font-size: clamp(28px, 4.5vw, 40px); font-weight: 700; line-height: 1.18; color: var(--navy); margin-bottom: 16px; }
  .hero-subtitle { font-size: 18px; color: #333; line-height: 1.6; }
  .hero-meta { margin-top: 22px; display: flex; flex-wrap: wrap; gap: 20px; font-family: 'Rajdhani', sans-serif; font-size: 14px; color: #666; align-items: center; }
  .hero-meta strong { color: var(--text); } .hero-meta .divider { width: 1px; height: 16px; background: var(--border); }
  article { max-width: 780px; margin: 0 auto; padding: 48px 24px 32px; }
  article h2 { font-family: 'Rajdhani', sans-serif; font-size: 26px; font-weight: 700; color: var(--navy); margin: 48px 0 16px; padding-top: 8px; border-top: 1px solid var(--border); }
  article h2:first-of-type { border-top: none; margin-top: 0; }
  article h3 { font-family: 'Rajdhani', sans-serif; font-size: 19px; font-weight: 700; color: #333; margin: 32px 0 10px; }
  article p { margin-bottom: 20px; }
  article a { color: var(--accent); text-decoration: underline; text-decoration-color: rgba(239,68,68,0.3); text-underline-offset: 3px; }
  article a:hover { text-decoration-color: var(--accent); }
  article ul, article ol { margin: 0 0 20px 24px; } article li { margin-bottom: 8px; }
  .takeaway { background: var(--navy); color: #fff; padding: 24px 28px; border-radius: 8px; margin: 28px 0; }
  .takeaway::before { content: 'KEY TAKEAWAY'; font-family: 'Rajdhani', sans-serif; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; color: var(--accent); display: block; margin-bottom: 8px; }
  .takeaway p { color: rgba(255,255,255,0.92); margin-bottom: 0; font-size: 17px; line-height: 1.7; } .takeaway strong { color: var(--brass-light); }
  .callout { border-left: 4px solid var(--accent); background: var(--red-dim); padding: 18px 22px; margin: 24px 0; border-radius: 0 8px 8px 0; }
  .callout p { margin-bottom: 0; font-size: 16px; } .callout strong { color: var(--navy); }
  .warning { border-left: 4px solid #dc2626; background: #fef2f2; padding: 18px 22px; margin: 24px 0; border-radius: 0 8px 8px 0; }
  .warning::before { content: '\\26A0 LIABILITY NOTE'; font-family: 'Rajdhani', sans-serif; font-size: 10px; font-weight: 700; letter-spacing: 1px; color: #dc2626; display: block; margin-bottom: 8px; }
  .warning p { margin-bottom: 0; font-size: 16px; }
  .scenario-box { background: #f9fafb; border: 1px solid var(--border); border-radius: 8px; padding: 20px 24px; margin: 24px 0; }
  .scenario-box .label { font-family: 'Rajdhani', sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: #dc2626; margin-bottom: 6px; }
  .scenario-box .label.good { color: var(--green); }
  .scenario-box h3 { font-family: 'Rajdhani', sans-serif; font-size: 17px; font-weight: 700; color: var(--navy); margin: 0 0 8px; }
  .scenario-box p { margin-bottom: 8px; font-size: 16px; } .scenario-box p:last-child { margin-bottom: 0; }
  .sign-box { background: #f9fafb; border: 1px solid var(--border); border-radius: 8px; padding: 20px 24px; margin: 20px 0; }
  .sign-box .num { font-family: 'Rajdhani', sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #dc2626; margin-bottom: 6px; }
  .sign-box h3 { font-family: 'Rajdhani', sans-serif; font-size: 17px; font-weight: 700; color: var(--navy); margin: 0 0 8px; }
  .sign-box p { margin-bottom: 8px; font-size: 16.5px; } .sign-box p:last-child { margin-bottom: 0; }
  .cta-block { background: linear-gradient(135deg, #dc2626, #ef4444); padding: 36px 32px; border-radius: 12px; margin: 44px 0; text-align: center; }
  .cta-block h3 { font-family: 'Rajdhani', sans-serif; font-size: 22px; color: #fff; margin: 0 0 10px; }
  .cta-block p { color: rgba(255,255,255,0.85); font-size: 15px; margin-bottom: 22px; max-width: 500px; margin-left: auto; margin-right: auto; }
  .cta-btn { display: inline-block; font-family: 'Rajdhani', sans-serif; font-size: 15px; font-weight: 700; color: #dc2626; background: #fff; padding: 13px 34px; border-radius: 8px; text-decoration: none; letter-spacing: 0.5px; text-transform: uppercase; }
  .cta-btn:hover { background: #f5f5f5; }
  .brevo-section { max-width: 780px; margin: 0 auto; padding: 0 24px; }
  .author-box { display: flex; gap: 18px; padding: 24px; background: #f9fafb; border: 1px solid var(--border); border-radius: 12px; margin: 44px 0 28px; max-width: 780px; margin-left: auto; margin-right: auto; }
  .author-photo { width: 64px; height: 64px; border-radius: 50%; background: #111; flex-shrink: 0; display: flex; align-items: center; justify-content: center; color: var(--accent); font-family: 'Rajdhani', sans-serif; font-weight: 700; font-size: 22px; }
  .author-info h4 { font-family: 'Rajdhani', sans-serif; font-size: 15px; color: var(--navy); margin-bottom: 3px; }
  .author-info .author-title { font-family: 'Rajdhani', sans-serif; font-size: 12.5px; color: #666; margin-bottom: 7px; }
  .author-info p { font-size: 14px; line-height: 1.6; margin-bottom: 0; }
  .author-info a { color: var(--accent); }
  .related-section { max-width: 780px; margin: 0 auto; padding: 40px 24px 20px; border-top: 2px solid var(--accent); }
  .related-label { font-family: 'Rajdhani', sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--accent); margin-bottom: 18px; }
  .related-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; }
  .related-card { border: 1px solid var(--border); border-radius: 8px; padding: 18px; }
  .related-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.06); }
  .related-card .card-type { font-family: 'Rajdhani', sans-serif; font-size: 10px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--accent); margin-bottom: 6px; }
  .related-card h4 { font-family: 'Rajdhani', sans-serif; font-size: 16px; font-weight: 600; line-height: 1.35; margin-bottom: 6px; }
  .related-card h4 a { color: var(--navy); text-decoration: none; } .related-card h4 a:hover { color: var(--accent); }
  .related-card p { font-size: 13px; color: #666; line-height: 1.5; margin-bottom: 0; }
  table { width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 15px; }
  th { background: #f3f4f6; font-family: 'Rajdhani', sans-serif; font-weight: 700; text-align: left; padding: 10px 14px; border-bottom: 2px solid var(--border); }
  td { padding: 10px 14px; border-bottom: 1px solid var(--border); }
  /* Nav */
  .site-nav { position: fixed; top: 0; left: 0; right: 0; z-index: 100; display: flex; align-items: center; justify-content: space-between; padding: 0 clamp(1rem,4vw,3rem); height: 56px; background: rgba(10,10,10,0.95); backdrop-filter: blur(20px); border-bottom: 1px solid rgba(255,255,255,0.06); }
  .site-nav .nb { font-family: 'Rajdhani', sans-serif; font-weight: 700; font-size: 1.1rem; color: #ededed; text-decoration: none; letter-spacing: 0.04em; }
  .site-nav .nb .bo { color: #ef4444; }
  .site-nav .nl { display: flex; gap: 1.5rem; align-items: center; }
  .site-nav .nl a { font-family: 'Barlow', sans-serif; font-size: 0.85rem; font-weight: 500; color: #71717a; text-decoration: none; }
  .site-nav .nl a:hover { color: #ededed; }
  .site-nav .nl .la { background: linear-gradient(135deg,#ef4444,#dc2626); color: #fff !important; padding: 0.35rem 1rem; border-radius: 8px; font-weight: 600; font-size: 0.8rem; }
  .hb { display: none; background: none; border: none; cursor: pointer; padding: 0.4rem; z-index: 110; }
  .hb svg { width: 22px; height: 22px; stroke: #ededed; stroke-width: 2; fill: none; }
  @media(max-width:768px) { .hb { display: block; } .site-nav .nl { display: none; flex-direction: column; align-items: stretch; gap: 0; position: fixed; top: 56px; left: 0; right: 0; background: rgba(10,10,10,0.95); backdrop-filter: blur(24px); border-bottom: 1px solid rgba(255,255,255,0.08); padding: 0.5rem 0; max-height: 0; overflow: hidden; transition: max-height 0.35s; } .site-nav .nl.open { display: flex; max-height: 400px; padding: 0.75rem 0; } .site-nav .nl a { padding: 0.75rem clamp(1rem,4vw,3rem); font-size: 0.95rem; border-bottom: 1px solid rgba(255,255,255,0.04); } .site-nav .nl .la { margin: 0.5rem clamp(1rem,4vw,3rem) 0.25rem; text-align: center; padding: 0.65rem 1rem; border-radius: 10px; } }
  /* Footer */
  .site-footer { background: #0a0a0a; color: #71717a; padding: 3rem 1.5rem 2.5rem; text-align: center; }
  .site-footer .fb { font-family: 'Rajdhani', sans-serif; font-size: 1.1rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #71717a; margin-bottom: 0.5rem; }
  .site-footer .fb .bo { color: #ef4444; }
  .site-footer .tl { font-size: 0.8rem; color: #52525b; margin-bottom: 0.75rem; font-style: italic; }
  .site-footer .fl { display: flex; justify-content: center; gap: 1.5rem; margin-bottom: 0.75rem; }
  .site-footer .fl a { font-size: 0.75rem; color: #52525b; text-decoration: none; }
  .site-footer .fl a:hover { color: #a1a1aa; }
  .site-footer .cp { font-size: 0.7rem; color: #52525b; }
  @media (max-width: 600px) { .hero h1 { font-size: 26px; } .hero { padding: 20px 16px 32px; } article { padding: 32px 16px 24px; } .author-box { flex-direction: column; align-items: center; text-align: center; } }
"""

NAV_HTML = """<nav class="site-nav">
  <a href="https://brassops.com" class="nb">Brass<span class="bo">Ops</span></a>
  <button class="hb" aria-label="Toggle menu" aria-expanded="false"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg></button>
  <div class="nl">
    <a href="https://brassops.com/why-brassops">Why Brass<span style="color:#ef4444">Ops</span></a>
    <a href="https://brassops.com/briefing">Briefing</a>
    <a href="https://brassops.com/faq">FAQ</a>
    <a href="https://brassops.com/contact">Contact</a>
    <a href="https://app.brassops.com" class="la" target="_blank" rel="noopener">Launch App</a>
  </div>
</nav>"""

FOOTER_HTML = """<footer class="site-footer">
  <p class="fb">Brass<span class="bo">Ops</span></p>
  <p class="tl">Built for those who train to protect.</p>
  <div class="fl"><a href="https://brassops.com/privacy">Privacy Policy</a><a href="https://brassops.com/terms">Terms of Service</a></div>
  <p class="cp">&copy; 2026 BrassOps. All rights reserved.</p>
</footer>"""

HAMBURGER_JS = """<script>
document.addEventListener('DOMContentLoaded',()=>{
  const h=document.querySelector('.hb'),n=document.querySelector('.nl');
  if(h&&n)h.addEventListener('click',()=>{const o=n.classList.toggle('open');h.setAttribute('aria-expanded',o);h.innerHTML=o?'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>':'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>';});
});
</script>"""

AUTHOR_BOX = f"""<div class="brevo-section">{BREVO_IFRAME}</div>
  <div class="author-box" style="max-width:780px;margin:28px auto;">
    <div class="author-photo">{AUTHOR_INITIALS}</div>
    <div class="author-info">
      <h4>{AUTHOR_NAME}</h4>
      <div class="author-title">Founder at BrassOps</div>
      <p>{AUTHOR_NAME} is the founder of BrassOps, the range intelligence platform built for law enforcement firearms programs. Connect on <a href="{LINKEDIN_URL}" target="_blank" rel="noopener">LinkedIn</a>.</p>
    </div>
  </div>"""

def slugify(title):
    s = title.lower()
    s = re.sub(r"[''']", '', s)
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = s.strip('-')
    return s[:80]

def format_date_nice(date_str):
    d = datetime.strptime(date_str, '%Y-%m-%d')
    return d.strftime('%B %d, %Y').replace(' 0', ' ')

def process_article(article, start=None, end=None):
    src_path = os.path.join(RAW_DIR, article['src'])
    if not os.path.exists(src_path):
        print(f"  SKIP: {src_path} not found")
        return None

    with open(src_path, 'r', encoding='utf-8') as f:
        html = f.read()

    slug = slugify(article['title'])
    out_name = f"{article['num']}-{slug}.html"
    pub_date = article['date']
    pub_date_nice = format_date_nice(pub_date)

    # 1. Replace Google Fonts link
    html = re.sub(
        r"<link[^>]*fonts\.googleapis\.com/css2\?family=[^>]*>",
        '<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700;800&family=Rajdhani:wght@400;500;600;700&display=swap" rel="stylesheet">',
        html
    )

    # 2. Replace entire <style> block (use lambda to avoid regex replacement issues)
    new_style = f'<style>{NEW_CSS}</style>'
    html = re.sub(
        r'<style>.*?</style>',
        lambda m: new_style,
        html, flags=re.DOTALL
    )

    # 3. Author name replacements
    html = html.replace('[Author Name]', AUTHOR_NAME)
    html = html.replace('[Title]', 'Founder')
    html = html.replace('[Rank/Agency/Branch]', 'Law Enforcement Professional')
    html = html.replace('[credential description]', 'the founder of BrassOps')
    html = html.replace('[relevant function]', 'product development and strategy')
    html = html.replace('[he/she/they]', 'he')
    html = re.sub(r'Connect on <a href="#">LinkedIn</a>',
                  f'Connect on <a href="{LINKEDIN_URL}" target="_blank" rel="noopener">LinkedIn</a>', html)

    # 4. Schema.org author name
    html = re.sub(r'"name"\s*:\s*"[^"]*Author[^"]*"', f'"name":"{AUTHOR_NAME}"', html)
    html = re.sub(r'"name"\s*:\s*"\[Author Name\]"', f'"name":"{AUTHOR_NAME}"', html)

    # 5. Update datePublished in schema
    html = re.sub(r'"datePublished"\s*:\s*"[^"]*"', f'"datePublished":"{pub_date}"', html)

    # 6. Update visible publish date in hero-meta
    # Match patterns like "Published <strong>July 24, 2026</strong>"
    html = re.sub(
        r'Published\s*<strong>[^<]*</strong>',
        f'Published <strong>{pub_date_nice}</strong>',
        html
    )

    # 7. CTA URLs — replace /demo/ with full contact URL
    html = html.replace('href="/demo/"', 'href="https://brassops.com/contact/"')
    html = html.replace("href='/demo/'", 'href="https://brassops.com/contact/"')

    # 8. Internal links to full URLs
    html = re.sub(r'href="(/blog/[^"]*)"', r'href="https://brassops.com\1"', html)
    html = re.sub(r'href="(/training-documentation-law-enforcement/[^"]*)"', r'href="https://brassops.com\1"', html)
    html = re.sub(r'href="(/firearms-qualification-standards/[^"]*)"', r'href="https://brassops.com\1"', html)
    html = re.sub(r'href="(/case-law/[^"]*)"', r'href="https://brassops.com\1"', html)
    html = re.sub(r'href="(/insights/[^"]*)"', r'href="https://brassops.com\1"', html)
    html = html.replace('href="/"', 'href="https://brassops.com/"')

    # 9. Replace author box with new one (including Brevo iframe)
    # Use string find/replace instead of regex to avoid backslash issues
    author_start = html.find('<div class="author-box">')
    if author_start != -1:
        # Find the closing of the author-box div (it has nested divs)
        depth = 0
        i = author_start
        author_end = -1
        while i < len(html):
            if html[i:i+4] == '<div':
                depth += 1
            elif html[i:i+6] == '</div>':
                depth -= 1
                if depth == 0:
                    author_end = i + 6
                    break
            i += 1
        if author_end != -1:
            html = html[:author_start] + AUTHOR_BOX + html[author_end:]

    # 10. Replace author avatar initials (any 2-letter combo)
    html = re.sub(
        r'<div class="author-photo">[A-Z]{2}</div>',
        f'<div class="author-photo">{AUTHOR_INITIALS}</div>',
        html
    )

    # 11. Add nav after <body>
    html = re.sub(r'<body>\s*', f'<body>\n{NAV_HTML}\n', html)

    # 12. Add footer + hamburger JS before </body>
    html = re.sub(r'</body>', f'{FOOTER_HTML}\n{HAMBURGER_JS}\n</body>', html)

    # 13. Update canonical URL
    html = re.sub(
        r'<link rel="canonical" href="[^"]*">',
        f'<link rel="canonical" href="https://brassops.com/blog/{out_name}">',
        html
    )

    # Write output
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, out_name)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  ✓ {out_name}")
    return {
        'slug': f"{article['num']}-{slug}",
        'title': article['title'],
        'date': pub_date,
        'file': out_name,
    }

def main():
    with open(MAPPING_FILE, 'r') as f:
        articles = json.load(f)

    # Support processing a range: python process-articles.py 1 10
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end = int(sys.argv[2]) if len(sys.argv) > 2 else len(articles)

    print(f"Processing articles {start}-{end} of {len(articles)}...")
    batch = articles[start-1:end]

    results = []
    for article in batch:
        result = process_article(article)
        if result:
            results.append(result)

    print(f"\nDone. {len(results)} articles processed to {OUT_DIR}/")

if __name__ == '__main__':
    main()
