"""Spreadsheet reports the office can actually work in.

The reports used to be CSV. A CSV opens in Excel, which is why it looked
like enough, but it arrives as a wall of text: every peso figure is a
string, so nothing sums; the header scrolls away on the first drag; columns
land at whatever width the file was saved with; and a peso sign or an ñ in a
tenant's name comes out as mojibake unless the reader guesses UTF-8, which
Excel does not. Anyone wanting a total retyped the column.

These are real .xlsx workbooks instead. Amounts are written as numbers with
a peso format, so a selection shows its own sum in the status bar; the
header row is frozen and filterable; columns are sized to their contents;
and the encoding question does not arise.

    sheet = Sheet("Payments", columns=[
        Column("Date", "date"), Column("Tenant"), Column("Amount", "money"),
    ], rows=[[d, name, amount], ...], heading=["THE ELIS CENTER", "Payments"])
    return workbook_response("Elis_Payments", [sheet])
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO

from flask import Response

# The house colours, so a printed report is recognisably the Elis Center's.
GOLD = "D7B35B"
INK = "141417"
PAPER = "FAF8F2"

# Excel has no peso built in, so the symbol is quoted into the format. The
# red negative is what makes a returned deposit read as money going out.
MONEY = '₱#,##0.00;[Red]-₱#,##0.00'
FORMATS = {
    "money": MONEY,
    "int": "#,##0",
    "date": "yyyy-mm-dd",
    "datetime": "yyyy-mm-dd hh:mm",
    "percent": "0.0%",
    "text": "@",
}
# Widths a column of this kind needs before its contents are measured.
FLOORS = {"money": 14, "date": 12, "datetime": 18, "int": 9, "percent": 9}


@dataclass
class Column:
    label: str
    kind: str = "text"
    width: int | None = None
    total: bool = False          # sum this column in a totals row
    wrap: bool = False


@dataclass
class Sheet:
    title: str
    columns: list[Column]
    rows: list[list] = field(default_factory=list)
    heading: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    totals: bool = False
    # Said in the sheet when there are no rows. An empty grid under a header
    # reads as a report that failed rather than one with nothing to report.
    empty: str = "Nothing to report."


def _autosize(ws, sheet, first_col_row):
    from openpyxl.utils import get_column_letter
    for i, col in enumerate(sheet.columns, start=1):
        if col.width:
            ws.column_dimensions[get_column_letter(i)].width = col.width
            continue
        widest = len(col.label)
        for row in sheet.rows:
            if i - 1 >= len(row):
                continue
            value = row[i - 1]
            if value is None:
                continue
            if isinstance(value, (int, float)):
                # A number is rendered by its format, not by repr: 22500.0
                # is six characters on screen as ₱22,500.00, which is ten.
                shown = f"{value:,.2f}"
            elif isinstance(value, (date, datetime)):
                shown = "0000-00-00 00:00"
            else:
                shown = str(value)
            widest = max(widest, *(len(line) for line in shown.split("\n")))
        floor = FLOORS.get(col.kind, 10)
        # Capped: one long note must not push every other column off the page.
        ws.column_dimensions[get_column_letter(i)].width = min(max(widest + 3, floor), 52)


def build_workbook(sheets: list[Sheet]):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)

    thin = Side(style="thin", color="DDD6C4")
    for sheet in sheets:
        # Excel refuses / \ ? * [ ] : in a sheet name and caps it at 31.
        safe = "".join(c for c in sheet.title if c not in "/\\?*[]:")[:31] or "Sheet"
        ws = wb.create_sheet(safe)
        last = get_column_letter(max(1, len(sheet.columns)))
        r = 1

        for n, line in enumerate(sheet.heading):
            ws.cell(row=r, column=1, value=line)
            ws.merge_cells(f"A{r}:{last}{r}")
            cell = ws.cell(row=r, column=1)
            cell.font = Font(bold=True, size=14 if n == 0 else 11,
                             color=INK if n == 0 else "666666")
            cell.alignment = Alignment(horizontal="left", vertical="center")
            ws.row_dimensions[r].height = 22 if n == 0 else 16
            r += 1
        if sheet.heading:
            r += 1

        header_row = r
        for i, col in enumerate(sheet.columns, start=1):
            cell = ws.cell(row=r, column=i, value=col.label)
            cell.font = Font(bold=True, color=INK, size=11)
            cell.fill = PatternFill("solid", fgColor=GOLD)
            cell.alignment = Alignment(horizontal="center", vertical="center",
                                       wrap_text=True)
            cell.border = Border(bottom=thin, top=thin, left=thin, right=thin)
        ws.row_dimensions[r].height = 24
        r += 1

        first_data = r
        if not sheet.rows:
            cell = ws.cell(row=r, column=1, value=sheet.empty)
            cell.font = Font(italic=True, color="888888")
            ws.merge_cells(f"A{r}:{last}{r}")
            r += 1
        for row in sheet.rows:
            for i, col in enumerate(sheet.columns, start=1):
                value = row[i - 1] if i - 1 < len(row) else None
                cell = ws.cell(row=r, column=i, value=value)
                if col.kind in FORMATS:
                    cell.number_format = FORMATS[col.kind]
                if col.kind in ("money", "int", "percent"):
                    cell.alignment = Alignment(horizontal="right")
                elif col.wrap:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                cell.border = Border(bottom=thin)
            if (r - first_data) % 2:
                for i in range(1, len(sheet.columns) + 1):
                    ws.cell(row=r, column=i).fill = PatternFill("solid", fgColor=PAPER)
            r += 1
        last_data = r - 1

        if sheet.totals and sheet.rows:
            ws.cell(row=r, column=1, value="TOTAL")
            for i, col in enumerate(sheet.columns, start=1):
                cell = ws.cell(row=r, column=i)
                cell.font = Font(bold=True)
                cell.border = Border(top=Side(style="double", color=INK))
                if col.total:
                    letter = get_column_letter(i)
                    # A formula, not a precomputed number: filter the sheet or
                    # delete a row and the total follows.
                    cell.value = f"=SUBTOTAL(109,{letter}{first_data}:{letter}{last_data})"
                    cell.number_format = MONEY
                    cell.alignment = Alignment(horizontal="right")
            r += 1

        if sheet.notes:
            r += 1
            for line in sheet.notes:
                ws.cell(row=r, column=1, value=line).font = Font(
                    size=9, color="888888", italic=True)
                ws.merge_cells(f"A{r}:{last}{r}")
                r += 1

        if sheet.rows:
            ws.auto_filter.ref = f"A{header_row}:{last}{last_data}"
        ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
        _autosize(ws, sheet, header_row)
        ws.sheet_view.showGridLines = False
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_title_rows = f"{header_row}:{header_row}"

    return wb


def workbook_response(filename: str, sheets: list[Sheet]) -> Response:
    """An .xlsx download, or a CSV of the first sheet if openpyxl is missing.

    The fallback exists so a report is never a 500: openpyxl is an ordinary
    dependency, but a report is the thing an administrator reaches for when
    something else has already gone wrong, and a plain table beats an error
    page.
    """
    try:
        wb = build_workbook(sheets)
    except ImportError:
        return _csv_fallback(filename, sheets[0] if sheets else None)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    stamp = datetime.now().strftime("%Y%m%d")
    return Response(
        buf.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 f'attachment; filename="{filename}_{stamp}.xlsx"'},
    )


def _csv_fallback(filename: str, sheet: Sheet | None) -> Response:
    import csv
    from io import StringIO
    out = StringIO()
    # The BOM is what tells Excel the file is UTF-8. Without it a peso sign
    # or an ñ in a tenant's name arrives as mojibake.
    out.write("﻿")
    writer = csv.writer(out)
    if sheet:
        for line in sheet.heading:
            writer.writerow([line])
        if sheet.heading:
            writer.writerow([])
        writer.writerow([c.label for c in sheet.columns])
        for row in sheet.rows:
            writer.writerow(["" if v is None else v for v in row])
    return Response(out.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             f'attachment; filename="{filename}.csv"'})
