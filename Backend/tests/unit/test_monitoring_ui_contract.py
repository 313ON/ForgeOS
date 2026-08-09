from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

STATIC_DIR = Path(__file__).resolve().parents[2] / "app" / "static"
INDEX_PATH = STATIC_DIR / "index.html"
REQUIRED_KEYS = (
    "monitoring.topology_overline",
    "monitoring.topology_title",
    "monitoring.topology_help",
    "monitoring.map_title",
    "monitoring.map_help",
    "monitoring.column_name",
    "monitoring.column_target",
    "monitoring.column_type",
    "monitoring.column_status",
    "monitoring.column_latency",
    "monitoring.column_last_check",
    "monitoring.column_actions",
    "monitoring.summary_online",
    "monitoring.summary_latency",
    "monitoring.summary_issues",
    "monitoring.summary_last_check",
    "monitoring.added",
    "monitoring.updated",
    "monitoring.deleted",
    "monitoring.delete_confirm",
    "common.yesterday",
    "common.days_ago",
)


def _load(language: str) -> dict:
    path = STATIC_DIR / "i18n" / f"{language}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _monitoring_section(html: str) -> str:
    start = html.index("x-show=\"page === 'monitoring'\"")
    end = html.index("x-show=\"page === 'security'\"")
    return html[start:end]


def test_formatters_module_is_loaded_before_app() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")
    app_pos = html.index("function forgeApp()")
    loader_pos = html.index('<script src="/static/js/formatters.js">')
    assert loader_pos < app_pos


def test_monitoring_technical_values_are_rtl_safe() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")
    assert 'class="technical-value truncate text-xs text-slate-300" x-text="target.ip_or_host"' in html
    assert re.search(r'class="technical-value px-5 py-4 text-end[^"]*"', html)


def test_monitoring_visible_strings_are_dictionary_driven() -> None:
    section = _monitoring_section(INDEX_PATH.read_text(encoding="utf-8"))
    en = _load("en")
    fa = _load("fa")
    used = {key for key in re.findall(r"monitoring\.\w+", section)}
    for key in used:
        assert key in en, f"key {key} missing from en.json"
        assert en[key] in fa.values() or key in fa, f"key {key} missing from fa.json"


def test_monitoring_summary_uses_translated_labels() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")
    assert 'this.translated("monitoring.summary_online"' in html
    assert 'this.translated("monitoring.summary_latency"' in html
    assert 'this.translated("monitoring.summary_issues"' in html
    assert 'this.translated("monitoring.summary_last_check"' in html


def test_monitoring_delete_confirm_and_toasts_use_translations() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")
    assert 'this.translated("monitoring.delete_confirm"' in html
    assert 'this.translated("monitoring.added"' in html
    assert 'this.translated("monitoring.updated"' in html
    assert 'this.translated("monitoring.deleted"' in html


def test_required_dictionary_keys_are_present_in_both_languages() -> None:
    en = _load("en")
    fa = _load("fa")
    for key in REQUIRED_KEYS:
        assert key in en, f"key {key} missing from en.json"
        assert key in fa, f"key {key} missing from fa.json"


def test_monitoring_formatters_wired_into_app() -> None:
    section = _monitoring_section(INDEX_PATH.read_text(encoding="utf-8"))
    assert "formatNumber(" in section
    assert 'monitoring.search_placeholder' in section
    assert re.search(r'placeholder="Search targets', section) is None


def test_monitoring_app_javascript_has_valid_syntax() -> None:
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