"""Layout parser — structural region detection on top of OCR text extraction.

Phase P1: uses PyMuPDF (free, local) vector analysis to identify and map into the
`ocr_extraction` schema:
  - **Tables**       -> page.tables  (contract TableBlock: table_id, bbox,
                       header_row_idx, rows, conf) via page.find_tables()
  - **Official stamps/seals** and **Signatures** -> page.images
                       (contract ImageBlock: img_id, bbox, kind, ocr_text, conf)
                       via vector drawing classification + embedded raster scan.

`enrich()` consumes an `ocr_extraction` dict (contract 2) in place and returns
it, filling the per-page `tables`/`images` arrays. It is a pure in-process step
between OCR and NLP.
"""

from typing import Any

try:  # PyMuPDF new releases export `pymupdf`; older use legacy `fitz`
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz

#: ratio thresholds for region classification
_CURVE_OPS = {"c", "ke"}          # bezier curve + ellipse ops in drawing paths
_STAMP_ASPECT = (0.55, 1.9)       # circles / ovals
_SIGN_ASPECT = 2.0                # wide, thin strokes (typical signatures)
_MIN_REGION = 12.0                # ignore tiny marks
_DARK = 0.35                       # below this channel value = "ink dark"
_SIGNATURE_LABELS = ("signature", "authorized signatory", "sign", "witness")


