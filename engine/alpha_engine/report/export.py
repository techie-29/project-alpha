"""PDF and Excel versions of a finished report. Built only from the report JSON, so they always match what the owner saw."""
from __future__ import annotations
import io
from xml.sax.saxutils import escape
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _n(v, unit=""):
    if v is None:
        return "-"
    a = abs(v)
    s = f"{v/1e6:.2f}M" if a >= 1e6 else f"{v/1e3:.1f}K" if a >= 1e4 else f"{v:,.0f}" if a >= 100 else f"{v:.2f}"
    return f"{unit} {s}".strip()


def _kpi_value(k):
    if k["kind"] == "rate":
        return f"{k['value']*100:.1f}%"
    return _n(k["value"], k.get("unit", ""))


def to_pdf(report: dict, owner: dict | None = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="Alpha business report", author="Project Alpha")
    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=ss["Title"], fontSize=19, leading=23, alignment=0, spaceAfter=4)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13, spaceBefore=12, spaceAfter=5, textColor=colors.HexColor("#0b6b4f"))
    B = ParagraphStyle("B", parent=ss["BodyText"], fontSize=9.5, leading=13)
    S = ParagraphStyle("S", parent=B, fontSize=8, textColor=colors.HexColor("#555555"))
    T = ParagraphStyle("T", parent=B, fontName="Helvetica-Bold")
    p = lambda t, st=B: Paragraph(escape(str(t)), st)
    b = report["briefing"]
    el = [p("Business report", H1), p(f"Files: {', '.join(f['name'] for f in report['files'])}", S), p(f"Generated {report['generated_at'][:16].replace('T', ' ')} UTC", S), Spacer(1, 6),
          p(b["headline"], ParagraphStyle("hl", parent=B, fontSize=13, leading=17, fontName="Helvetica-Bold")), p(b["status"]), p(b.get("coverage") or "", S),
          p(f"Checked {b['checked']['series']:,} measure-and-group combinations ({b['checked']['tests']:,} statistical tests).", S)]
    el.append(p("What matters most", H2))
    for s in b["stories"] or []:
        el += [p(f"{s['title']}  [{s['claim']}]", T), p(s["detail"]), p(s["action"], S), Spacer(1, 4)]
    if not b["stories"]:
        el.append(p("Nothing unusual changed. Everything checked stayed within its own normal range."))
    el.append(p("Fix, keep, watch", H2))
    for key, title in (("fix", "Fix"), ("keep", "Keep"), ("watch", "Watch")):
        items = report["intelligence"][key]
        el.append(p(f"{title} ({len(items)})", T))
        for it in items[:8]:
            el += [p(f"- {it['title']}"), p(it["where_to_look"], S)]
    for v in report["your_data"]:
        el += [PageBreak(), p(f"Your data: {v['view']}", H2), p(f"{v['rows_total']:,} rows, {v['from'][:10]} to {v['to'][:10]}, by {v['step']}.", S)]
        rows = [["Measure", "Total", "Recent change", "Vs year before"]]
        for k in v["kpis"]:
            ch = k.get("change_recent")
            rows.append([k["label"], _kpi_value(k), "-" if ch is None else (f"{ch*100:+.1f} pts" if k.get("change_is_points") else f"{ch*100:+.0f}%"),
                         "-" if k.get("change_year") is None else f"{k['change_year']*100:+.0f}%"])
        t = Table(rows, colWidths=[62 * mm, 40 * mm, 35 * mm, 35 * mm])
        t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6f3ee")), ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#bbbbbb")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        el.append(t)
        for bd in v["breakdowns"][:3]:
            el.append(p(f"{bd['measure']} by {bd['column'].replace('_', ' ')}", T))
            tr = [["Group", bd["unit"] or "Amount", "Share"]] + [[r["value"], _n(r["amount"]), f"{r['share']*100:.0f}%"] for r in bd["rows"][:6]]
            tt = Table(tr, colWidths=[70 * mm, 40 * mm, 30 * mm])
            tt.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#cccccc"))]))
            el += [tt, Spacer(1, 4)]
    el += [PageBreak(), p("Findings in detail", H2)]
    for f in report["insights"]["findings"]:
        n = f["numbers"]
        el += [p(f"{f['title']}  [{f['claim']}]", T), p(f["detail"])]
        el.append(p(f"Before {_n(n['before'], n.get('unit') or '')}, during {_n(n['after'], n.get('unit') or '')}. How sure: {f['evidence_strength']}. File: {f['view']}.", S))
        d = f.get("drivers")
        if d and d["by_column"]:
            top = d["by_column"][0]["top"][0]
            el.append(p(f"Lines up with {top['value']} ({d['by_column'][0]['col'].replace('_', ' ')}): {top['share_of_change']*100:.0f}% of the change.", S))
        inv = f.get("investigation")
        if inv and inv.get("summary"):
            el.append(p(f"AI helper note (numbers verified against calculations): {inv['summary']}", S))
        el.append(Spacer(1, 6))
    if not report["insights"]["findings"]:
        el.append(p("No findings: nothing changed beyond normal variation."))
    qs = {a["questionId"]: a["answer"] for a in (owner or {}).get("answers", [])}
    if report.get("questions"):
        el.append(p("Questions for the owner", H2))
        for q in report["questions"]:
            el += [p(q["text"], S), p("Answer: " + qs.get(q["id"], "(not answered)"))]
    el.append(p("How to read this report", H2))
    el += [p(b["what_this_means"], S)] + [p("- " + l, S) for l in report["limits"]] + [p("- " + c, S) for c in b["caveats"]]

    def foot(c, d):
        c.saveState(); c.setFont("Helvetica", 7.5); c.setFillColor(colors.HexColor("#777777"))
        c.drawString(18 * mm, 9 * mm, "Alpha - describes what changed and what it lines up with; it does not prove causes."); c.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {d.page}"); c.restoreState()
    doc.build(el, onFirstPage=foot, onLaterPages=foot)
    return buf.getvalue()


