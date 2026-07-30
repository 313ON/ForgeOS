from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time
from io import BytesIO
from typing import Any

import xlsxwriter


def build_assets_workbook(rows: Sequence[dict[str, Any]], lang: str = "en") -> BytesIO:
    """Build a styled ForgeOS inventory workbook in memory."""
    is_persian = lang == "fa"
    labels = _labels(lang)
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    workbook.set_properties(
        {
            "title": "ForgeOS Assets Export",
            "subject": "IT asset financial inventory",
            "author": "ForgeOS",
        }
    )
    header_format = workbook.add_format(
        {
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#064E3B",
            "border": 0,
            "align": "left",
            "valign": "vcenter",
        }
    )
    title_format = workbook.add_format(
        {
            "bold": True,
            "font_size": 16,
            "font_color": "#064E3B",
            "bottom": 2,
            "bottom_color": "#10B981",
        }
    )
    label_format = workbook.add_format({"bold": True, "font_color": "#334155"})
    currency_format = workbook.add_format({"num_format": '#,##0.00 "USD/Toman"'})
    date_format = workbook.add_format({"num_format": "yyyy-mm-dd"})
    even_format = workbook.add_format({"bg_color": "#F8FAFC"})
    odd_format = workbook.add_format({"bg_color": "#FFFFFF"})
    even_currency = workbook.add_format({"bg_color": "#F8FAFC", "num_format": '#,##0.00'})
    odd_currency = workbook.add_format({"bg_color": "#FFFFFF", "num_format": '#,##0.00'})
    status_formats = {
        "active": workbook.add_format({"font_color": "#047857", "bg_color": "#D1FAE5"}),
        "maintenance": workbook.add_format({"font_color": "#B45309", "bg_color": "#FEF3C7"}),
        "stock": workbook.add_format({"font_color": "#0369A1", "bg_color": "#E0F2FE"}),
        "retired": workbook.add_format({"font_color": "#64748B", "bg_color": "#E2E8F0"}),
    }
    summary = workbook.add_worksheet("Summary")
    if is_persian:
        summary.right_to_left()
    summary.set_column("A:A", 28)
    summary.set_column("B:B", 24)
    summary.write("A1", labels["title"], title_format)
    summary.write("A3", labels["metric"], header_format)
    summary.write("B3", labels["value"], header_format)
    total_formula = f"=SUM(Assets!F2:F{len(rows) + 1})" if rows else "=0"
    summary_rows = [
        (labels["generated"], date.today().isoformat()),
        (labels["asset_count"], len(rows)),
        (labels["total_valuation"], total_formula),
        (labels["invoices_attached"], sum(bool(row.get("invoice_path")) for row in rows)),
    ]
    for row_number, (label, value) in enumerate(summary_rows, start=3):
        summary.write(row_number, 0, label, label_format)
        if isinstance(value, str) and value.startswith("="):
            summary.write_formula(row_number, 1, value, currency_format)
        else:
            summary.write(row_number, 1, value)

    type_counts = _counts(rows, "type")
    status_counts = _counts(rows, "status")
    summary.write("D3", labels["by_type"], header_format)
    summary.write("E3", labels["count"], header_format)
    for row_number, (label, count) in enumerate(type_counts.items(), start=3):
        summary.write(row_number, 3, label)
        summary.write(row_number, 4, count)
    summary.write("G3", labels["by_status"], header_format)
    summary.write("H3", labels["count"], header_format)
    for row_number, (label, count) in enumerate(status_counts.items(), start=3):
        summary.write(row_number, 6, label)
        summary.write(row_number, 7, count)

    assets_sheet = workbook.add_worksheet("Assets")
    if is_persian:
        assets_sheet.right_to_left()
    columns = [
        (labels["asset_tag"], "asset_tag"),
        (labels["type"], "type"),
        (labels["model"], "model"),
        (labels["serial"], "serial_number"),
        (labels["purchase_date"], "purchase_date"),
        (labels["purchase_price"], "purchase_price"),
        (labels["location"], "location"),
        (labels["status"], "status"),
        (labels["invoice_attached"], "invoice_path"),
    ]
    for column_number, (label, _) in enumerate(columns):
        assets_sheet.write(0, column_number, label, header_format)
    assets_sheet.freeze_panes(1, 0)
    assets_sheet.autofilter(0, 0, len(rows), len(columns) - 1)
    assets_sheet.set_row(0, 24)
    widths = [14, 14, 24, 20, 15, 23, 18, 14, 18]
    for column_number, width in enumerate(widths):
        assets_sheet.set_column(column_number, column_number, width)
    for row_number, row in enumerate(rows, start=1):
        base_format = even_format if row_number % 2 else odd_format
        price_format = even_currency if row_number % 2 else odd_currency
        for column_number, (_, key) in enumerate(columns):
            value = row.get(key)
            if key == "purchase_date" and value:
                assets_sheet.write_datetime(
                    row_number,
                    column_number,
                    datetime.combine(value, time.min) if isinstance(value, date) else value,
                    date_format,
                )
            elif key == "purchase_price" and value is not None:
                assets_sheet.write_number(row_number, column_number, float(value), price_format)
            elif key == "invoice_path":
                assets_sheet.write(row_number, column_number, "Yes" if value else "No", base_format)
            elif key == "status":
                assets_sheet.write(
                    row_number,
                    column_number,
                    value or "",
                    status_formats.get(str(value).casefold(), base_format),
                )
            else:
                assets_sheet.write(row_number, column_number, value or "", base_format)
    if rows:
        assets_sheet.write(len(rows) + 1, 0, labels["total_valuation"], header_format)
        assets_sheet.write_formula(
            len(rows) + 1,
            5,
            f"=SUM(F2:F{len(rows) + 1})",
            currency_format,
        )

    invoices = workbook.add_worksheet("Invoices")
    if is_persian:
        invoices.right_to_left()
    invoice_columns = [labels["asset_tag"], labels["vendor"], labels["invoice_number"], labels["purchase_date"], labels["purchase_price"], labels["invoice_attached"]]
    for column_number, label in enumerate(invoice_columns):
        invoices.write(0, column_number, label, header_format)
    invoices.set_column("A:A", 16)
    invoices.set_column("B:C", 24)
    invoices.set_column("D:D", 16)
    invoices.set_column("E:E", 18)
    invoices.set_column("F:F", 18)
    for row_number, row in enumerate(rows, start=1):
        values = [
            row.get("asset_tag"),
            row.get("vendor_name"),
            row.get("invoice_number"),
            row.get("purchase_date"),
            row.get("purchase_price"),
            "Yes" if row.get("invoice_path") else "No",
        ]
        for column_number, value in enumerate(values):
            if column_number == 3 and value:
                invoices.write_datetime(
                    row_number,
                    column_number,
                    datetime.combine(value, time.min) if isinstance(value, date) else value,
                    date_format,
                )
            elif column_number == 4 and value is not None:
                invoices.write_number(row_number, column_number, float(value), currency_format)
            else:
                invoices.write(row_number, column_number, value or "")
    workbook.close()
    output.seek(0)
    return output


