# core_ai — Document Intelligence Package

Pure Python, in-process, **zero HTTP coupling**. Imported by `backend.app.services`
to execute pipeline Stages 1-3 (see `docs/02_core_workflow.md`).

| Package            | Stage | Emits                         |
| ------------------ | ----- | ----------------------------- |
| `core_ai/ocr/`     | 1     | contract 2 `ocr_extraction`   |
| `core_ai/nlp/`     | 2     | contract 3 `parsed_document`  |
| `core_ai/rules/`   | 3     | contract 5 `validation_result`|
| `core_ai/llm/`     | 3 opt| llm_judge verdicts             |

Rules of thumb:
- All public entry points accept/return **plain dicts matching the contracts**
  (`contracts/*.schema.json`). No FastAPI, no SQLAlchemy here.
- Never raise to block the pipeline: errors surface via `status` +
  `errors[]` / per-rule `error` status.
- Heavy models (PaddleOCR, spaCy) load lazily on first call and are cached on
  the extractor/engine instances.