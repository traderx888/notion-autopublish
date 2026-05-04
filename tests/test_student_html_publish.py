import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import student_html_publish as shp


SAMPLE_SOURCE_HTML = """\
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<title>學海無涯 | 測試學生版文章</title>
</head>
<body>
<header class="masthead">
  <div class="masthead-date">2026年5月3日 · 第 38 期 · 測試專刊</div>
</header>
<main>
  <div class="hero-subtitle">這是一篇測試用學生版文章，覆蓋 AI、財報與 FOMC。</div>
</main>
</body>
</html>
"""

SAMPLE_PORTAL_HTML = """\
<!DOCTYPE html>
<html>
<body>
<div class="section-label">課程資料 COURSE MATERIALS</div>
<div class="section-label">研究通訊 NEWSLETTERS</div>
<div class="footer">Footer</div>
</body>
</html>
"""


class StudentHtmlPublishTests(unittest.TestCase):
    def test_inject_student_gate_and_nav_adds_auth_and_portal_link(self) -> None:
        rendered = shp.inject_student_gate_and_nav(SAMPLE_SOURCE_HTML)

        self.assertIn('sessionStorage.getItem("student_auth")', rendered)
        self.assertIn('href="student.html"', rendered)
        self.assertEqual(rendered.count("student-portal-nav-style"), 1)

    def test_upsert_portal_card_is_idempotent(self) -> None:
        card_html = shp.build_portal_card_html(
            filename="sample.html",
            title="測試文章",
            card_date="2026年5月3日",
            description="測試描述",
            tags=[shp.PortalTag("AI", "tag-deep")],
            icon="📘",
            border_color="var(--accent)",
        )

        once = shp.upsert_portal_card(SAMPLE_PORTAL_HTML, card_html, "sample.html")
        twice = shp.upsert_portal_card(once, card_html, "sample.html")

        self.assertEqual(twice.count('href="sample.html"'), 1)
        self.assertLess(twice.index('href="sample.html"'), twice.index("NEWSLETTERS"))

    def test_publish_student_html_writes_output_and_updates_portal(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            output_dir = tmp_root / "output"
            output_dir.mkdir()

            source_path = tmp_root / "source.html"
            source_path.write_text(SAMPLE_SOURCE_HTML, encoding="utf-8")

            student_html = output_dir / "student.html"
            student_html.write_text(SAMPLE_PORTAL_HTML, encoding="utf-8")

            with mock.patch.object(shp, "OUTPUT_DIR", output_dir), mock.patch.object(shp, "STUDENT_HTML", student_html):
                result = shp.publish_student_html(
                    source_path,
                    output_name="published.html",
                    description="測試描述",
                    tag_specs=["AI:tag-deep", "FOMC:tag-rates"],
                )

            published_html = (output_dir / "published.html").read_text(encoding="utf-8")
            updated_portal = student_html.read_text(encoding="utf-8")

            self.assertEqual(result["output_path"], str(output_dir / "published.html"))
            self.assertIn('sessionStorage.getItem("student_auth")', published_html)
            self.assertIn('href="student.html"', published_html)
            self.assertIn('href="published.html"', updated_portal)
            self.assertIn("測試描述", updated_portal)


if __name__ == "__main__":
    unittest.main()