def _counts(rows: Sequence[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "Unspecified")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _labels(lang: str) -> dict[str, str]:
    if lang == "fa":
        return {
            "title": "پرتفوی دارایی ForgeOS", "metric": "شاخص", "value": "مقدار",
            "generated": "تاریخ تولید", "asset_count": "تعداد دارایی", "total_valuation": "ارزش کل",
            "invoices_attached": "فاکتورهای پیوست‌شده", "by_type": "دارایی بر اساس نوع",
            "by_status": "دارایی بر اساس وضعیت", "count": "تعداد", "asset_tag": "برچسب دارایی",
            "type": "نوع", "model": "مدل", "serial": "سریال", "purchase_date": "تاریخ خرید",
            "purchase_price": "قیمت خرید", "location": "مکان", "status": "وضعیت",
            "invoice_attached": "فاکتور پیوست؟", "vendor": "فروشنده", "invoice_number": "شماره فاکتور",
        }
    return {
        "title": "ForgeOS Asset Portfolio", "metric": "Metric", "value": "Value",
        "generated": "Generated", "asset_count": "Asset count", "total_valuation": "Total valuation",
        "invoices_attached": "Invoices attached", "by_type": "Assets by Type",
        "by_status": "Assets by Status", "count": "Count", "asset_tag": "Asset Tag",
        "type": "Type", "model": "Model", "serial": "Serial", "purchase_date": "Purchase Date",
        "purchase_price": "Purchase Price (USD/Toman)", "location": "Location", "status": "Status",
        "invoice_attached": "Invoice Attached?", "vendor": "Vendor", "invoice_number": "Invoice Number",
    }
