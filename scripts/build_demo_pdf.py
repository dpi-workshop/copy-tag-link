#!/usr/bin/env python
"""Build the styled PDF sample used by CTL-Core sample workflows.

This script is optional and only needed when regenerating the sample PDF.
It uses ReportLab and Pillow from the local environment.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, Image as PdfImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


SAMPLE_DIR = Path("samples/simple-source")
PDF_PATH = SAMPLE_DIR / "market-snapshot.pdf"
IMAGE_PATH = SAMPLE_DIR / "demo-photo.png"


def build_demo_image() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (720, 360), "#e0f2fe")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 720, 80), fill="#0f766e")
    draw.text((28, 26), "Reusable image asset", fill="white")
    draw.rounded_rectangle((70, 130, 250, 300), radius=22, fill="#f97316")
    draw.rounded_rectangle((280, 110, 650, 155), radius=12, fill="#1e3a8a")
    draw.rounded_rectangle((280, 180, 610, 225), radius=12, fill="#7c3aed")
    draw.rounded_rectangle((280, 250, 560, 295), radius=12, fill="#334155")
    draw.text((105, 202), "IMG", fill="white")
    draw.text((305, 124), "Original files stay preserved", fill="white")
    draw.text((305, 194), "Assets are copied and linked", fill="white")
    draw.text((305, 264), "Indexes are rebuildable", fill="white")
    image.save(IMAGE_PATH)


class HeaderBlock(Flowable):
    def __init__(self, width: float = 7.5 * inch, height: float = 1.25 * inch) -> None:
        super().__init__()
        self.width = width
        self.height = height

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#0f766e"))
        canvas.roundRect(0, 0, self.width, self.height, 10, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#f97316"))
        canvas.circle(self.width - 0.55 * inch, self.height - 0.38 * inch, 0.18 * inch, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 24)
        canvas.drawString(0.35 * inch, 0.72 * inch, "CTL Demo Market Snapshot")
        canvas.setFont("Helvetica", 10)
        canvas.drawString(0.36 * inch, 0.42 * inch, "Styled PDF source for Copy, Tag, Link ingestion")
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawRightString(self.width - 0.35 * inch, 0.18 * inch, "Generated sample | Public demo data")
        canvas.restoreState()


class DiagramBlock(Flowable):
    def __init__(self, width: float = 7.5 * inch, height: float = 1.55 * inch) -> None:
        super().__init__()
        self.width = width
        self.height = height

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.setFillColor(colors.HexColor("#f8fafc"))
        canvas.roundRect(0, 0, self.width, self.height, 8, stroke=1, fill=1)
        labels = [
            ("Source PDF", "#1d4ed8"),
            ("Copy", "#0f766e"),
            ("Tag", "#f97316"),
            ("Link", "#7c3aed"),
            ("CTL Package", "#334155"),
        ]
        box_w = 1.15 * inch
        gap = 0.28 * inch
        start_x = 0.35 * inch
        box_y = 0.55 * inch
        for index, (label, color) in enumerate(labels):
            box_x = start_x + index * (box_w + gap)
            canvas.setFillColor(colors.HexColor(color))
            canvas.roundRect(box_x, box_y, box_w, 0.45 * inch, 6, stroke=0, fill=1)
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawCentredString(box_x + box_w / 2, box_y + 0.19 * inch, label)
            if index < len(labels) - 1:
                arrow_x = box_x + box_w + 0.06 * inch
                arrow_y = box_y + 0.225 * inch
                canvas.setStrokeColor(colors.HexColor("#64748b"))
                canvas.line(arrow_x, arrow_y, arrow_x + gap - 0.12 * inch, arrow_y)
                canvas.line(arrow_x + gap - 0.12 * inch, arrow_y, arrow_x + gap - 0.20 * inch, arrow_y + 0.06 * inch)
                canvas.line(arrow_x + gap - 0.12 * inch, arrow_y, arrow_x + gap - 0.20 * inch, arrow_y - 0.06 * inch)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.setFont("Helvetica-Oblique", 8)
        canvas.drawCentredString(
            self.width / 2,
            0.22 * inch,
            "Original stays preserved. Assets, records, search indexes, and OKF cards stay linked.",
        )
        canvas.restoreState()


def build_pdf() -> None:
    build_demo_image()
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Deck",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#334155"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            textColor=colors.HexColor("#1e3a8a"),
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Caption",
            parent=styles["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748b"),
            alignment=1,
        )
    )

    story = [HeaderBlock(), Spacer(1, 0.12 * inch)]
    story.append(Paragraph("Summary", styles["Section"]))
    story.append(
        Paragraph(
            "Semantic HTML can preserve document structure before any database, vector store, or graph layer is added. "
            "The original document remains in the CTL package, while extracted records link back to the source and copied assets.",
            styles["Deck"],
        )
    )
    story.append(Paragraph("Adoption Signals", styles["Section"]))
    data = [
        ["Signal", "Value", "Note"],
        ["HTML structure", "High", "Headings, tables, figures, and links remain visible."],
        ["Database requirement", "None", "The package opens as static files."],
        ["Adapter flexibility", "High", "Indexes can be rebuilt from the CTL package."],
    ]
    table = Table(data, colWidths=[1.7 * inch, 1.15 * inch, 4.05 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#eff6ff")),
                ("BACKGROUND", (0, 2), (-1, 2), colors.white),
                ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#f0fdf4")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.12 * inch))
    story.append(DiagramBlock())
    story.append(Paragraph("Generated diagram: source data becomes a portable CTL package.", styles["Caption"]))
    story.append(Paragraph("Image Asset", styles["Section"]))
    story.append(PdfImage(str(IMAGE_PATH), width=3.6 * inch, height=1.8 * inch))
    story.append(Paragraph("Generated image: reusable visual asset embedded in the PDF.", styles["Caption"]))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph("Learn more from the CTL-Core repository: https://github.com/dpi-workshop/ctl-core", styles["Deck"]))

    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
    )
    doc.build(story)


if __name__ == "__main__":
    build_pdf()
    print(PDF_PATH.resolve())
