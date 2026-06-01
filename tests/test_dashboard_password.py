from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HASH = "f565a575dc72ab8e48978a9915295090118d447d8156f310c7d1655f3aa3720b"
OLD_HASH = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"


def test_dashboard_and_smm_password_gate_use_jarvis88_hash():
    dashboard_html = (REPO_ROOT / "output" / "dashboard.html").read_text(encoding="utf-8")
    smm_html = (REPO_ROOT / "output" / "smm.html").read_text(encoding="utf-8")

    assert f"const PASS_HASH = '{EXPECTED_HASH}'" in dashboard_html
    assert f"const PASS_HASH = '{EXPECTED_HASH}'" in smm_html
    assert OLD_HASH not in dashboard_html
    assert OLD_HASH not in smm_html
