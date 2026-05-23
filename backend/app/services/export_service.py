# backend/app/services/export_service.py

from datetime import datetime, timedelta
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.database_models import Article, Board
from app.services.dashboard_service import build_keyword_filter


def get_export_articles(
    db: Session,
    keyword: str,
    days: int = 30,
    sort_by: str = "push_count",
    boards: list[str] | None = None,
    limit: int = 200,
) -> list[Article]:
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    query = (
        db.query(Article)
        .filter(build_keyword_filter(keyword))
        .filter(Article.published_at >= start_date)
        .filter(Article.published_at <= end_date)
    )

    if boards:
        query = query.filter(Article.board.has(Board.name.in_(boards)))

    if sort_by == "latest":
        query = query.order_by(desc(Article.published_at))
    else:
        query = query.order_by(desc(Article.push_count), desc(Article.published_at))

    return query.limit(limit).all()


def _cell(value) -> str:
    if value is None:
        value = ""

    text = escape(str(value))

    return f'<c t="inlineStr"><is><t>{text}</t></is></c>'


def _row(values: list, index: int) -> str:
    cells = "".join(_cell(value) for value in values)
    return f'<row r="{index}">{cells}</row>'


def build_articles_xlsx(articles: list[Article]) -> bytes:
    headers = [
        "ID",
        "Title",
        "Board",
        "Author",
        "Push Count",
        "Published At",
        "URL",
        "Preview",
    ]

    rows = [_row(headers, 1)]

    for index, article in enumerate(articles, start=2):
        content = (article.content or "").replace("\r", " ").replace("\n", " ")
        preview = content[:220]

        rows.append(_row([
            article.id,
            article.title,
            article.board.name if article.board else "",
            article.author.username if article.author else "unknown",
            article.push_count or 0,
            article.published_at.strftime("%Y-%m-%d %H:%M:%S") if article.published_at else "",
            article.url,
            preview,
        ], index))

    worksheet = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews><sheetView workbookViewId="0"/></sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>
    <col min="1" max="1" width="8" customWidth="1"/>
    <col min="2" max="2" width="42" customWidth="1"/>
    <col min="3" max="4" width="18" customWidth="1"/>
    <col min="5" max="6" width="16" customWidth="1"/>
    <col min="7" max="7" width="50" customWidth="1"/>
    <col min="8" max="8" width="60" customWidth="1"/>
  </cols>
  <sheetData>
    {''.join(rows)}
  </sheetData>
</worksheet>"""

    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Articles" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""

    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""

    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""

    output = BytesIO()

    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)

    return output.getvalue()
