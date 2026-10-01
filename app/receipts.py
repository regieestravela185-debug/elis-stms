"""The two receipts the office issues by hand, generated filled-in.

Both are transcriptions of the property's own BIR-registered forms — the
Acknowledgment Receipt and the Service Invoice — so a printed copy sits
beside a booklet copy and reads the same. The wording, the column headings
and the footer registration lines are copied from the forms themselves and
should not be reworded: they are what the forms say.

What this does NOT do is invent a serial number. The red number on each
form belongs to a BIR-accredited printed booklet, and a system that made
its own up would be putting a number on a document that claims to be that
booklet's. The administrator copies the number off the physical form, and
the generated PDF carries that same one.
"""
from io import BytesIO
import re

from .ai_utils import amount_to_words

# The forms' own registration details, printed on every copy.
BUSINESS_NAME = "THE ELIS BUSINESS CENTER"
BUSINESS_TAGLINE = "COMMERCIAL AND RESIDENCES"
BUSINESS_ADDRESS = "#2 Milagrosa, Calamba City, Laguna"
INVOICE_NAME = "ELIS BUSINESS CENTER"
INVOICE_ADDRESS = "#2 Milagrosa, (Tulo) 4027 City of Calamba Laguna Philippines"
PROPRIETOR = "Eugenia H. Liquido - Prop."
INVOICE_TIN = "VAT Reg. TIN: 112-397-305-00002"
FOOTER_ADDRESS = "Purok 1 Brgy. Sucol Calamba City Laguna"
FOOTER_TEL = "Tel. No. 502-0459"
FOOTER_TIN = "VAT REG TIN: 418-224-342-00000"
ATP_NO = "BIR ATP No. 056AU2026000003221"
ATP_ISSUED = "Date Issued: February 27, 2026"
ACCREDITATION_NO = "Accreditation No.: 056MP2022000000001"
ACCREDITATION_DATE = "Accreditation Date: 10-17-2022"
PRINTER = "PROTOTYPE PRINTING AND ENTERPRISE"
BOOKLET_NOTE = "25 Bklts (50x2) 0501-17750"
AR_NOTE = "Pls submit tenants’ government issued IDs"
NOTHING_FOLLOWS = "- nothing follows -"

VAT_RATE = 0.12

# The booklets' own colours. The forms are printed in a single navy — the
# border, the ruling and the letterhead all sit in it — with the serial
# number alone in red. This is deliberately NOT the website's gold: the
# gold mark in static/img belongs to the site, and a receipt that does not
# look like the booklet it claims to copy is the wrong document.
NAVY = (0.106, 0.157, 0.400)
INK = (0.078, 0.078, 0.090)
RULE = NAVY
SERIAL_RED = (0.78, 0.07, 0.09)

_TENS = ("Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")


def amount_to_receipt_words(amount) -> str:
    """"Five Thousand Five Hundred Thirty-eight Pesos and 77/100".

    The receipts write centavos as a fraction rather than in words, and
    hyphenate a compound ten, which is how the forms in the booklet read.
    amount_to_words spells the centavos out and leaves the pair open, so it
    is reshaped here rather than changed — the lease contracts depend on it
    as it stands.
    """
    amount = float(amount or 0)
    pesos = int(amount)
    centavos = int(round((amount - pesos) * 100))
    if centavos == 100:            # 5538.999 must not become "and 100/100"
        pesos, centavos = pesos + 1, 0

    words = amount_to_words(pesos)
    words = words.split(" Pesos")[0] if " Pesos" in words else words
    words = re.sub(rf"\b({'|'.join(_TENS)}) (\w+)",
                   lambda m: f"{m.group(1)}-{m.group(2).lower()}", words)
    return f"{words} Pesos and {centavos:02d}/100"


def vat_breakdown(total, rate: float = VAT_RATE) -> dict:
    """Split a VAT-inclusive total the way the Service Invoice prints it.

    The figure handed over is what the tenant pays, VAT included, so the net
    is the total divided by 1 + rate rather than the total times the rate —
    the second is the commonest way to get this wrong and overstates VAT by
    the rate squared. Rounding the net and subtracting it back gives a VAT
    that always adds up to the printed total.
    """
    total = round(float(total or 0), 2)
    net = round(total / (1 + rate), 2)
    return {"total": total, "net": net, "vat": round(total - net, 2), "rate": rate}


