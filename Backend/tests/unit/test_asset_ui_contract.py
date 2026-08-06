from __future__ import annotations

import re
import subprocess
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[2] / "app" / "static" / "index.html"


def test_asset_fields_are_not_locked_by_unknown_state() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")

    assert ':disabled="assetUnknown[' not in html
    assert "finally { this.extractBusy = false; }" in html
    assert "finally { this.saving = false; }" in html
    assert "this.manualMode = true;" in html


def test_summary_warning_groups_are_safe_when_arrays_are_missing() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")

    assert "const w = this.summary?.warnings || {};" in html
    assert "Array.isArray(w.expiring_warranties)" in html


def test_asset_component_javascript_has_valid_syntax(tmp_path: Path) -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")
    match = re.search(r"(function forgeApp\(\).*?)</script>", html, re.DOTALL)
    assert match is not None
    script_path = tmp_path / "forge_app.js"
    script_path.write_text(match.group(1), encoding="utf-8")

    result = subprocess.run(
        ["node", "--check", str(script_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_edit_flow_normalizes_ids_and_resets_state() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")

    assert "this.resolveAsset(asset)" in html
    assert '["null", "missing", "undefined", "nan"]' in html
    assert "this.resetAssetForm();" in html
    assert "this.editingAssetId = this.normalizeAssetId(draft.id);" in html
    assert 'method: editing ? "PATCH" : "POST"' in html


def test_import_flow_prefills_asset_form_from_report() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")

    assert "populateAssetDraft(parsed)" in html
    assert "this.populateAssetDraft(result.parsed_fields || {})" in html
    assert "this.assignedPersonId = null;" in html


def test_edit_button_is_explicit_type_and_asset_tag_is_nullable() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")

    assert '<button type="button" @click="editAsset(asset)"' in html
    assert "payload.asset_tag = assetTag || null;" in html
    assert ":required=\"field.required\"" not in html


def test_deep_clone_falls_back_when_structured_clone_fails() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")

    assert "deepClone(value)" in html
    assert "structuredClone(value)" in html
    assert "catch (_error)" in html
    assert "return JSON.parse(JSON.stringify(value));" in html
