"""Pydantic mirrors for contracts 1-3: document_upload, ocr_extraction, parsed_document.

Source of truth: contracts/*.schema.json.
"""

from pydantic import BaseModel, Field

DOC_ROLES = ["technical_bid", "financial_bid", "emd", "certificates", "annexure"]
FILE_TYPES = ["pdf", "image", "docx"]


# ---- Contract 1: document_upload ----
class FileInput(BaseModel):
    file_id: str | None = None
    file_name: str
    file_type: str = Field(..., pattern="|".join(FILE_TYPES))
    size_bytes: int | None = None
    sha256: str | None = None
    doc_role: str = Field(..., pattern="|".join(DOC_ROLES))


class DocumentUpload(BaseModel):
    request_id: str | None = None
    tender_id: str
    bid_id: str
    supplier: str
    category: str
    submitted_at: str | None = None
    files: list[FileInput]


# ---- Contract 2: ocr_extraction ----
class SourceSpan(BaseModel):
    page: int
    start: int | None = None
    end: int | None = None
    bbox: list[float] | None = None


class TextBlock(BaseModel):
    block_id: str
    text: str
    conf: float = Field(ge=0, le=1)
    bbox: list[float]  # [x1,y1,x2,y2]
    block_type: str  # heading|body|table_cell|header|footer|stamp|signature|other


class TableBlock(BaseModel):
    table_id: str
    bbox: list[float]
    header_row_idx: int | None = None
    rows: list[list[str]]
    conf: float = Field(ge=0, le=1)


class ImageBlock(BaseModel):
    img_id: str
    bbox: list[float]
    kind: str  # stamp|signature|logo|photo|other
    ocr_text: str | None = None
    conf: float | None = Field(default=None, ge=0, le=1)


class Page(BaseModel):
    page_no: int = Field(ge=1)
    page_w: float | None = None
    page_h: float | None = None
    dpi: int | None = None
    text_blocks: list[TextBlock] = Field(default_factory=list)
    tables: list[TableBlock] = Field(default_factory=list)
    images: list[ImageBlock] = Field(default_factory=list)
    full_text: str = ""


class DocumentOcr(BaseModel):
    file_id: str
    doc_role: str
    pages: list[Page]
    meta: dict = Field(default_factory=dict)


class OcrExtraction(BaseModel):
    request_id: str
    tender_id: str | None = None
    bid_id: str | None = None
    status: str = "completed"  # completed|partial|failed
    errors: list[dict] = Field(default_factory=list)
    documents: list[DocumentOcr]


# ---- Contract 3: parsed_document ----
class Entity(BaseModel):
    entity: str
    value: str
    normalized_value: str | float | bool | None = None
    confidence: float = Field(ge=0, le=1)
    source_span: SourceSpan | None = None


class KeyValuePair(BaseModel):
    key: str
    value: str
    confidence: float = Field(ge=0, le=1)
    source_span: SourceSpan | None = None


class Section(BaseModel):
    section_id: str
    heading: str
    body: str
    keywords: list[str] = Field(default_factory=list)
    page: int | None = None
    entities: list[Entity] = Field(default_factory=list)
    tables_normalized: list[str] = Field(default_factory=list)


class TableNormalized(BaseModel):
    table_id: str
    columns: list[str]
    rows: list[list[str]]


class ParsedDocument(BaseModel):
    file_id: str
    doc_role: str
    sections: list[Section] = Field(default_factory=list)
    key_value_pairs: list[KeyValuePair] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    tables_normalized: list[TableNormalized] = Field(default_factory=list)
    summary: str | None = None
    confidence: float = Field(ge=0, le=1)


class ParsedBundle(BaseModel):
    request_id: str
    tender_id: str | None = None
    bid_id: str | None = None
    status: str = "completed"
    documents: list[ParsedDocument]