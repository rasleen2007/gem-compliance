# reference/ — Offline fixtures

Keep demo assets here so the pipeline works with zero network at the hackathon.

- `sample_tender_rules.geojson` / `.csv` — exported rule packs (mirror seed_rules.sql)
- `sample_bids/` — 2-3 anonymized bid PDFs (technical + financial + EMD)
- `mock_payloads/` — hand-written contract samples (1 per contract) for contract
  tests and frontend dev without a running backend

| File (planned)                          | Contract           |
| --------------------------------------- | ------------------ |
| `mock_payloads/upload.json`             | document_upload    |
| `mock_payloads/ocr_extraction.json`     | ocr_extraction     |
| `mock_payloads/parsed_document.json`    | parsed_document    |
| `mock_payloads/validation_result.json`  | validation_result  |
| `mock_payloads/dashboard.json`          | compliance_dashboard |

> Add the first mock (dashboard.json) in Phase P2 so the frontend can be built
> against a sealed fixture while the pipeline is still in progress.