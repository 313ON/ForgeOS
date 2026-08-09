from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[2] / "app" / "static"
INDEX_PATH = STATIC_DIR / "index.html"

WAREHOUSE_KEYS = (
    "warehouse.overline",
    "warehouse.title",
    "warehouse.subtitle",
    "warehouse.refresh",
    "warehouse.search",
    "warehouse.search_placeholder",
    "warehouse.column_sku_item",
    "warehouse.column_category",
    "warehouse.column_stock",
    "warehouse.column_location",
    "warehouse.column_condition",
    "warehouse.loading",
    "warehouse.low_stock",
    "warehouse.empty",
    "warehouse.empty_help",
    "warehouse.filtered_empty",
    "warehouse.filtered_empty_help",
    "warehouse.refreshed",
    "warehouse.add_item",
    "warehouse.edit",
    "warehouse.movement",
    "warehouse.new_title",
    "warehouse.new_help",
    "warehouse.edit_title",
    "warehouse.edit_help",
    "warehouse.field_sku",
    "warehouse.field_name",
    "warehouse.field_category",
    "warehouse.field_unit",
    "warehouse.field_minimum_stock",
    "warehouse.field_storage_location",
    "warehouse.field_bin_code",
    "warehouse.field_condition",
    "warehouse.field_vendor",
    "warehouse.field_serial",
    "warehouse.field_batch",
    "warehouse.field_notes",
    "warehouse.saving",
    "warehouse.save",
    "warehouse.item_added",
    "warehouse.item_updated",
    "warehouse.movement_title",
    "warehouse.movement_type",
    "warehouse.movement_quantity",
    "warehouse.movement_reference",
    "warehouse.movement_notes",
    "warehouse.movement_submit",
    "warehouse.movement_recorded",
    "common.actions",
)

REFERENCE_KEYS = (
    "references.overline",
    "references.title",
    "references.subtitle",
    "references.refresh",
    "references.search",
    "references.search_placeholder",
    "references.preview",
    "references.download",
    "references.no_description",
    "references.loading",
    "references.empty",
    "references.empty_help",
    "references.filtered_empty",
    "references.filtered_empty_help",
    "references.refreshed",
    "references.upload",
    "references.upload_title",
    "references.upload_help",
    "references.field_title",
    "references.field_category",
    "references.field_tags",
    "references.field_description",
    "references.field_file",
    "references.uploading",
    "references.uploaded",
)


def _load(language: str) -> dict:
    path = STATIC_DIR / "i18n" / f"{language}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _section(html: str, page: str, next_page: str) -> str:
    start = html.index(f"x-show=\"page === '{page}'\"")
    end = html.index(f"x-show=\"page === '{next_page}'\"")
    return html[start:end]


def _warehouse_section() -> str:
    return _section(INDEX_PATH.read_text(encoding="utf-8"), "warehouse", "references")


def _references_section() -> str:
    return _section(INDEX_PATH.read_text(encoding="utf-8"), "references", "people")


def test_warehouse_required_keys_exist_in_both_locales() -> None:
    en = _load("en")
    fa = _load("fa")
    for key in WAREHOUSE_KEYS:
        assert key in en, f"key {key} missing from en.json"
        assert key in fa, f"key {key} missing from fa.json"


def test_references_required_keys_exist_in_both_locales() -> None:
    en = _load("en")
    fa = _load("fa")
    for key in REFERENCE_KEYS:
        assert key in en, f"key {key} missing from en.json"
        assert key in fa, f"key {key} missing from fa.json"


def test_warehouse_visible_strings_are_dictionary_driven() -> None:
    section = _warehouse_section()
    en = _load("en")
    fa = _load("fa")
    used = {key for key in re.findall(r"warehouse\.\w+", section)}
    assert used, "no warehouse.* keys found in the warehouse section"
    for key in used:
        assert key in en, f"key {key} missing from en.json"
        assert key in fa, f"key {key} missing from fa.json"
    assert re.search(r'placeholder="[A-Z]', section) is None


def test_references_visible_strings_are_dictionary_driven() -> None:
    section = _references_section()
    en = _load("en")
    fa = _load("fa")
    used = {key for key in re.findall(r"references\.\w+", section)}
    assert used, "no references.* keys found in the references section"
    for key in used:
        assert key in en, f"key {key} missing from en.json"
        assert key in fa, f"key {key} missing from fa.json"
    assert re.search(r'placeholder="[A-Z]', section) is None


def test_warehouse_uses_shared_primitives() -> None:
    section = _warehouse_section()
    for token in (
        'class="control"',
        'class="table-scroll"',
        'class="empty-state empty-state--loose',
        'class="loading-state',
        'class="technical-value text-xs text-muted" x-text="item.sku"',
        'x-text="stockLabel(item)"',
    ):
        assert token in section, f"missing shared primitive token: {token}"


def test_references_uses_shared_primitives_and_formatters() -> None:
    section = _references_section()
    for token in (
        'class="control"',
        'class="empty-state empty-state--loose',
        'class="loading-state surface',
        'class="technical-value mt-1 truncate text-[10px] text-muted" x-text="document.original_filename"',
        "formatBytes(document.size_bytes)",
        "formatDate(document.created_at)",
        'data-i18n="references.preview"',
        'data-i18n="references.download"',
        "translated('references.no_description'",
    ):
        assert token in section, f"missing shared primitive/formatter token: {token}"


def test_formatters_module_integration_remains_intact() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")
    assert '<script src="/static/js/formatters.js">' in html
    assert "function forgeApp()" in html


def test_warehouse_references_javascript_has_valid_syntax() -> None:
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