def _sheet(ws, header, rows, widths=None):
    ws.append(header)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="0B6B4F"); c.alignment = Alignment(vertical="top", wrap_text=True)
    for r in rows:
        ws.append(r)
    for i, w in enumerate(widths or [], 1):
        ws.column_dimensions[chr(64 + i)].width = w
    ws.freeze_panes = "A2"


def to_xlsx(report: dict, owner: dict | None = None) -> bytes:
    wb = Workbook(); b = report["briefing"]
    ws = wb.active; ws.title = "Briefing"
    _sheet(ws, ["Item", "Text"], [["Headline", b["headline"]], ["Status", b["status"]], ["Coverage", b.get("coverage") or ""], ["Generated", report["generated_at"]],
                                  *[["Caveat", c] for c in b["caveats"]], *[["Limit", l] for l in report["limits"]]], [16, 110])
    ws = wb.create_sheet("Findings")
    _sheet(ws, ["ID", "File", "Level", "Claim", "Good or bad", "Title", "Detail", "Before", "During", "Change %", "Currency/unit", "Amount involved", "Share of total %", "When", "How sure", "Where to look", "AI helper note"],
           [[f["id"], f["view"], f["level"], f["claim"], f["polarity"], f["title"], f["detail"], f["numbers"]["before"], f["numbers"]["after"],
             None if f["numbers"]["relative"] is None else round(f["numbers"]["relative"] * 100, 1), f["numbers"].get("unit"), f["numbers"]["impact"],
             None if not f["numbers"]["impact_share"] else round(f["numbers"]["impact_share"] * 100, 2), f["when"], f["evidence_strength"],
             next((i["where_to_look"] for k in ("fix", "keep", "watch") for i in report["intelligence"][k] if i["finding_id"] == f["id"]), ""),
             (f.get("investigation") or {}).get("summary") or ""] for f in report["insights"]["findings"]],
           [12, 28, 11, 22, 11, 60, 60, 12, 12, 10, 10, 14, 12, 18, 12, 60, 70])
    ws = wb.create_sheet("Fix-Keep-Watch")
    _sheet(ws, ["Bucket", "Finding", "Why", "Where to look"], [[k.capitalize(), i["title"], i["why"], i["where_to_look"]] for k in ("fix", "keep", "watch") for i in report["intelligence"][k]], [10, 70, 60, 70])
    ws = wb.create_sheet("Key numbers")
    _sheet(ws, ["File", "Measure", "Value", "Unit", "Recent change", "Vs year before"],
           [[v["view"], k["label"], k["value"], k.get("unit", ""), k.get("change_recent"), k.get("change_year")] for v in report["your_data"] for k in v["kpis"]], [34, 30, 16, 8, 14, 14])
    ws = wb.create_sheet("Breakdowns")
    _sheet(ws, ["File", "Measure", "By", "Group", "Amount", "Share", "Rows", "Vs year before"],
           [[v["view"], bd["measure"], bd["column"], r["value"], r["amount"], r["share"], r["rows"], r["change_year"]] for v in report["your_data"] for bd in v["breakdowns"] for r in bd["rows"]], [30, 26, 22, 22, 14, 10, 10, 14])
    ws = wb.create_sheet("Rows behind findings")
    rows, cols = [], 0
    for f in report["insights"]["findings"]:
        r = f.get("rows") or {}
        for line in r.get("rows", []):
            rows.append([f["id"], f["title"][:80], r.get("file"), *line]); cols = max(cols, len(line))
    _sheet(ws, ["Finding", "Title", "File", *[f"Column {i+1}" for i in range(cols)]], rows, [12, 50, 28])
    ws = wb.create_sheet("Owner notes")
    fb = {x["findingId"]: x["verdict"] for x in (owner or {}).get("feedback", [])}
    _sheet(ws, ["Type", "Item", "Answer or verdict"], [*[["Feedback", k, v] for k, v in fb.items()], *[["Answer", a["questionId"], a["answer"]] for a in (owner or {}).get("answers", [])]], [12, 40, 80])
    out = io.BytesIO(); wb.save(out)
    return out.getvalue()
