from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

STATIC_DIR = Path(__file__).resolve().parents[2] / "app" / "static"
INDEX_PATH = STATIC_DIR / "index.html"

IMPORT_KEYS = (
    "import.overline",
    "import.title",
    "import.help",
    "import.drop",
    "import.choose",
    "import.txt_limit",
    "import.analyze",
    "import.importing",
    "import.parsing",
    "import.results",
    "import.results_help",
    "profile.recommended",
    "profile.source",
    "common.unknown",
    "common.not_detected",
    "common.choose_txt",
)


def _load(language: str) -> dict:
    path = STATIC_DIR / "i18n" / f"{language}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _import_section() -> str:
    html = INDEX_PATH.read_text(encoding="utf-8")
    start = html.index("x-show=\"page === 'import'\"")
    end = html.index("x-show=\"page === 'reports'\"")
    return html[start:end]


def test_import_required_keys_exist_in_both_locales() -> None:
    en = _load("en")
    fa = _load("fa")
    for key in IMPORT_KEYS:
        assert key in en, f"key {key} missing from en.json"
        assert key in fa, f"key {key} missing from fa.json"


def test_import_visible_strings_are_dictionary_driven() -> None:
    section = _import_section()
    en = _load("en")
    fa = _load("fa")
    used = {key for key in re.findall(r"(?:import|profile|common)\.\w+", section)}
    assert used, "no import.* keys found in the import section"
    for key in used:
        assert key in en, f"key {key} missing from en.json"
        assert key in fa, f"key {key} missing from fa.json"
    assert re.search(r'placeholder="[A-Z]', section) is None


def test_import_dropzone_wiring_and_acceptance() -> None:
    section = _import_section()
    for token in (
        'x-ref="fileInput"',
        'accept=".txt,.log,text/plain"',
        '@change="selectFile($event.target.files[0])"',
        '@dragover.prevent',
        '@drop.prevent="handleDrop($event)"',
        "translated('import.drop', 'Drop your report here')",
        'data-i18n="import.choose"',
        'data-i18n="import.txt_limit"',
        'data-i18n="import.parsing"',
        "translated('import.importing'",
        "translated('import.analyze'",
    ):
        assert token in section, f"missing dropzone wiring token: {token}"
    assert re.search(r"x-text=\"uploading \? '[A-Z]", section) is None


def test_import_js_helpers_use_translations() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")
    assert 'this.translated("common.choose_txt"' in html
    assert 'this.translated("common.not_detected"' in html
    assert "translated('common.unknown', 'Unknown')" in html
    assert 'data-i18n="profile.recommended"' in html
    assert 'data-i18n="profile.source"' in html


def test_import_app_javascript_has_valid_syntax() -> None:
    if not pytest.importorskip("shutil").which("node"):
        return
    html = INDEX_PATH.read_text(encoding="utf-8")
    match = re.search(r"(function forgeApp\(\).*?)</script>", html, re.DOTALL)
    assert match is not None

    result = subprocess.run(
        ["node", "--check", "-"],
        input=match.group(1),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
