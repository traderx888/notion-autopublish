import re
import json
import os

def html_to_text(html):
    # Remove script and style blocks
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL|re.IGNORECASE)

    # Convert headers
    html = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\n# \1\n', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n## \1\n', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n### \1\n', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<h4[^>]*>(.*?)</h4>', r'\n#### \1\n', html, flags=re.DOTALL|re.IGNORECASE)

    # Convert list items
    html = re.sub(r'<li[^>]*>(.*?)</li>', r'\n- \1', html, flags=re.DOTALL|re.IGNORECASE)

    # Convert br tags to newlines
    html = re.sub(r'<br\s*/?\s*>', '\n', html, flags=re.IGNORECASE)

    # Convert p tags to double newlines
    html = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\1\n', html, flags=re.DOTALL|re.IGNORECASE)

    # Remove all remaining HTML tags
    html = re.sub(r'<[^>]+>', '', html)

    # Decode HTML entities
    html = html.replace('&amp;', '&')
    html = html.replace('&lt;', '<')
    html = html.replace('&gt;', '>')
    html = html.replace('&quot;', '"')
    html = html.replace('&#39;', "'")
    html = html.replace('&apos;', "'")
    html = html.replace('&rarr;', '->')
    html = html.replace('&larr;', '<-')
    html = html.replace('&mdash;', '--')
    html = html.replace('&ndash;', '-')
    html = html.replace('&bull;', '-')
    html = html.replace('&nbsp;', ' ')
    html = html.replace('&hellip;', '...')
    html = html.replace('&lsquo;', "'")
    html = html.replace('&rsquo;', "'")
    html = html.replace('&ldquo;', '"')
    html = html.replace('&rdquo;', '"')
    html = html.replace('&trade;', '(TM)')
    html = html.replace('&copy;', '(C)')
    html = html.replace('&reg;', '(R)')
    html = html.replace('&deg;', ' degrees')
    html = html.replace('&plusmn;', '+/-')
    html = html.replace('&#8211;', '-')
    html = html.replace('&#8212;', '--')
    html = html.replace('&#8216;', "'")
    html = html.replace('&#8217;', "'")
    html = html.replace('&#8220;', '"')
    html = html.replace('&#8221;', '"')

    # Clean up excessive whitespace
    html = re.sub(r'[ \t]+', ' ', html)
    html = re.sub(r'\n{3,}', '\n\n', html)
    html = html.strip()

    return html

# Newsletter number -> filename mapping
output_dir = r"C:\Users\User\Documents\GitHub\notion-autopublish\output"
mapping = {}
for f in os.listdir(output_dir):
    m = re.match(r'newsletter_(\d+)_(.+)\.html', f)
    if m:
        num = int(m.group(1))
        mapping[num] = f

# The 48 page IDs
page_ids = {
    49: "34a3caa8a48781878910f70686198415",
    53: "34a3caa8a48781a19248d70b8a2053ce",
    47: "34a3caa8a48781aca9f4cb10ef60532b",
    54: "34a3caa8a48781b1b025d0c521cda11e",
    51: "34a3caa8a48781c8bf3ef5215c352ec2",
    52: "34a3caa8a48781d3bf0bdae0beb43573",
    48: "34a3caa8a48781fba97ecefcc679c542",
    50: "34a3caa8a48781ff8969f7bdfb9bbcae",
    31: "34a3caa8a48781239e08fb1dc4358346",
    37: "34a3caa8a487812980c0e76a13ab8cab",
    26: "34a3caa8a4878143ad48ce78a4edbfd1",
    34: "34a3caa8a48781598f23f58bc6d1af0e",
    29: "34a3caa8a4878159ba67e9eb45ef2384",
    39: "34a3caa8a487815f9164d38674a47649",
    38: "34a3caa8a4878165a503cb6fb2f98801",
    40: "34a3caa8a487818580b3ec9d2cc9e928",
    27: "34a3caa8a487818aa9edd047dd86a96b",
    43: "34a3caa8a4878190be68f0fcb926d5ec",
    35: "34a3caa8a48781919b39cd1cdb5ddb14",
    44: "34a3caa8a4878194aae5f605c7f850c1",
    28: "34a3caa8a48781ba8c3eca03f888ad95",
    46: "34a3caa8a48781bda5f0cb90009916a9",
    30: "34a3caa8a48781c282ececef95bc1487",
    32: "34a3caa8a48781c39dccd6e720862752",
    41: "34a3caa8a48781d38e13e9900a694c3a",
    33: "34a3caa8a48781e89ae4f32613e4c3bf",
    36: "34a3caa8a48781f0bb49d62f33743b31",
    42: "34a3caa8a48781f5a842d13e39128996",
    21: "34a3caa8a487811eb1aef5b9ce8e8852",
    22: "34a3caa8a487811f95eaf3fb06f996d6",
    8: "34a3caa8a4878125a590c8ebcaf621ec",
    24: "34a3caa8a4878129af5debc353eb072d",
    16: "34a3caa8a48781308659eb5d63ca4e16",
    6: "34a3caa8a48781378594dc80abce345b",
    12: "34a3caa8a4878155b863cdc75275847e",
    18: "34a3caa8a4878166b6ced454e0fff58b",
    15: "34a3caa8a487816bbc54e82a9ba5cd64",
    10: "34a3caa8a4878184bffcf4eda11e12bc",
    25: "34a3caa8a4878191b7ccf0b96f8f5909",
    14: "34a3caa8a487819dbde0fa7412df3f56",
    9: "34a3caa8a48781a0ad54c8166e193c66",
    13: "34a3caa8a48781c68bf1e81f2b1912fe",
    17: "34a3caa8a48781d1ae08f7d1282d89c3",
    20: "34a3caa8a48781daa521c3d72a84ac71",
    23: "34a3caa8a48781dfacb9ca1c2b7720cc",
    11: "34a3caa8a48781ecad0ac78bb6c19430",
    19: "34a3caa8a48781ecba5fd955444c0022",
    7: "34a3caa8a48781fab10ff7f09cc73265",
}

results = {}
for num, page_id in sorted(page_ids.items()):
    if num in mapping:
        filepath = os.path.join(output_dir, mapping[num])
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_html = f.read()
        text = html_to_text(raw_html)
        # Truncate if needed
        if len(text) > 90000:
            text = text[:90000] + "\n\n[Content truncated]"
        results[str(num)] = {"page_id": page_id, "text": text, "filename": mapping[num]}
    else:
        print(f"MISSING: newsletter #{num}")

# Write each as individual file for easy reading
out_dir = r"C:\Users\User\Documents\GitHub\notion-autopublish\output\_txt"
os.makedirs(out_dir, exist_ok=True)
for num_str, data in results.items():
    with open(os.path.join(out_dir, f"{num_str}.txt"), 'w', encoding='utf-8') as f:
        f.write(data['text'])

# Write mapping
with open(os.path.join(out_dir, "mapping.json"), 'w', encoding='utf-8') as f:
    json.dump({k: {"page_id": v["page_id"], "filename": v["filename"], "chars": len(v["text"])} for k, v in results.items()}, f, indent=2)

print(f"Converted {len(results)} newsletters")
for num_str in sorted(results.keys(), key=int):
    print(f"  #{num_str}: {len(results[num_str]['text'])} chars -> {results[num_str]['page_id']}")
