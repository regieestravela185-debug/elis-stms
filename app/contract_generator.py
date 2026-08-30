"""Generates a filled-in Lease Contract PDF for commercial tenants, using
the property's own contract template as the source of truth for the
legal boilerplate. Only the tenant/unit-specific facts are parameterized
(names, unit, rent, deposit, lease term, address, etc.) — everything else
is transcribed verbatim from the original template so the generated
document matches what a notary/lawyer already reviewed.

This is a draft for printing and physical signing/notarization — it is
NOT auto-sent to the tenant. Once signed and notarized, admin uploads the
final scanned copy via the existing Documents feature (Lease Agreement).
"""
from io import BytesIO

from .ai_utils import amount_to_words


def _lease_term_phrase(start, end) -> str:
    days = (end - start).days
    years = round(days / 365.25, 2)
    if abs(years - round(years)) < 0.05 and round(years) >= 1:
        whole = round(years)
        word = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five"}.get(whole, str(whole))
        unit = "year" if whole == 1 else "years"
        return f"{word} ({whole}) {unit} commencing on {start.strftime('%B %d, %Y')} and expiring on {end.strftime('%B %d, %Y')}"
    return f"the period commencing on {start.strftime('%B %d, %Y')} and expiring on {end.strftime('%B %d, %Y')}"


