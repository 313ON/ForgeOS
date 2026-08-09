from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[2] / "app" / "static"
INDEX_PATH = STATIC_DIR / "index.html"

TOPOLOGY_KEYS = (
    "topology.title",
    "topology.help",
    "topology.refresh",
    "topology.refreshed",
    "topology.loading",
    "topology.empty",
    "topology.nodes",
    "topology.links",
    "topology.add_link",
    "topology.cancel",
    "topology.delete",
    "topology.source",
    "topology.target",
    "topology.select_asset",
    "topology.link_type",
    "topology.ethernet",
    "topology.wireless",
    "topology.label",
    "topology.label_placeholder",
    "topology.link_required",
    "topology.self_link",
    "topology.link_added",
    "topology.link_delete_confirm",
    "topology.link_deleted",
    "topology.source_set",
    "topology.source_cleared",
    "topology.click_hint",
    "topology.legend_pass",
    "topology.legend_fail",
    "topology.legend_warning",
    "topology.legend_root",
    "topology.map_aria",
    "topology.asset_missing",
    "topology.table_source",
    "topology.table_target",
    "topology.table_type",
    "topology.table_label",
    "topology.table_actions",
    "topology.no_links",
)


def _load(language: str) -> dict:
    path = STATIC_DIR / "i18n" / f"{language}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _topology_section() -> str:
    html = INDEX_PATH.read_text(encoding="utf-8")
    start = html.index("x-show=\"page === 'monitoring'\"")
    end = html.index("x-show=\"page === 'security'\"")
    return html[start:end]


def test_topology_required_keys_exist_in_both_locales() -> None:
    en = _load("en")
    fa = _load("fa")
    for key in TOPOLOGY_KEYS:
        assert key in en, f"key {key} missing from en.json"
        assert key in fa, f"key {key} missing from fa.json"


def test_topology_visible_strings_are_dictionary_driven() -> None:
    section = _topology_section()
    en = _load("en")
    fa = _load("fa")
    state_references = {"topology.assets", "topology.links"}
    used = {key for key in re.findall(r"topology\.\w+", section) if key not in state_references}
    assert used, "no topology.* keys found in the monitoring section"
    for key in used:
        assert key in en, f"key {key} missing from en.json"
        assert key in fa, f"key {key} missing from fa.json"
    assert re.search(r'placeholder="[A-Z]', section) is None


def test_topology_uses_shared_primitives() -> None:
    section = _topology_section()
    for token in (
        'class="enterprise-panel__header"',
        'class="topology-viewport"',
        'class="topology-node"',
        'class="topology-edge"',
        'class="control"',
        "topologyLayout",
    ):
        assert token in section, f"missing shared primitive token: {token}"


def test_topology_javascript_has_valid_syntax() -> None:
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