def _brand_mark(c, x, y, h, color=NAVY):
    """The stepped skyline from the booklet's letterhead, drawn.

    The only mark that ships with this repository is the website's gold one,
    which is not what is printed on these forms. Drawing it keeps the receipt
    looking like the booklet and avoids an image that may not be there.
    """
    unit = h / 10.0
    # (left, width, height) in units — a low block, two tall towers, a tail.
    towers = ((0.0, 1.9, 4.6), (2.1, 2.4, 9.2), (4.7, 2.3, 7.0), (7.2, 2.4, 5.2))
    c.saveState()
    for left, w, th in towers:
        bx, bw, bh = x + left * unit, w * unit, th * unit
        c.setFillColorRGB(*color)
        c.rect(bx, y, bw, bh, stroke=0, fill=1)
        # The window texture: thin gaps cut back out in white.
        c.setFillColorRGB(1, 1, 1)
        step = bw / 4.2
        gx = bx + step * 0.75
        while gx < bx + bw - step * 0.35:
            c.rect(gx, y + unit * 0.35, step * 0.26, bh - unit * 0.7, stroke=0, fill=1)
            gx += step
    c.restoreState()


def _wordmark(c, x, y, *, the_line, big, rest_lines, color=NAVY, scale=1.0):
    """"THE / ELIS / BUSINESS CENTER" set the way the booklet sets it.

    ELIS is the whole lockup — several times the size of the words around it
    — so it is drawn as its own run rather than as part of a sentence.
    Returns the width taken, so a caller can place the serial clear of it.
    """
    big_size = 25 * scale
    small_size = 7.2 * scale
    rest_size = 10.5 * scale

    c.setFillColorRGB(*color)
    if the_line:
        c.setFont("Helvetica-Bold", small_size)
        c.drawString(x, y + big_size * 0.78, the_line)
    c.setFont("Helvetica-Bold", big_size)
    c.drawString(x, y, big)
    bw = c.stringWidth(big, "Helvetica-Bold", big_size)

    rx = x + bw + 5 * scale
    ry = y + big_size * 0.58
    for i, line in enumerate(rest_lines):
        size = rest_size if i == 0 else rest_size * 0.63
        c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", size)
        c.drawString(rx, ry, line)
        ry -= size * 1.30
        if i == 0:
            rx += 0  # the tagline sits flush under BUSINESS CENTER
    widest = max([c.stringWidth(l, "Helvetica", rest_size) for l in rest_lines] or [0])
    return bw + 5 * scale + widest


def _peso(c, x, y, font, size):
    """Draw ₱ at the baseline and return its width.

    reportlab's built-in fonts have no peso glyph — it comes out as a broken
    box — and no font file ships with this repository to embed instead, so
    the sign is drawn: a capital P with the two bars across its stem.
    """
    c.setFont(font, size)
    c.drawString(x, y, "P")
    w = c.stringWidth("P", font, size)
    c.saveState()
    c.setLineWidth(max(0.35, size * 0.06))
    for frac in (0.30, 0.50):
        yy = y + size * frac
        c.line(x - size * 0.07, yy, x + w * 0.60, yy)
    c.restoreState()
    return w


def _money(c, x, y, value, font="Helvetica", size=9, align="left"):
    """Draw "₱1,234.56". With align="right", x is the right edge."""
    if value is None:
        return 0
    num = f"{float(value):,.2f}"
    pw = c.stringWidth("P", font, size)
    width = pw + 1.5 + c.stringWidth(num, font, size)
    if align == "right":
        x -= width
    _peso(c, x, y, font, size)
    c.setFont(font, size)
    c.drawString(x + pw + 1.5, y, num)
    return width


