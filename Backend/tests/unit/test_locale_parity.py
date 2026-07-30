from pathlib import Path

from Scripts.check_locale_parity import check_locale_pair


def test_backend_locale_key_parity() -> None:
    root = Path(__file__).resolve().parents[2]
    assert check_locale_pair(root / "locales/en.json", root / "locales/fa.json")


def test_static_locale_key_parity() -> None:
    root = Path(__file__).resolve().parents[2]
    static_i18n = root / "app/static/i18n"
    assert check_locale_pair(static_i18n / "en.json", static_i18n / "fa.json")
