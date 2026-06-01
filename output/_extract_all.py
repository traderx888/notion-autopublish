"""Extract markdown from all newsletter HTML files and save as JSON."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _extract_newsletter import extract_markdown

PAGES = [
    (6, "34a3caa8a48781378594dc80abce345b", "newsletter_6_uncategorized.html"),
    (7, "34a3caa8a48781fab10ff7f09cc73265", "newsletter_7_geopolitics.html"),
    (8, "34a3caa8a4878125a590c8ebcaf621ec", "newsletter_8_growth.html"),
    (9, "34a3caa8a48781a0ad54c8166e193c66", "newsletter_9_rates.html"),
    (10, "34a3caa8a4878184bffcf4eda11e12bc", "newsletter_10_trade.html"),
    (11, "34a3caa8a48781ecad0ac78bb6c19430", "newsletter_11_inflation.html"),
    (12, "34a3caa8a4878155b863cdc75275847e", "newsletter_12_china.html"),
    (13, "34a3caa8a48781c68bf1e81f2b1912fe", "newsletter_13_policy.html"),
    (14, "34a3caa8a487819dbde0fa7412df3f56", "newsletter_14_metals.html"),
    (15, "34a3caa8a487816bbc54e82a9ba5cd64", "newsletter_15_oil.html"),
    (16, "34a3caa8a48781308659eb5d63ca4e16", "newsletter_16_japan.html"),
    (17, "34a3caa8a48781d1ae08f7d1282d89c3", "newsletter_17_valuations.html"),
    (18, "34a3caa8a4878166b6ced454e0fff58b", "newsletter_18_volatility.html"),
    (19, "34a3caa8a48781ecba5fd955444c0022", "newsletter_19_credit.html"),
    (20, "34a3caa8a48781daa521c3d72a84ac71", "newsletter_20_china.html"),
    (21, "34a3caa8a487811eb1aef5b9ce8e8852", "newsletter_21_growth.html"),
    (22, "34a3caa8a487811f95eaf3fb06f996d6", "newsletter_22_japan_inflation.html"),
    (23, "34a3caa8a48781dfacb9ca1c2b7720cc", "newsletter_23_oil_geopolitics.html"),
    (24, "34a3caa8a4878129af5debc353eb072d", "newsletter_24_oil.html"),
    (25, "34a3caa8a4878191b7ccf0b96f8f5909", "newsletter_25_credit.html"),
    (26, "34a3caa8a4878143ad48ce78a4edbfd1", "newsletter_26_uncategorized.html"),
    (27, "34a3caa8a487818aa9edd047dd86a96b", "newsletter_27_geopolitics.html"),
    (28, "34a3caa8a48781ba8c3eca03f888ad95", "newsletter_28_china.html"),
    (29, "34a3caa8a4878159ba67e9eb45ef2384", "newsletter_29_growth_trade.html"),
    (30, "34a3caa8a48781c282ececef95bc1487", "newsletter_30_rates_japan.html"),
    (31, "34a3caa8a48781239e08fb1dc4358346", "newsletter_31_growth.html"),
    (32, "34a3caa8a48781c39dccd6e720862752", "newsletter_32_volatility.html"),
    (33, "34a3caa8a48781e89ae4f32613e4c3bf", "newsletter_33_geopolitics.html"),
    (34, "34a3caa8a48781598f23f58bc6d1af0e", "newsletter_34_oil.html"),
    (35, "34a3caa8a48781919b39cd1cdb5ddb14", "newsletter_35_trade_china.html"),
    (36, "34a3caa8a48781f0bb49d62f33743b31", "newsletter_36_geopolitics.html"),
    (37, "34a3caa8a487812980c0e76a13ab8cab", "newsletter_37_china.html"),
    (38, "34a3caa8a4878165a503cb6fb2f98801", "newsletter_38_inflation.html"),
    (39, "34a3caa8a487815f9164d38674a47649", "newsletter_39_oil.html"),
    (40, "34a3caa8a487818580b3ec9d2cc9e928", "newsletter_40_space.html"),
    (41, "34a3caa8a48781d38e13e9900a694c3a", "newsletter_41_semiconductor.html"),
    (42, "34a3caa8a48781f5a842d13e39128996", "newsletter_42_trade.html"),
    (43, "34a3caa8a4878190be68f0fcb926d5ec", "newsletter_43_volatility.html"),
    (44, "34a3caa8a4878194aae5f605c7f850c1", "newsletter_44_japan_rates.html"),
    (46, "34a3caa8a48781bda5f0cb90009916a9", "newsletter_46_china.html"),
    (47, "34a3caa8a48781aca9f4cb10ef60532b", "newsletter_47_policy.html"),
    (48, "34a3caa8a48781fba97ecefcc679c542", "newsletter_48_oil.html"),
    (50, "34a3caa8a48781ff8969f7bdfb9bbcae", "newsletter_50_growth.html"),
    (51, "34a3caa8a48781c8bf3ef5215c352ec2", "newsletter_51_inflation.html"),
    (52, "34a3caa8a48781d3bf0bdae0beb43573", "newsletter_52_valuations.html"),
    (53, "34a3caa8a48781a19248d70b8a2053ce", "newsletter_53_geopolitics.html"),
    (54, "34a3caa8a48781b1b025d0c521cda11e", "newsletter_54_geopolitics.html"),
]

output_dir = os.path.dirname(__file__)
results = {}

for num, page_id, filename in PAGES:
    filepath = os.path.join(output_dir, filename)
    if not os.path.exists(filepath):
        print(f"MISSING: {filename}", file=sys.stderr)
        continue
    with open(filepath, 'r', encoding='utf-8') as f:
        html_content = f.read()
    md = extract_markdown(html_content)
    results[str(num)] = {"page_id": page_id, "markdown": md, "filename": filename}
    print(f"OK: #{num} ({filename}) -> {len(md)} chars", file=sys.stderr)

out_path = os.path.join(output_dir, '_extracted_content.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\nExtracted {len(results)} newsletters to {out_path}", file=sys.stderr)
