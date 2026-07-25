"""
Render memo/decision_memo.md to a submission-ready PDF.

The PDF is generated FROM the Markdown, not hand-written in reportlab calls, so
the two can never drift apart -- edit the memo in one place and regenerate.
Supports the small Markdown subset the memo uses: #/## headings, **bold**,
*italic*, `---` rules, `>` notes, and paragraphs.
"""

from __future__ import annotations

import html
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

import config as cfg
from logging_config import get_logger

log = get_logger(__name__)
ACCENT = colors.HexColor("#c1440e")
DARK = colors.HexColor("#1a202c")
MUTED = colors.HexColor("#4a5568")

ss = getSampleStyleSheet()
S = {
    "h1": ParagraphStyle("h1", parent=ss["Title"], fontSize=15, leading=18,
                         textColor=DARK, alignment=0, spaceAfter=2),
    "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11, leading=13,
                         textColor=ACCENT, spaceBefore=8, spaceAfter=3),
    "body": ParagraphStyle("body", parent=ss["Normal"], fontSize=9, leading=12.5,
                           alignment=TA_JUSTIFY, textColor=DARK, spaceAfter=5),
    "meta": ParagraphStyle("meta", parent=ss["Normal"], fontSize=8.5, leading=12,
                           textColor=MUTED, spaceAfter=4),
}


def inline(text: str) -> str:
    """Markdown inline -> reportlab mini-HTML."""
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    return text


def build() -> None:
    md = (cfg.ROOT / "memo" / "decision_memo.md").read_text(encoding="utf-8")
    out = cfg.ROOT / "memo" / "decision_memo.pdf"
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=20 * mm,
                            rightMargin=20 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="Decision Memo - Onion Selling Windows")
    flow = []
    para: list[str] = []

    def flush():
        if para:
            flow.append(Paragraph(inline(" ".join(para)), S["body"]))
            para.clear()

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        if line.startswith("# "):
            flush(); flow.append(Paragraph(inline(line[2:]), S["h1"]))
        elif line.startswith("## "):
            flush(); flow.append(Paragraph(inline(line[3:]), S["h2"]))
        elif line.startswith("---"):
            flush(); flow.append(HRFlowable(width="100%", thickness=0.6,
                     color=colors.HexColor("#d0d5dd"), spaceBefore=3, spaceAfter=6))
        elif line.startswith("**To:**") or line.startswith("*Analysis"):
            flush(); flow.append(Paragraph(inline(line), S["meta"]))
        else:
            para.append(line.strip())
    flush()

    doc.build(flow)
    log.info("PDF -> %s", out)


if __name__ == "__main__":
    build()