def _wrap(c, text, font, size, max_width):
    """Greedy wrap, because these are fixed-width ruled boxes."""
    words, lines, line = (text or "").split(), [], ""
    for w in words:
        trial = f"{line} {w}".strip()
        if c.stringWidth(trial, font, size) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines or [""]


def _letterhead(c, W, H, *, title, wordmark, tagline, address_lines, serial,
                serial_label="No.", date_text="", scale=1.0):
    """The booklet's masthead: drawn mark, ELIS lockup, address, serial, date.

    `wordmark` is (small line above, the large word, the words beside it) —
    the Acknowledgment Receipt reads "THE ELIS BUSINESS CENTER" and the
    Service Invoice drops the "THE", which is the only difference between
    the two forms' heads.
    """
    from reportlab.lib.units import inch
    m = 0.32 * inch
    mark_h = 0.46 * inch * scale
    top = H - m - 0.16 * inch - mark_h

    _brand_mark(c, m, top, mark_h)
    # Clear of the mark: the small "THE" rides above the big word and would
    # otherwise sit on the skyline's last tower.
    text_x = m + mark_h * 1.30

    _wordmark(c, text_x, top + mark_h * 0.12,
              the_line=wordmark[0], big=wordmark[1],
              rest_lines=[wordmark[2]] + ([tagline] if tagline else []),
              scale=scale)

    c.setFillColorRGB(*INK)
    c.setFont("Helvetica", 7.2 * scale)
    yy = top - 0.10 * inch
    for line in address_lines:
        c.drawString(text_x, yy, line)
        yy -= 0.112 * inch

    if serial:
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(*INK)
        label_w = c.stringWidth(serial_label + " ", "Helvetica", 9)
        serial_w = c.stringWidth(str(serial), "Helvetica-Bold", 13)
        sx = W - m - serial_w
        c.drawString(sx - label_w, top + mark_h * 0.62, serial_label)
        c.setFillColorRGB(*SERIAL_RED)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(sx, top + mark_h * 0.62, str(serial))
        c.setFillColorRGB(*INK)

    # Under the serial, never beside it — on one line the two ran together.
    if date_text:
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(*INK)
        c.drawRightString(W - m, top + mark_h * 0.62 - 0.17 * inch, date_text)

    bottom = min(yy + 0.112 * inch, top) - 0.06 * inch
    if title:
        c.setFillColorRGB(*NAVY)
        c.setFont("Helvetica-Bold", 11.5)
        c.drawString(text_x, bottom - 0.16 * inch, title)
        c.setFillColorRGB(*INK)
        bottom -= 0.16 * inch
    return bottom - 0.22 * inch


def _footer(c, W, lines, *, bottom):
    from reportlab.lib.units import inch
    c.setFont("Helvetica", 5.9)
    c.setFillColorRGB(0.42, 0.42, 0.45)
    y = bottom
    for line in lines:
        c.drawCentredString(W / 2, y, line)
        y -= 0.095 * inch
    c.setFillColorRGB(*INK)


