from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

REPORT_DIR = Path(__file__).resolve().parent.parent.parent / "reports"


def generate_pdf(rec: dict) -> str:
    """rec = recommendation dict (see recommendations.rec_to_dict). Returns file path."""
    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / f"recommendation_{rec['id']}.pdf"
    s = getSampleStyleSheet()
    story = [Paragraph("Green Procurement Copilot - Recommendation Report", s["Title"]),
             Paragraph(rec["title"], s["Heading2"]), Paragraph(rec["summary"], s["BodyText"]), Spacer(1, 12)]

    rows = [["Supplier", "Cost impact", "CO2e (kg)", "Lead time", "Confidence"]]
    for o in rec["options"]:
        rows.append([o["supplier"] + (" (current)" if o.get("is_current") else ""),
                     f"{o['cost_impact_pct']:+g}%", f"{o['co2e_kg']:,.0f}",
                     f"{o['lead_time_days']} days", o["confidence"]])
    t = Table(rows, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2e7d32")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
    story += [t, Spacer(1, 12)]

    for heading, key in [("Assumptions", "assumptions"), ("Evidence", "evidence"), ("Missing data", "missing_data")]:
        story.append(Paragraph(heading, s["Heading3"]))
        for item in rec.get(key) or ["None"]:
            story.append(Paragraph(f"- {item}", s["BodyText"]))

    story += [Spacer(1, 12), Paragraph("Approval", s["Heading3"]),
              Paragraph(f"Status: {rec['approval_status']} | By: {rec.get('decided_by')} | "
                        f"At: {rec.get('decided_at')} | Comment: {rec.get('decision_comment') or '-'}", s["BodyText"]),
              Spacer(1, 12),
              Paragraph("<i>Disclaimer: emissions values are estimates, not audited measurements. "
                        "Spend-based estimates are less precise than activity-based data. Supplier claims must be "
                        "verified before being treated as fact. Humans make the final procurement decision.</i>",
                        s["BodyText"])]
    SimpleDocTemplate(str(path), pagesize=A4).build(story)
    return str(path)
