# 03 — Inter-Module Contracts Specification

Every message that crosses a module boundary is defined here and in
`contracts/*.schema.json` (JSON Schema draft-07). These files are the **single
source of truth**. Backend Pydantic models (`backend/app/schemas/`) mirror them,
and the frontend consumes the same shapes over REST.

## Communication Matrix

| Contract            | Producer             | Consumer               | Transport         | File                              |
| ------------------- | -------------------- | ---------------------- | ----------------- | --------------------------------- |
| document_upload     | Frontend / caller    | Backend upload route   | POST /api/v1/upload | `document_upload.schema.json`  |
| ocr_extraction      | core_ai.ocr          | core_ai.nlp, DB        | in-process dict    | `ocr_extraction.schema.json`   |
| parsed_document     | core_ai.nlp          | core_ai.rules, DB      | in-process dict    | `parsed_document.schema.json`  |
| validation_rule     | DB rule pack         | core_ai.rules          | in-process row     | `validation_rule.schema.json`  |
| validation_result   | core_ai.rules        | Backend, Dashboard     | GET /validate, DB  | `validation_result.schema.json`|
| compliance_dashboard| Backend              | Frontend dashboard     | GET /dashboard/{bid_id} | `compliance_dashboard.schema.json`|
| api_envelope        | Backend              | Frontend (all calls)   | all responses      | `api_envelope.schema.json`     |

## Field Dictionaries

### document_upload (contract 1)
| Field        | Type                    | Notes                                  |
| ------------ | ----------------------- | -------------------------------------- |
| `tender_id`  | string                  | GeM tender reference                   |
| `bid_id`     | string                  | bid reference (dashboard key)          |
| `supplier`   | string                  | bidder name                            |
| `category`   | string                  | commodity category                     |
| `files[]`    | array                   | each with `file_name`, `file_type` (pdf/image/docx), `doc_role` |
| `doc_role`   | enum                    | `technical_bid, financial_bid, emd, certificates, annexure` |

### ocr_extraction (contract 2)
| Field                  | Type     | Notes                                      |
| ---------------------- | -------- | ------------------------------------------ |
| `status`               | enum     | `completed, partial, failed`               |
| `documents[].pages[]`  | array    | per-page `text_blocks` (typed, bbox, conf), `tables` (grid + bbox), `images` (stamp/signature/…), `full_text` |
| `text_blocks[].block_type` | enum | `heading, body, table_cell, header, footer, stamp, signature, other` |
| `confidence`           | 0..1     | per block/table/image                      |

### parsed_document (contract 3)
| Field          | Type  | Notes                                          |
| -------------- | ----- | ---------------------------------------------- |
| `sections[]`   | array | `heading`, `body`, `keywords`, `page`, `entities[]`, `tables_normalized[]` |
| `entities[]`   | array | typed entity: `{entity, value, normalized_value, confidence, source_span}` |
| `key_value_pairs[]` | array | `{key, value, confidence, source_span}`   |
| `tables_normalized[]` | array | `{table_id, columns[], rows[][]}`        |
| `source_span`  | object| page + char offsets + optional bbox for evidence drill-down |

### validation_rule (contract 4)
| Field             | Notes                                                        |
| ----------------- | ------------------------------------------------------------ |
| `severity`        | `blocking` (auto-reject), `mandatory`, `advisory`            |
| `element`         | which `doc_role` the rule inspects                           |
| `target`          | entity type (`EMD_PERCENTAGE`), kv key (`kv.GSTIN`), or text (`word('valid until')`) |
| `operator`        | `>=, <=, ==, !=, >, <, contains, exists, not_exists, regex, date_after, llm_judge` |
| `expected_value`  | comparison constant (for `llm_judge`: free-text instruction) |
| `expression`      | optional compound condition (future)                         |

### validation_result (contract 5)
| Field            | Notes                                                       |
| ---------------- | ----------------------------------------------------------- |
| `results[]`      | `{rule_id, status(pass/fail/warn/skip/error), evidence{found, source_span, file_id, table_id}, reason, confidence, suggested_action}` |
| `overall_status` | `COMPLIANT` if no blocking/mandatory fails; `DISCREPANT` else; `NEEDS_REVIEW` for warns/skips only |
| `score`          | counts by severity and status + `compliance_pct`            |

### compliance_dashboard (contract 6)
| Field                  | Notes                                          |
| ---------------------- | ---------------------------------------------- |
| `status`               | adds `IN_PROGRESS` while pipeline runs         |
| `category_breakdown[]` | per-category pass/fail/warn/total              |
| `documents[]`          | per-file stage (`uploaded/ocr_done/parsed/validated/failed`) + status |
| `issues[]`             | flat, severity-sorted list for the discrepancy panel |
| `timeline[]`           | per-stage `{stage, status, ts, runtime_ms, message}` |

## Design Rules

1. **Forward-compatible:** unknown fields are ignored by consumers (permissive
   readers), producers never emit extra-fields without a schema bump + version.
2. **Evidence everywhere:** any AI-produced value carries `confidence` and
   `source_span` so the UI can show *where* the engine looked.
3. **No shared mutable state:** modules exchange immutable dicts/JSON validated at
   each boundary; nothing reaches across packages.
4. **Versioning:** a breaking change bumps the schema `$id` (e.g.,
   `document_upload.v2.schema.json`) and both producer/consumer are updated in the
   same commit during the hackathon.

## Example End-To-End Flow (trace)

```text
POST /api/v1/upload
  body: document_upload { tender_id, bid_id, files[2] {doc_role: technical_bid}, {doc_role: emd} }
→ 202 { status: accepted, request_id: "...", data: { request_id, tender_id, bid_id } }

pipeline (async, in-process):
  upload.ocr.extractor(bod_docs)            → ocr_extraction        (stage=ocr_done)
  upload.nlp.structure(ocr_extraction)      → parsed_document       (stage=parsed)
  upload.rules.evaluate(parsed, rule_pack)  → validation_result     (stage=validated)

GET /api/v1/dashboard/{bid_id}
→ 200 { status: ok, data: compliance_dashboard { status, score, issues[], timeline[] } }
```

A single `request_id` ties all stages together; the dashboard timeline is
reconstructed from `pipeline_events` in the DB.