def generate_acknowledgment_receipt_pdf(data: dict) -> BytesIO:
    """The Acknowledgment Receipt, laid out as the booklet form is.

    `columns` is the three-column grid the form carries — what the money was
    received for. The headings vary with the payment (RENT, SECURITY
    DEPOSIT, POWER, WATER), so they come from the caller rather than being
    fixed here.
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch

    # The page is sized to its contents. A fixed height left a third of the
    # sheet blank under a receipt with one line in its grid, which reads as a
    # document that failed to finish rather than a short one.
    cols = data.get("columns") or []
    grid_rows = max(2, max((len(col.get("lines") or []) for col in cols), default=2))
    W = 8.5 * inch
    H = 3.62 * inch + grid_rows * 0.20 * inch

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    m = 0.32 * inch

    # The form's own border.
    c.setStrokeColorRGB(*RULE)
    c.setLineWidth(1.1)
    c.rect(m * 0.6, m * 0.6, W - 1.2 * m, H - 1.2 * m)

    y = _letterhead(
        c, W, H, title="ACKNOWLEDGMENT RECEIPT",
        wordmark=("THE", "ELIS", "BUSINESS CENTER"), tagline=BUSINESS_TAGLINE,
        address_lines=[BUSINESS_ADDRESS], serial=data.get("serial_no"),
        date_text=data.get("date_text") or "",
    )

    # The sentence, wrapped inside the ruled area.
    body = (f"Received from Unit # {data.get('unit_label','')} "
            f"({data.get('payer_name','')}), the amount of "
            f"{data.get('amount_words','')} ")
    tail = f"only, in payment for the following:"
    avail = W - 2 * m

    c.setFont("Helvetica", 9.3)
    lines = _wrap(c, body, "Helvetica", 9.3, avail - 1.2 * inch)
    for i, line in enumerate(lines[:-1]):
        c.drawString(m, y, line)
        y -= 0.165 * inch
    # The amount in figures sits inline after the words, with the peso drawn.
    last = lines[-1]
    c.drawString(m, y, last)
    x = m + c.stringWidth(last + " ", "Helvetica", 9.3)
    c.drawString(x, y, "(")
    # The drawn peso's bars reach slightly left of its stem, so it needs a
    # hair of clearance or they touch the bracket.
    x += c.stringWidth("(", "Helvetica", 9.3) + 1.2
    x += _money(c, x, y, data.get("amount"), "Helvetica", 9.3)
    c.drawString(x, y, ") " + tail)
    y -= 0.28 * inch

    # The three-column grid.
    n = max(1, len(cols))
    cw = (W - 2 * m) / n
    rows = grid_rows
    head_h = 0.22 * inch
    row_h = 0.20 * inch
    grid_h = head_h + rows * row_h
    top = y

    c.setStrokeColorRGB(*RULE)
    c.setLineWidth(0.8)
    c.rect(m, top - grid_h, W - 2 * m, grid_h)
    c.line(m, top - head_h, W - m, top - head_h)
    for i in range(1, n):
        c.line(m + i * cw, top - grid_h, m + i * cw, top)

    for i, col in enumerate(cols):
        cx = m + i * cw
        c.setFillColorRGB(*NAVY)
        c.setFont("Helvetica-Bold", 8.2)
        c.drawCentredString(cx + cw / 2, top - head_h + 0.07 * inch,
                            (col.get("heading") or "").upper())
        c.setFillColorRGB(*INK)
        c.setFont("Helvetica", 8.2)
        yy = top - head_h - 0.14 * inch
        for line in (col.get("lines") or []):
            for part in _wrap(c, line, "Helvetica", 8.2, cw - 0.16 * inch):
                c.drawCentredString(cx + cw / 2, yy, part)
                yy -= 0.155 * inch
    y = top - grid_h - 0.26 * inch

    c.setFont("Helvetica-Bold", 8.4)
    c.drawString(m, y, "Note:")
    c.setFont("Helvetica", 8.4)
    c.drawString(m + 0.10 * inch, y - 0.16 * inch, AR_NOTE)

    sig_x = W - m - 2.3 * inch
    c.setLineWidth(0.7)
    c.line(sig_x, y - 0.10 * inch, W - m, y - 0.10 * inch)
    c.setFont("Helvetica", 7.6)
    c.drawCentredString(sig_x + 1.15 * inch, y - 0.24 * inch, "Authorized Signature")

    _footer(c, W, [
        f"{FOOTER_ADDRESS}  •  {FOOTER_TEL}  •  {FOOTER_TIN}",
        f"{ATP_NO}  •  {ATP_ISSUED}  •  {ACCREDITATION_DATE}  •  {PRINTER}",
    ], bottom=m * 0.6 + 0.20 * inch)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def generate_service_invoice_pdf(data: dict) -> BytesIO:
    """The Service Invoice, with the VAT box the form carries."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch

    items = data.get("items") or []
    body_rows = max(6, len(items))
    W = 8.5 * inch
    # Below the item grid sit the VAT boxes, the received line, two signature
    # blocks and the registration footer; 4.97in is what they need clear.
    H = 5.12 * inch + body_rows * 0.21 * inch

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    m = 0.32 * inch

    c.setStrokeColorRGB(*RULE)
    c.setLineWidth(1.1)
    c.rect(m * 0.6, m * 0.6, W - 1.2 * m, H - 1.2 * m)

    y = _letterhead(
        c, W, H, title=None,
        wordmark=("", "ELIS", "BUSINESS CENTER"), tagline="",
        address_lines=[INVOICE_ADDRESS, PROPRIETOR, INVOICE_TIN],
        serial=data.get("serial_no"),
    )

    c.setFillColorRGB(*INK)
    c.setFillColorRGB(*NAVY)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(m, y + 0.10 * inch, "Service Invoice")
    c.setFillColorRGB(*INK)

    # Sale type, ticked by the caller.
    bx = m + 1.55 * inch
    c.setLineWidth(0.7)
    for label, key in (("CASH SALES", "cash"), ("CHARGE SALES", "charge")):
        c.rect(bx, y + 0.09 * inch, 0.10 * inch, 0.10 * inch)
        if (data.get("sale_type") or "cash") == key:
            c.setFont("Helvetica-Bold", 8)
            c.drawString(bx + 0.016 * inch, y + 0.108 * inch, "X")
        c.setFont("Helvetica", 7.6)
        c.drawString(bx + 0.15 * inch, y + 0.11 * inch, label)
        bx += c.stringWidth(label, "Helvetica", 7.6) + 0.45 * inch

    c.setFont("Helvetica", 8.4)
    c.drawRightString(W - m, y + 0.11 * inch, f"Date: {data.get('date_text','')}")
    y -= 0.18 * inch

    # Sold to.
    c.setFont("Helvetica-Bold", 8)
    c.drawString(m, y, "SOLD TO")
    y -= 0.16 * inch
    c.setFont("Helvetica", 8)
    for label, value, width in (
        ("Registered Name:", data.get("sold_to_name", ""), 4.4),
        ("Business Address:", data.get("sold_to_address", ""), 4.4),
    ):
        c.drawString(m, y, label)
        vx = m + c.stringWidth(label + " ", "Helvetica", 8)
        c.drawString(vx, y, value or "")
        c.setLineWidth(0.5)
        c.line(vx, y - 0.035 * inch, m + width * inch, y - 0.035 * inch)
        if label.startswith("Registered"):
            c.drawString(m + 4.7 * inch, y, "TIN:")
            tx = m + 4.7 * inch + c.stringWidth("TIN: ", "Helvetica", 8)
            c.drawString(tx, y, data.get("sold_to_tin", "") or "")
            c.line(tx, y - 0.035 * inch, W - m, y - 0.035 * inch)
        y -= 0.20 * inch

    # Item grid.
    y -= 0.04 * inch
    heads = [("Item Description/Nature of Service", 3.9), ("QTY.", 0.7),
             ("Unit Cost/Price", 1.4), ("Amount", 1.36)]
    total_w = W - 2 * m
    widths = [h[1] * inch for h in heads]
    widths[0] = total_w - sum(widths[1:])
    head_h, row_h = 0.22 * inch, 0.21 * inch
    grid_h = head_h + body_rows * row_h
    top = y

    c.setStrokeColorRGB(*RULE)
    c.setLineWidth(0.8)
    c.rect(m, top - grid_h, total_w, grid_h)
    c.line(m, top - head_h, W - m, top - head_h)
    x = m
    for w in widths[:-1]:
        x += w
        c.line(x, top - grid_h, x, top)
    for r in range(1, body_rows):
        c.setLineWidth(0.3)
        c.line(m, top - head_h - r * row_h, W - m, top - head_h - r * row_h)

    c.setFillColorRGB(*NAVY)
    c.setFont("Helvetica-Bold", 7.6)
    x = m
    for (label, _), w in zip(heads, widths):
        c.drawCentredString(x + w / 2, top - head_h + 0.075 * inch, label)
        x += w
    c.setFillColorRGB(*INK)

    for i, item in enumerate(items[:body_rows]):
        ry = top - head_h - (i + 1) * row_h + 0.065 * inch
        c.setFont("Helvetica", 8)
        for part in _wrap(c, item.get("description", ""), "Helvetica", 8,
                          widths[0] - 0.12 * inch)[:1]:
            c.drawString(m + 0.06 * inch, ry, part)
        if item.get("qty"):
            c.drawCentredString(m + widths[0] + widths[1] / 2, ry, str(item["qty"]))
        if item.get("unit_price") is not None:
            _money(c, m + widths[0] + widths[1] + widths[2] - 0.08 * inch, ry,
                   item["unit_price"], "Helvetica", 8, align="right")
        if item.get("amount") is not None:
            _money(c, W - m - 0.08 * inch, ry, item["amount"], "Helvetica", 8,
                   align="right")
    y = top - grid_h

    # The two summary boxes the form prints side by side.
    vat = data.get("vat") or vat_breakdown(data.get("total", 0))
    left_w = widths[0] + widths[1]
    box_rows = [
        ("VATables Sales", vat["net"]),
        ("VAT", vat["vat"]),
        ("Zero-Rated Sales", None),
        ("VAT-Exempt Sales", None),
    ]
    right_rows = [
        ("Total Sales (VAT Inclusive)", vat["total"], False),
        ("Less: VAT", vat["vat"], False),
        ("Amount: Net of VAT", vat["net"], False),
        ("Less: Discount (SC/PWD/NAAC/MOV/SP)", None, False),
        ("Add: VAT", vat["vat"], False),
        ("Less: Withholding Tax", None, False),
        ("TOTAL AMOUNT DUE", vat["total"], True),
    ]
    rh = 0.185 * inch
    box_h = max(len(box_rows), len(right_rows)) * rh
    c.setLineWidth(0.8)
    c.rect(m, y - box_h, total_w, box_h)
    c.line(m + left_w, y - box_h, m + left_w, y)

    yy = y - rh + 0.055 * inch
    for label, value in box_rows:
        c.setFont("Helvetica", 7.6)
        c.drawString(m + 0.06 * inch, yy, label)
        if value is not None:
            _money(c, m + left_w - 0.08 * inch, yy, value, "Helvetica", 7.6, align="right")
        c.setLineWidth(0.3)
        c.line(m, yy - 0.055 * inch, m + left_w, yy - 0.055 * inch)
        yy -= rh

    yy = y - rh + 0.055 * inch
    for label, value, bold in right_rows:
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 7.6)
        c.drawString(m + left_w + 0.06 * inch, yy, label)
        if value is not None:
            _money(c, W - m - 0.08 * inch, yy, value,
                   "Helvetica-Bold" if bold else "Helvetica", 7.6, align="right")
        c.setLineWidth(0.3)
        c.line(m + left_w, yy - 0.055 * inch, W - m, yy - 0.055 * inch)
        yy -= rh
    y -= box_h + 0.20 * inch

    c.setFont("Helvetica", 8.4)
    c.drawString(m, y, "Received the amount of")
    rx = m + c.stringWidth("Received the amount of  ", "Helvetica", 8.4)
    w = _money(c, rx, y, vat["total"], "Helvetica-Bold", 9.4)
    c.setLineWidth(0.6)
    c.line(rx - 0.04 * inch, y - 0.045 * inch, rx + w + 0.30 * inch, y - 0.045 * inch)

    c.setFont("Helvetica", 7.4)
    c.drawString(W - m - 2.5 * inch, y, "By: ______________________________")
    c.drawRightString(W - m, y - 0.145 * inch, "Cashier / Authorized Representative")
    y -= 0.34 * inch
    c.setFont("Helvetica", 6.8)
    c.drawString(m, y, "SC/PWD/NAAC/MOV/Solo Parent ID No.: ____________________")
    c.drawRightString(W - m, y, "Signature: ______________________________")

    _footer(c, W, [
        f"{BOOKLET_NOTE}  •  {ATP_NO}  •  {ATP_ISSUED}",
        f"{ACCREDITATION_NO}  •  {ACCREDITATION_DATE}  •  {PRINTER}",
    ], bottom=m * 0.6 + 0.20 * inch)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf
