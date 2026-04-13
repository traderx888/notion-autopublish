from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "output"
STUDENT_HTML = OUTPUT_DIR / "student.html"
VIEWER_HTML = OUTPUT_DIR / "q2_2026_market_intelligence_newsletter.html"
PDF_ASSET = OUTPUT_DIR / "assets" / "q2_2026_market_intelligence_newsletter.pdf"


def test_student_portal_links_to_q2_pdf_viewer():
    html = STUDENT_HTML.read_text(encoding="utf-8")

    assert 'href="q2_2026_market_intelligence_newsletter.html"' in html
    assert "Q2 2026 全球市場深度解析" in html


def test_q2_pdf_viewer_requires_student_auth_and_references_pdf_asset():
    html = VIEWER_HTML.read_text(encoding="utf-8")

    assert 'sessionStorage.getItem("student_auth")' in html
    assert 'assets/q2_2026_market_intelligence_newsletter.pdf' in html


def test_q2_pdf_asset_exists():
    assert PDF_ASSET.exists()
    assert PDF_ASSET.stat().st_size > 0
