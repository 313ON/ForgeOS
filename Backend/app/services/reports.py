from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time
from io import BytesIO
from pathlib import Path
from typing import Any

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from forge.runtime.reporting.excel_exporter import build_assets_workbook

from ..domain.models import Asset

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STATIC_FONT_DIR = PROJECT_ROOT / "Backend" / "app" / "static" / "fonts"
FONT_CANDIDATES = (
    STATIC_FONT_DIR / "Vazirmatn.ttf",
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/ubuntu/Ubuntu[wdth,wght].ttf"),
)


def asset_report_rows(db: Session, asset_ids: Sequence[int] | None = None) -> list[dict[str, Any]]:
    """Return normalized asset rows shared by Excel and PDF exporters."""
    query = select(Asset)
    if asset_ids is not None:
        query = query.where(Asset.id.in_(asset_ids))
    assets = db.scalars(query.order_by(Asset.asset_tag, Asset.id)).all()
    return [
        {
            "asset_tag": asset.asset_tag,
            "type": asset.type,
            "asset_name": asset.asset_name,
            "category": asset.category,
            "manufacturer": asset.manufacturer or asset.brand,
            "model": asset.model,
            "ram_mb": asset.ram_mb,
            "cpu_name": asset.cpu_name,
            "gpu_name": asset.gpu_name,
            "serial_number": asset.serial_number,
            "purchase_date": asset.purchase_date,
            "purchase_price": asset.purchase_price,
            "location": asset.location,
            "status": asset.status,
            "invoice_path": asset.invoice_path,
            "vendor_name": asset.vendor_name,
            "invoice_number": asset.invoice_number,
        }
        for asset in assets
    ]


def create_excel_report(rows: Sequence[dict[str, Any]], lang: str = "en") -> BytesIO:
    """Create an RTL-aware styled Excel report."""
    return build_assets_workbook(rows, lang=lang)


def create_pdf_report(rows: Sequence[dict[str, Any]], lang: str = "en") -> BytesIO:
    """Create an executive Dark Enterprise PDF report with Persian-capable fonts."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(auto=True, margin=12)
    font_path = _font_path()
    font_family = "Helvetica"
    if font_path:
        pdf.add_font("ForgeFont", style="", fname=str(font_path))
        pdf.add_font("ForgeFont", style="B", fname=str(font_path))
        font_family = "ForgeFont"
    pdf.add_page()
    if hasattr(pdf, "set_right_to_left"):
        pdf.set_right_to_left(True)
    if hasattr(pdf, "set_text_shaping") and font_path:
        pdf.set_text_shaping(use_shaping_engine=True, direction="rtl", script="arab", language="fas")
    pdf.set_fill_color(11, 15, 25)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")
    is_persian = lang == "fa"
    pdf.set_text_color(226, 232, 240)
    pdf.set_font(font_family, style="B", size=20)
    pdf.cell(0, 12, "گزارش دارایی‌های ForgeOS" if is_persian else "ForgeOS Asset Report", new_x="LMARGIN", new_y="NEXT", align="R" if is_persian else "L")
    pdf.set_font(font_family, size=9)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(
        0,
        7,
        (f"تاریخ تولید: {date.today().isoformat()}  |  تعداد دارایی: {len(rows)}"
         if is_persian else f"Generated: {date.today().isoformat()}  |  Assets: {len(rows)}"),
        new_x="LMARGIN",
        new_y="NEXT",
        align="R" if is_persian else "L",
    )
    pdf.ln(8)

    total_value = sum(float(row["purchase_price"] or 0) for row in rows)
    pdf.set_fill_color(6, 78, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(font_family, style="B", size=11)
    pdf.cell(80, 10, "ارزش کل" if is_persian else "Total value", border=0, fill=True, align="C")
    pdf.cell(80, 10, f"{total_value:,.2f}", border=0, fill=True, align="C")
    pdf.cell(80, 10, "فاکتورهای پیوست‌شده" if is_persian else "Invoices attached", border=0, fill=True, align="C")
    pdf.cell(30, 10, str(sum(bool(row["invoice_path"]) for row in rows)), border=0, fill=True, align="C")
    pdf.ln(18)

    headers = (
        ["فاکتور", "وضعیت", "مکان", "قیمت خرید", "تاریخ خرید", "سریال", "مدل", "نوع", "برچسب"]
        if is_persian
        else ["Invoice", "Status", "Location", "Purchase Price", "Purchase Date", "Serial", "Model", "Type", "Asset Tag"]
    )
    widths = [23, 23, 32, 32, 28, 36, 38, 28, 30]
    pdf.set_font(font_family, style="B", size=8)
    pdf.set_fill_color(6, 78, 59)
    for header, width in zip(headers, widths, strict=True):
        pdf.cell(width, 9, header, border=0, fill=True, align="C")
    pdf.ln()
    pdf.set_font(font_family, size=7.5)
    for index, row in enumerate(rows):
        pdf.set_fill_color(15, 23, 42) if index % 2 == 0 else pdf.set_fill_color(30, 41, 59)
        values = [
            ("دارد" if row["invoice_path"] else "ندارد")
            if is_persian
            else ("Yes" if row["invoice_path"] else "No"),
            str(row["status"] or ""),
            str(row["location"] or ""),
            f'{float(row["purchase_price"]):,.2f}' if row["purchase_price"] is not None else "—",
            _format_date(row["purchase_date"]),
            str(row["serial_number"] or ""),
            str(row["model"] or ""),
            str(row["type"] or ""),
            str(row["asset_tag"] or ""),
        ]
        for value, width in zip(values, widths, strict=True):
            pdf.cell(width, 8, value[:30], border=0, fill=True, align="C")
        pdf.ln()
    raw_output = pdf.output(dest="S")
    output = BytesIO(raw_output.encode("latin-1") if isinstance(raw_output, str) else bytes(raw_output))
    output.seek(0)
    return output


def _font_path() -> Path | None:
    return next((candidate for candidate in FONT_CANDIDATES if candidate.is_file()), None)


def _format_date(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        value = value.date()
    return value.isoformat()
