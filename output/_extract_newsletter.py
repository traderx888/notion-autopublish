"""Extract markdown content from newsletter HTML files."""
import re
import html as html_mod
import sys
import json


def strip_tags(s):
    """Remove all HTML tags."""
    s = re.sub(r'<[^>]+>', '', s)
    return html_mod.unescape(s)


def to_md_inline(s):
    """Convert inline HTML to markdown."""
    s = re.sub(r'<strong>(.*?)</strong>', r'**\1**', s)
    s = re.sub(r'<b>(.*?)</b>', r'**\1**', s)
    s = re.sub(r'<span style="color:#fff;font-weight:700">(.*?)</span>', r'**\1**', s)
    s = re.sub(r'<span[^>]*font-weight:\s*700[^>]*>(.*?)</span>', r'**\1**', s)
    s = re.sub(r'<span[^>]*font-weight:\s*bold[^>]*>(.*?)</span>', r'**\1**', s)
    s = re.sub(r'<em>(.*?)</em>', r'*\1*', s)
    s = re.sub(r'<i>(.*?)</i>', r'*\1*', s)
    # Remove remaining tags
    s = re.sub(r'<[^>]+>', '', s)
    s = html_mod.unescape(s)
    return s


def extract_markdown(html_content):
    """Convert newsletter HTML to clean markdown."""
    text = html_content

    # Remove script and style blocks
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<head>.*?</head>', '', text, flags=re.DOTALL)

    # Get body content only
    m = re.search(r'<body[^>]*>', text)
    if m:
        text = text[m.end():]
    m = re.search(r'</body>', text)
    if m:
        text = text[:m.start()]

    # Remove footer and everything after
    text = re.sub(r'<div class="footer">.*', '', text, flags=re.DOTALL)

    # Remove nav-links
    text = re.sub(r'<div class="nav-links">.*?</div>\s*</div>', '', text, flags=re.DOTALL)

    # Remove TOC
    text = re.sub(r'<div class="toc">.*?</div>\s*</div>\s*</div>', '', text, flags=re.DOTALL)

    # Remove issue-badge
    text = re.sub(r'<span class="issue-badge">.*?</span>', '', text, flags=re.DOTALL)

    result_parts = []

    # Extract h1 title
    title_match = re.search(r'<h1>(.*?)</h1>', text)
    if title_match:
        result_parts.append(f"# {strip_tags(title_match.group(1))}")
        text = text.replace(title_match.group(0), '')

    # Extract subtitle
    subtitle_match = re.search(r'<p class="subtitle">(.*?)</p>', text)
    if subtitle_match:
        result_parts.append(f"*{strip_tags(subtitle_match.group(1))}*")
        text = text.replace(subtitle_match.group(0), '')

    if result_parts:
        result_parts.append("")

    # --- Pre-process: convert all stat val/lbl pairs inline ---
    # Replace each <div class="stat"><div class="val"...>X</div><div class="lbl">Y</div></div>
    # with a marker
    def convert_single_stat(m):
        val_html = m.group(1)
        lbl_html = m.group(2)
        val = strip_tags(val_html).strip()
        lbl = strip_tags(lbl_html).strip()
        lbl = re.sub(r'\s+', ' ', lbl)
        return f'STAT_BULLET:- **{val}** \u2014 {lbl}:END_STAT'

    text = re.sub(
        r'<div class="stat">\s*<div class="val"[^>]*>(.*?)</div>\s*<div class="lbl">(.*?)</div>\s*</div>',
        convert_single_stat, text, flags=re.DOTALL
    )

    # Now replace stat-grid wrapper with newlines around the bullets
    text = re.sub(r'<div class="stat-grid">\s*', '\nSTAT_GRID_START\n', text)
    # Collect consecutive STAT_BULLETs
    text = re.sub(r'STAT_BULLET:(.*?):END_STAT', r'\1', text)
    text = text.replace('STAT_GRID_START\n', '')

    # --- Convert structural elements ---

    # callout blocks
    def convert_callout(m):
        callout_html = m.group(0)
        title_m = re.search(r'<div class="callout-title">(.*?)</div>', callout_html)
        title = strip_tags(title_m.group(1)).strip() if title_m else 'Key Points'
        items = re.findall(r'<li>(.*?)</li>', callout_html, re.DOTALL)
        lines = [f"\n## {title}\n"]
        for item in items:
            item_text = to_md_inline(item).strip()
            lines.append(f"- {item_text}")
        return '\n'.join(lines)

    text = re.sub(r'<div class="callout"[^>]*>.*?</ul>\s*</div>', convert_callout, text, flags=re.DOTALL)

    # h2 tags
    def convert_h2(m):
        inner = m.group(1)
        inner = re.sub(r'<span class="tag[^"]*">(.*?)</span>', r'[\1] ', inner)
        inner = strip_tags(inner).strip()
        inner = re.sub(r'\s+', ' ', inner)
        return f"\n## {inner}\n"
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', convert_h2, text, flags=re.DOTALL)

    # h3 tags
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', lambda m: f"\n### {strip_tags(m.group(1)).strip()}\n", text, flags=re.DOTALL)

    # article-title
    text = re.sub(r'<div class="article-title">(.*?)</div>', lambda m: f"\n**{strip_tags(m.group(1)).strip()}**\n", text)
    text = re.sub(r'<div class="article-title-cn">(.*?)</div>', lambda m: f"*{strip_tags(m.group(1)).strip()}*\n", text)

    # data-point -> blockquote
    def convert_data_point(m):
        inner = to_md_inline(m.group(1))
        inner = inner.replace('\xa0|\xa0', ' | ').replace('&nbsp;|&nbsp;', ' | ')
        return f"\n> {inner.strip()}\n"
    text = re.sub(r'<div class="data-point">(.*?)</div>', convert_data_point, text, flags=re.DOTALL)

    # implication -> bold label + text
    def convert_implication(m):
        inner = m.group(0)
        label_m = re.search(r'<div class="label">(.*?)</div>', inner)
        label = strip_tags(label_m.group(1)).strip() if label_m else 'Key Insight'
        body = re.sub(r'<div class="label">.*?</div>', '', inner)
        body = to_md_inline(body).strip()
        return f"\n**{label}:** {body}\n"
    text = re.sub(r'<div class="implication">.*?</div>\s*</div>', convert_implication, text, flags=re.DOTALL)

    # list items
    text = re.sub(r'<li>(.*?)</li>', lambda m: f"- {to_md_inline(m.group(1)).strip()}", text, flags=re.DOTALL)

    # paragraphs
    text = re.sub(r'<p[^>]*>(.*?)</p>', lambda m: f"\n{to_md_inline(m.group(1)).strip()}\n", text, flags=re.DOTALL)

    # Convert remaining inline
    text = to_md_inline(text)

    # Remove all remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Clean HTML entities
    text = html_mod.unescape(text)

    # Clean up whitespace
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    # Remove excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    full_text = '\n'.join(result_parts) + text.strip()
    return full_text.strip()


if __name__ == '__main__':
    filename = sys.argv[1]
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    md = extract_markdown(content)
    print(json.dumps({"markdown": md}, ensure_ascii=False))