def generate_lease_contract_pdf(data: dict) -> BytesIO:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

    lessor_name = data["lessor_name"]
    lessor_business_name = data["lessor_business_name"]
    lessor_address = data["lessor_address"]

    lessee_display = data["lessee_company"] or data["lessee_name"]
    # A company is referred to as "the [Company]" and needs a "represented
    # by [person], [position]" clause; an individual lessee represents
    # themself, so both of those would read oddly ("the Juan Dela Cruz",
    # "represented by Juan Dela Cruz" about himself) and are dropped.
    lessee_display_with_article = f"the {lessee_display}" if data["lessee_company"] else lessee_display
    lessee_rep_clause = (
        f'represented by {data["lessee_name"]}, {data["lessee_position"]},'
        if data["lessee_company"] else
        ""
    )
    lessee_civil_status = data["lessee_civil_status"]
    lessee_nationality = data["lessee_nationality"]
    lessee_address = data["lessee_address"]
    lessee_business_nature = data["lessee_business_nature"] or "general business"

    unit_code = data["unit_code"]
    monthly_rental = float(data["monthly_rental"])
    security_deposit = float(data["security_deposit"])
    lease_start = data["lease_start"]
    lease_end = data["lease_end"]

    # reportlab's base Helvetica font doesn't have the ₱ glyph (renders as a
    # broken-box character) — "Php " reads fine in any font and is a
    # standard way to write peso amounts in PH legal documents anyway.
    monthly_rental_str = f"Php {monthly_rental:,.2f}"
    monthly_rental_words = amount_to_words(monthly_rental)
    security_deposit_str = f"Php {security_deposit:,.2f}"
    security_deposit_words = amount_to_words(security_deposit)
    lease_term_phrase = _lease_term_phrase(lease_start, lease_end)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ContractTitle", parent=styles["Heading1"], fontSize=18,
        alignment=TA_CENTER, spaceAfter=20,
    )
    body_style = ParagraphStyle(
        "ContractBody", parent=styles["Normal"], fontSize=10.5,
        alignment=TA_JUSTIFY, spaceAfter=12, leading=15,
    )
    sig_style = ParagraphStyle(
        "Sig", parent=styles["Normal"], fontSize=10.5, spaceAfter=4,
    )

    elements = [Paragraph("LEASE CONTRACT", title_style)]

    def clause(label, text):
        elements.append(Paragraph(f"<b>{label}:</b> {text}", body_style))

    clause(
        "PARTIES",
        f'This Contract is between {lessor_business_name} (&ldquo;LESSOR&rdquo;), represented by '
        f'{lessor_name}, of legal age, and with postal address at {lessor_address}; and '
        f'{lessee_display_with_article} (&ldquo;LESSEE&rdquo;), {lessee_rep_clause} of legal age, {lessee_civil_status}, '
        f'{lessee_nationality}, with postal address at {lessee_address}.',
    )
    elements.append(Paragraph(
        f'{lessee_display}, the LESSEE, agrees to rent the commercial unit of the ELIS Commercial Center, '
        f'the LESSOR, for office and business use only. The LESSEE engages in {lessee_business_nature}.',
        body_style,
    ))
    clause(
        "COMMERCIAL UNIT",
        f'Unit {unit_code} of the ELIS Business Center at {lessor_address}. The said unit which will be '
        'rented cannot be used for storage of toxic chemicals, flammable materials, ammunitions, illegal '
        'drugs or substances and cannot be used for any activity that is considered illegal and prohibited '
        'by law.',
    )
    clause(
        "CONDITION OF THE PREMISES AND ALTERATIONS",
        'The LESSEE hereby acknowledges to have received the commercial unit including its fixtures in a '
        'clean, safe, and good working condition. The LESSEE must use customary diligence in maintaining '
        'the commercial unit and keeping them in good condition, preventing the units from damages and '
        'sustaining its cleanliness.',
    )
    clause(
        "MONTHLY RENTAL",
        f'{monthly_rental_words} ({monthly_rental_str}), and payable on or before the first (1st) day of '
        'each calendar month. The LESSEE shall issue twelve post dated checks to cover the entire rental '
        'term. The official receipt will be issued monthly, after every check clearing.',
    )
    clause(
        "LEASE TERM",
        f'{lease_term_phrase}. Pre-termination of the lease is prohibited. The Lease Term is extendable and '
        'renewable, subject to the agreed terms and arrangement by both parties.',
    )
    clause("ADVANCE RENTAL", 'Upon the execution of this Contract, the LESSEE agrees to pay in advance, one (1) month rent.')
    clause(
        "SECURITY DEPOSIT",
        f'Upon the execution of this Contract, the LESSEE agrees to pay a security deposit in an amount of '
        f'{security_deposit_words} ({security_deposit_str}), as security for the faithful compliance by the '
        'LESSEE of all terms and conditions of this Contract and for the return of the commercial units in '
        'good and proper condition, and to answer for any and all repairs or damages to the commercial units '
        'and other liabilities of the LESSEE under this contract. This security deposit cannot be applied by '
        'the LESSEE to any unpaid rental(s) or to any other liability of the LESSEE to the LESSOR. The '
        'security deposit shall be refunded to the LESSEE, without any interest thereon, immediately if there '
        'are no damages or repairs to be done on the rented units.',
    )
    clause(
        "PRE-TERMINATION",
        'Pre-termination of the lease is prohibited, except when justified by circumstances beyond '
        "LESSEE&rsquo;s control such as force majeure. In such case, the LESSEE shall not be bound to pay the "
        'rentals for the unexpired or remaining period of this contract.',
    )
    clause(
        "DEDUCTIONS TO SECURITY DEPOSIT AND OTHER CHARGES",
        'The following charges will be deducted from the security deposit, if applicable: unpaid rent; '
        'unpaid utilities, repairs or damages to the units caused by negligence, carelessness, accident, or '
        'abuse, including stickers, scratches, tears, burns, stains, or unapproved holes; replacement cost of '
        "the LESSOR&rsquo;s property that was in or attached to the unit and is missing; utilities for repairs "
        'or cleaning; cost that may be incurred to let in LESSOR&rsquo;s representatives to remove the '
        'telephone or cable TV services or rental items (if LESSEE so request or has moved out); cost that '
        'may be incurred to open the unit when LESSEE or any guest or occupant is missing a key; unreturned '
        'keys; missing or burned-out light bulbs; removing or rekeying unauthorized security devices; '
        'packing, removing, or storing property removed or stored pursuant to this contract; removing '
        'illegally parked vehicles; trash removal; government fees or fines against LESSOR for '
        "LESSEE&rsquo;s violation of laws, decrees or ordinances; late-payment and returned-check charges; or "
        "in any valid eviction proceeding against the LESSEE, plus attorney&rsquo;s fees, court costs, and "
        'filing fees actually paid; charges for replacing all keys if LESSEE fails to return them on or '
        'before actual move-out date.',
    )
    clause(
        "UTILITY SERVICES",
        'All charges for electricity, water, and other utility services to the rented units shall be for the '
        'sole account of the LESSEE. The LESSEE shall promptly pay all utility charges directly to the '
        'utility company concerned. The LESSOR will not be liable for the discontinuance of, or interruptions '
        'in utility services to the LESSEE due to any cause or reason whatsoever.',
    )
    clause(
        "LOSS",
        'The LESSOR is not liable to any resident, guest, or occupant for injury, damage, or loss to person '
        'or property, from any cause including fire, smoke, rain, flood, water leaks, lightning, wind, '
        'explosions, interruption of utilities, pipe leaks, theft, negligent or intentional acts of resident, '
        'occupants, guests, or criminal conduct of other persons including theft, burglary, assault, '
        'vandalism or other crimes.',
    )
    clause(
        "HOUSE RULES",
        'The LESSEE shall faithfully comply with and abide by the House Rules promulgated, updated, or '
        'revised by the LESSOR from time to time. The House Rules shall form an integral part of this '
        'Contract, such that any violation thereof will constitute a breach of this Contract.',
    )
    clause(
        "ABANDONMENT",
        'Abandonment of the commercial unit constitutes a violation of the terms and conditions of this '
        'Contract. The LESSEE is deemed to have ABANDONED the commercial unit when all of the following have '
        "occurred: (1) all occupants appear to have moved out from the commercial unit in LESSOR&rsquo;s "
        'reasonable judgment; (2) office equipments, furniture, and company belongings have been '
        "substantially removed in LESSOR&rsquo;s reasonable judgment; (3) LESSEE has been in default in "
        'payment of rent for thirty (30) days from due date, or water or electric services for the '
        "commercial units have been terminated; and (4) LESSEE has not responded for one (1) week to "
        "LESSOR&rsquo;s notice left on the inside of the main entry door stating that LESSOR considers the "
        'apartment abandoned.',
    )
    clause(
        "ALTERATIONS",
        'Any improvements or alterations in the commercial unit shall be requested by the LESSEE for approval '
        "of the LESSOR. The LESSEE agrees not to alter, damage, or remove the LESSOR&rsquo;s property, "
        'including but not limited to fixtures, wiring, cables, conduits, sockets and other electrical '
        'installations, windows, locks, keys, and security devices without the approval of the LESSOR. Any '
        "improvements to the commercial unit without the LESSOR&rsquo;s consent and approval shall become "
        'property of the LESSOR unless agreed otherwise in writing.',
    )
    clause(
        "MAINTENANCE, REPAIR AND REPLACEMENT",
        'The LESSEE shall well and sufficiently preserve, repair and maintain in good, clean tenable '
        'condition, at its own cost, the interiors of the commercial unit, including the flooring, interior '
        'walls or other finishes, doors, windows, cables, conduits, wirings, sockets, electrical '
        'installations, and plumbing fixtures found in the unit. The LESSEE shall, at its own expense, '
        'replace the light bulbs in the unit with the same type and wattage as well as repair or replace '
        'parts in the toilet tank with the same type and quality as that installed by the LESSOR. The '
        'commercial units and all additions and installations supplied by LESSOR shall be kept in a good, '
        'clean, working condition. The LESSEE shall keep drains, pipes, sanitary or plumbing apparatus in the '
        'unit in good and clean condition. The LESSEE shall pay the LESSOR costs in cleaning, repairing or '
        'replacing any of the same when found to be blocked or stopped. The LESSEE shall take all such steps '
        'and precautions at its own cost to prevent the Leased Premises from becoming infested with termites, '
        'rats, mice, cockroaches or other pests or vermin. Should the LESSEE fail to maintain the Leased '
        'Premises properly such that the same is infested with pests, the LESSOR may employ pest control '
        'services on the Leased Premises and charge the cost thereof to the LESSEE. All minor repairs in the '
        "unit will be at the LESSEE&rsquo;s sole expense. Major repairs not caused by or attributable to the "
        "LESSOR&rsquo;s fault or negligence shall be for the LESSEE&rsquo;s sole account.",
    )
    clause(
        "REMEDIES FOR BREACH",
        'If the LESSEE violates any of the terms or conditions of this Contract, the LESSOR may, in addition '
        'to any other remedies or recourse prescribed by law, pursue any or all of following remedies, '
        'simultaneously or successively, as follows: to terminate this Contract of Lease without the need of '
        'any prior notice, demand or judicial declaration; to immediately repossess the commercial unit '
        'without the necessity or instituting any judicial or court action. In this connection, the LESSEE '
        'hereby names, constitutes, and appoints the LESSOR, its authorized agents, employees, and/or '
        'representatives, as its attorney-in-fact, with full power and authority, to open, break-open, '
        'padlock, enter, occupy, secure, the commercial unit, to clean up, make repairs in, remove property '
        'left in the commercial unit and to take such other steps and employ such other means to enable the '
        'LESSOR to take full and complete physical possession and control of the commercial unit, barring the '
        'LESSEE from entering the commercial unit.',
    )
    clause(
        "RETURN OF THE COMMERCIAL UNIT",
        'Upon the expiration of the Lease Term, or upon the termination of this contract, the LESSEE shall '
        'immediately and peacefully return to the LESSOR the possession of the commercial unit in as good, '
        'clean, sanitary and workable condition as when the LESSEE received it from the LESSOR, reasonable '
        'and ordinary wear and tear excepted, devoid of all occupants, office equipments, furniture, and '
        'office articles, and effects of any kind.',
    )
    clause("SUB-LEASE", 'Sub-letting of the commercial unit or any portion or space therein is prohibited.')
    clause("ASSIGNMENT", 'This Contract or any leasehold rights or interest therein cannot be assigned by the LESSEE.')
    clause(
        "LITIGATION",
        'In the event the LESSOR is compelled to seek judicial relief against the LESSEE in order to enforce '
        'any or all of its rights under this Contract, the LESSEE, in addition to any other damages that may '
        'be awarded by the Court, hereby agrees to pay an amount equivalent to twenty-five (25%) percent of '
        'the amount claimed but in no case less than Php 50,000.00, as and by way of attorney&rsquo;s fees, aside '
        'from the costs of litigation, and other expenses which the law entitles the offended party to '
        'recover from the offending party. The parties hereby agree to submit any action arising from or '
        'incident to this Contract to the jurisdiction of the proper courts of Calamba City only, to the '
        'exclusion of all other venues.',
    )

    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(
        'IN WITNESS WHEREOF, the parties have hereunto set their hands this _____________________ at '
        '_____________________.',
        body_style,
    ))
    elements.append(Spacer(1, 0.4 * inch))
    elements.append(Paragraph(f'<b>{lessor_business_name.upper()}</b><br/>LESSOR', sig_style))
    elements.append(Spacer(1, 0.4 * inch))
    elements.append(Paragraph('Represented by:', sig_style))
    elements.append(Spacer(1, 0.4 * inch))
    elements.append(Paragraph(f'<b>{lessor_name}</b>', sig_style))
    elements.append(Spacer(1, 0.4 * inch))
    elements.append(Paragraph(f'<b>{lessee_display.upper()}</b><br/>LESSEE', sig_style))
    elements.append(Spacer(1, 0.4 * inch))
    elements.append(Paragraph('Represented by:', sig_style))
    elements.append(Spacer(1, 0.4 * inch))
    elements.append(Paragraph(f'<b>{data["lessee_name"]}</b>', sig_style))

    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph('SIGNED IN THE PRESENCE OF:', sig_style))
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph('_________________________&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;_________________________', sig_style))

    elements.append(Spacer(1, 0.4 * inch))
    elements.append(Paragraph(
        '<i>This is a draft generated for printing and physical signing/notarization. It is not a legally '
        'binding document until signed by both parties and notarized.</i>',
        ParagraphStyle("Note", parent=styles["Normal"], fontSize=8.5, textColor=colors.grey, alignment=TA_CENTER),
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
