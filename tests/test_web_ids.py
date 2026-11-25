import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_html_ids_are_unique():
    text = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    ids = re.findall(r'id="([^"]+)"', text)
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    assert not duplicates, f"duplicate HTML ids: {duplicates}"


def test_single_defense_select_and_result_are_separate():
    text = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert text.count('id="single-defense"') == 1
    assert 'id="single-defense-result"' in text