class LayoutParser:
    """Structural layout analyser. Stateless; instantiate per job."""

    # -- public entry point -------------------------------------------------
    def enrich(self, extraction: dict, paths: dict[str, str] | None = None) -> dict:
        """Fill page `tables`/`images` arrays from PDF vector/raster analysis.

        `paths` maps file_id -> stored PDF path (the pages in `extraction` hold
        geometry only, no document handle).
        """
        paths = paths or {}
        for document in extraction.get("documents", []):
            path = paths.get(document.get("file_id"))
            if not path:
                continue
            try:
                with fitz.open(str(path)) as pdf:
                    self._enrich_document(document, pdf)
            except Exception:  # noqa: BLE001 — layout is best-effort, never fatal
                pass
        return extraction

    # -- document / page ----------------------------------------------------
    def _enrich_document(self, document: dict, pdf: Any) -> None:
        for page_dict in document.get("pages", []):
            page_no = page_dict.get("page_no", 1) - 1
            if page_no < 0 or page_no >= pdf.page_count:
                continue
            page = pdf[page_no]
            if "tables" not in page_dict:
                page_dict["tables"] = []
            if "images" not in page_dict:
                page_dict["images"] = []
            page_dict["tables"] = self._detect_tables(page, page_dict.get("page_no", 1))
            page_dict["images"] = self._detect_regions(page, page_dict, page_dict.get("page_no", 1))

    # -- tables --------------------------------------------------------------
    def _detect_tables(self, page: Any, page_no: int) -> list[dict]:
        out: list[dict] = []
        try:
            found = page.find_tables()
        except Exception:  # noqa: BLE001
            found = None

        for index, table in enumerate(found or [], start=1):
            rows: list[list[str]] = []
            try:
                rows = [[(cell or "").strip() for cell in row] for row in table.extract()]
                rows = [row for row in rows if any(row)]
            except Exception:  # noqa: BLE001
                continue
            if len(rows) < 2 or not rows[0]:
                continue  # degenerate: header only or empty table
            try:
                bbox = [float(v) for v in table.bbox]
            except Exception:  # noqa: BLE001
                bbox = [0.0, 0.0, 0.0, 0.0]
            header_confident = all(any(cell for cell in row) for row in rows[:2])
            out.append({
                "table_id": f"p{page_no}_t{index}",
                "bbox": bbox,
                "header_row_idx": 0,
                "rows": rows,
                "conf": 0.9 if header_confident else 0.7,
            })
        return out

    # -- stamps / signatures -------------------------------------------------
    def _detect_regions(self, page: Any, page_dict: dict, page_no: int) -> list[dict]:
        regions: list[dict] = []
        # 1) vector drawings (official seals are vector ellipses/arcs in CAD-exported PDFs)
        try:
            drawings = page.get_drawings()
        except Exception:  # noqa: BLE001
            drawings = []
        for drawing in drawings:
            rect = drawing.get("rect")
            if rect is None:
                continue
            classified = self._classify_region(rect, drawing.get("items") or [], drawing.get("fill"))
            if classified is None:
                continue
            kind, conf = classified
            region_rect = fitz.Rect(rect)
            if self._overlaps_any(region_rect, regions):
                continue
            ocr_text = None
            if kind == "stamp":
                ocr_text = self._text_in(page, region_rect)
            elif kind == "signature":
                ocr_text = self._signature_label(page, region_rect)
            regions.append(self._region(page_dict, region_rect, kind, ocr_text, conf))

        # 2) embedded raster images: round & small -> likely scanned stamp/seal
        try:
            image_list = page.get_images(full=True) or []
        except Exception:  # noqa: BLE001
            image_list = []
        for image in image_list:
            xref = image[0]
            try:
                rects = page.get_image_rects(xref) or []
            except Exception:  # noqa: BLE001
                continue
            for rect in rects:
                if rect.width < _MIN_REGION or rect.height < _MIN_REGION:
                    continue
                if self._overlaps_any(rect, regions):
                    continue
                aspect = rect.width / rect.height if rect.height else 99.0
                page_area = page_dict.get("page_w", 1.0) * page_dict.get("page_h", 1.0) or rect.get_area() * 8
                is_round = _STAMP_ASPECT[0] <= aspect <= _STAMP_ASPECT[1]
                is_small = rect.get_area() < page_area * 0.2
                kind = "stamp" if is_round and is_small else "photo"
                conf = 0.7 if kind == "stamp" else 0.5
                ocr_text = self._text_in(page, rect) if kind == "stamp" else None
                regions.append(self._region(page_dict, rect, kind, ocr_text, conf))
        return regions

    # -- classification heuristics --------------------------------------------
    @staticmethod
    def _classify_region(rect: Any, items: list, fill: Any) -> tuple[str, float] | None:
        if items is None or not items or rect is None:
            return None
        width, height = rect.width, rect.height
        if width < _MIN_REGION or height < _MIN_REGION:
            return None
        aspect = width / height if height else 0.0
        curve_count = sum(1 for item in items if item and item[0] in _CURVE_OPS)
        colored = LayoutParser._is_colored(fill)

        if _STAMP_ASPECT[0] <= aspect <= _STAMP_ASPECT[1] and len(items) >= 2 \
                and (colored or curve_count >= 2):
            return "stamp", (0.82 if colored else 0.62)
        if aspect >= _SIGN_ASPECT and len(items) >= 3 and not colored:
            return "signature", 0.55
        return None

    @staticmethod
    def _is_colored(fill: Any) -> bool:
        if not fill:
            return False
        channels = [c for c in fill if c is not None]
        if len(channels) < 3:
            return False
        spread = max(channels) - min(channels)  # gray ink has ~no spread
        return spread > 0.15 and min(channels) > 0.05

    @staticmethod
    def _is_dark(channels: list) -> bool:
        return all(c <= _DARK for c in channels)

    @staticmethod
    def _overlaps_any(rect: Any, regions: list[dict]) -> bool:
        area = rect.get_area()
        for region in regions:
            other = fitz.Rect(region["bbox"])
            inter = other & rect
            if inter.is_empty:
                continue
            overlap = inter.get_area() / min(area, other.get_area())
            if overlap > 0.65:
                return True
        return False

    @staticmethod
    def _text_in(page: Any, rect: Any) -> str | None:
        try:
            text = page.get_text("text", clip=rect).strip()
        except Exception:  # noqa: BLE001
            return None
        return text[:200] or None

    @staticmethod
    def _signature_label(page: Any, rect: Any) -> str | None:
        """Return nearby label like 'Authorized Signatory' if any, else None."""
        try:
            page_text = page.get_text("text")
        except Exception:  # noqa: BLE001
            return None
        needle = page_text.lower()
        for label in _SIGNATURE_LABELS:
            if label in needle:
                return label
        return None

    @staticmethod
    def _region(page_dict: dict, rect: Any, kind: str, ocr_text: str | None, conf: float) -> dict:
        return {
            "img_id": f"p{page_dict.get('page_no', 1)}_img{rect.x0:.0f}x{rect.y0:.0f}",
            "bbox": [rect.x0, rect.y0, rect.x1, rect.y1],
            "kind": kind,
            "ocr_text": ocr_text,
            "conf": round(conf, 2),
        }