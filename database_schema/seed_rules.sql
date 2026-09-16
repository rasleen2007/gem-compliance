-- Seed rule pack (contract 4) for the demo tender GeM/2026/B/123456.
-- Mirrors backend/app/core/db.py::_seed_demo_rules (source of truth).
-- Categories mirror the MVP compliance dashboard: EMD, Eligibility, Technical,
-- Financial, Certificates. Adjust expected_value per actual tender.

INSERT OR IGNORE INTO validation_rules
    (rule_id, tender_id, category, description, severity, element, target, operator, expected_value, notes) VALUES
-- EMD (Rule-EMD: financial threshold)
('RULE-EMD-001', 'GeM/2026/B/123456', 'EMD',
 'Earnest Money Deposit (EMD) must be at least 50,000 INR', 'blocking', 'all',
 'EMD_AMOUNT', '>=', '50000', 'Auto-extract from EMD/financial sections'),

-- Document presence (Rule-DOC)
('RULE-DOC-001', 'GeM/2026/B/123456', 'Eligibility',
 'Supplier GSTIN registration must be present', 'blocking', 'all',
 'GSTIN', 'exists', NULL, 'Entity token or text presence'),
('RULE-DOC-002', 'GeM/2026/B/123456', 'Eligibility',
 'Supplier PAN must be present', 'mandatory', 'all',
 'PAN', 'exists', NULL, 'Entity token or text presence'),
('RULE-DOC-003', 'GeM/2026/B/123456', 'Financial',
 'Itemized price breakup table must be attached', 'advisory', 'financial_bid',
 'table:PRICE_BREAKUP', 'exists', NULL, 'Table block or keyword grouping'),

-- Date comparison (Rule-DATE)
('RULE-DATE-001', 'GeM/2026/B/123456', 'Certificates',
 'Certificate/document validity must extend past the tender deadline (2026-06-30)', 'mandatory', 'certificates',
 'CERT_VALIDITY', 'date_after', '2026-06-30', 'Compare extracted validity date against tender deadline'),
('RULE-DATE-002', 'GeM/2026/B/123456', 'Eligibility',
 'Company incorporation date must precede 2020-01-01 (eligibility criterion)', 'advisory', 'all',
 'INCORPORATION_DATE', 'date_before', '2020-01-01', 'Recency filter on the bidding entity'),

-- Financial turnover (Rule-FIN: multi-line FY parse)
('RULE-FIN-001', 'GeM/2026/B/123456', 'Financial',
 'Latest financial year turnover must be at least 1,00,00,000 INR (1 crore)', 'mandatory', 'financial_bid',
 'TURNOVER', '>=', '10000000', 'Multi-line financial-year + amount extraction'),

-- Multi-document identity cross-check (Rule-XCHK)
('RULE-XCHK-001', 'GeM/2026/B/123456', 'Cross-Check',
 'Company legal name must match across every uploaded document (financial spreadsheet vs Certificate of Incorporation)', 'blocking', 'all',
 'COMPANY_NAME', 'cross_check', NULL, 'Reconcile COMPANY_NAME normalized values across all files'),
('RULE-XCHK-002', 'GeM/2026/B/123456', 'Cross-Check',
 'PAN must be identical across every uploaded document', 'blocking', 'all',
 'PAN', 'cross_check', NULL, 'Reconcile PAN normalized values across all files'),
('RULE-XCHK-003', 'GeM/2026/B/123456', 'Cross-Check',
 'GSTIN must be identical across every uploaded document', 'blocking', 'all',
 'GSTIN', 'cross_check', NULL, 'Reconcile GSTIN normalized values across all files'),
('RULE-XCHK-004', 'GeM/2026/B/123456', 'Cross-Check',
 'CIN (Certificate of Incorporation) must match on all referenced documents', 'mandatory', 'all',
 'CIN', 'cross_check', NULL, 'Reconcile CIN normalized values across all files'),
('RULE-XCHK-005', 'GeM/2026/B/123456', 'Cross-Check',
 'Company registration number must agree across all uploaded documents', 'mandatory', 'all',
 'COMPANY_REGISTRATION_NUMBER', 'cross_check', NULL, 'Reconcile incorporation registration number across all files'),
('RULE-XCHK-006', 'GeM/2026/B/123456', 'Cross-Check',
 'Incorporation date must agree across all uploaded documents', 'advisory', 'all',
 'INCORPORATION_DATE', 'cross_check', NULL, 'Reconcile incorporation date across all files');

-- ===========================================================================
-- Demo bids (Phase P4) â€” idempotent dashboard-ready history for live pitches.
-- Mirrors backend/app/core/db.py::_seed_demo_bids (db.py is the runtime source
-- of truth; this block mirrors it for manual/ops seeding). Every statement is
-- guarded so re-running this file is safe. Evidence JSON is provided only for
-- failing results (the dashboard's Issues panel reads only fail rows).
-- ===========================================================================

-- rule_results auto-increments (no UNIQUE(bid_id, rule_id)): mirror db.py by
-- clearing the three demo bids' rows first so re-runs never duplicate verdicts.
DELETE FROM rule_results WHERE bid_id IN ('demo-pass-001', 'demo-fail-001', 'demo-conflict-001');

-- -- PASS: Bharat Infrastructure Ltd -> COMPLIANT ----------------------------
INSERT OR IGNORE INTO bids (bid_id, tender_id, supplier, category, request_id, overall_status)
VALUES ('demo-pass-001', 'GeM/2026/B/123456', 'Bharat Infrastructure Ltd', 'Civil Works', 'req-demo-pass-001', 'COMPLIANT');

INSERT OR IGNORE INTO documents
    (file_id, bid_id, file_name, file_type, doc_role, size_bytes, sha256, store_path, stage, stage_status) VALUES
('demo-file-pass-tech', 'demo-pass-001', 'technical_bid_bharat.pdf', 'pdf', 'technical_bid', 482132, '9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f', 'demo/pass/technical_bid_bharat.pdf', 'validated', 'ok'),
('demo-file-pass-fin',  'demo-pass-001', 'financial_bid_bharat.pdf', 'pdf', 'financial_bid', 315840, '8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e', 'demo/pass/financial_bid_bharat.pdf', 'validated', 'ok'),
('demo-file-pass-cert', 'demo-pass-001', 'certificate_bharat.pdf', 'pdf', 'certificates', 1029440, '7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d7d', 'demo/pass/certificate_bharat.pdf', 'validated', 'ok'),
('demo-file-pass-emd',  'demo-pass-001', 'emd_receipt_bharat.pdf', 'pdf', 'emd', 88240, '6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c6c', 'demo/pass/emd_receipt_bharat.pdf', 'validated', 'ok');

INSERT INTO rule_results (bid_id, rule_id, status, evidence, reason, confidence, suggested_action) VALUES
('demo-pass-001', 'RULE-EMD-001', 'pass', '{"found":"EMD of Rs. 75,000 furnished via Bank Guarantee"}', 'Extracted 75000.0 >= required 50000.0', 0.95, 'none'),
('demo-pass-001', 'RULE-DOC-001', 'pass', '{"found":"27AABCA1234F1Z5"}', 'GSTIN present in parsed document', 0.9, 'none'),
('demo-pass-001', 'RULE-DOC-002', 'pass', '{"found":"AABCA1234D"}', 'PAN present in parsed document', 0.9, 'none'),
('demo-pass-001', 'RULE-DOC-003', 'pass', '{"found":"Itemized price breakup table detected"}', 'table:PRICE_BREAKUP present in parsed document', 0.9, 'none'),
('demo-pass-001', 'RULE-DATE-001', 'pass', '{"found":"valid till 2027-12-31"}', 'CERT_VALIDITY 2027-12-31 is after 2026-06-30', 0.9, 'none'),
('demo-pass-001', 'RULE-DATE-002', 'pass', '{"found":"Date of Incorporation: 2015-03-20"}', 'INCORPORATION_DATE 2015-03-20 is before 2020-01-01', 0.9, 'none'),
('demo-pass-001', 'RULE-FIN-001', 'pass', '{"found":"Financial Year 2025-26 turnover of Rs. 2.50 crore"}', 'Extracted 2.5e+07 >= required 1e+07', 0.95, 'none'),
('demo-pass-001', 'RULE-XCHK-001', 'pass', '{"found":"COMPANY_NAME consistent across 4 document(s)"}', 'consistent', 0.9, 'none'),
('demo-pass-001', 'RULE-XCHK-002', 'pass', '{"found":"PAN consistent across 4 document(s)"}', 'consistent', 0.9, 'none'),
('demo-pass-001', 'RULE-XCHK-003', 'pass', '{"found":"GSTIN consistent across 4 document(s)"}', 'consistent', 0.9, 'none'),
('demo-pass-001', 'RULE-XCHK-004', 'pass', '{"found":"CIN consistent across 2 document(s)"}', 'consistent', 0.9, 'none'),
('demo-pass-001', 'RULE-XCHK-005', 'pass', '{"found":"COMPANY_REGISTRATION_NUMBER consistent across 2 document(s)"}', 'consistent', 0.9, 'none'),
('demo-pass-001', 'RULE-XCHK-006', 'pass', '{"found":"INCORPORATION_DATE consistent across 4 document(s)"}', 'consistent', 0.9, 'none');

-- -- FAIL: Global Parts Exports -> DISCREPANT (one corrupt file isolated) ----
INSERT OR IGNORE INTO bids (bid_id, tender_id, supplier, category, request_id, overall_status)
VALUES ('demo-fail-001', 'GeM/2026/B/123456', 'Global Parts Exports', 'Industrial Supplies', 'req-demo-fail-001', 'DISCREPANT');

INSERT OR IGNORE INTO documents
    (file_id, bid_id, file_name, file_type, doc_role, size_bytes, sha256, store_path, stage, stage_status) VALUES
('demo-file-fail-tech', 'demo-fail-001', 'technical_bid_global.pdf', 'pdf', 'technical_bid', 391044, '5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b', 'demo/fail/technical_bid_global.pdf', 'validated', 'ok'),
('demo-file-fail-fin',  'demo-fail-001', 'financial_bid_global.pdf', 'pdf', 'financial_bid', 262180, '4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a', 'demo/fail/financial_bid_global.pdf', 'validated', 'ok'),
('demo-file-fail-cert', 'demo-fail-001', 'certificate_global.pdf', 'pdf', 'certificates', 0, '3939393939393939393939393939393939393939393939393939393939393939', 'demo/fail/certificate_global.pdf', 'failed', 'error');

INSERT INTO rule_results (bid_id, rule_id, status, evidence, reason, confidence, suggested_action) VALUES
('demo-fail-001', 'RULE-EMD-001', 'fail', '{"found":"EMD of Rs. 10,000 furnished (below threshold)"}', 'Extracted 10000.0 < required 50000.0', 0.9, 'attach_missing_doc'),
('demo-fail-001', 'RULE-DOC-001', 'fail', '{"found":null,"missing":["GSTIN"]}', 'GSTIN: [] not found in parsed document', 0.9, 'attach_missing_doc'),
('demo-fail-001', 'RULE-DOC-002', 'fail', '{"found":null,"missing":["PAN"]}', 'PAN: [] not found in parsed document', 0.9, 'attach_missing_doc'),
('demo-fail-001', 'RULE-DOC-003', 'fail', '{"found":null,"missing":["table:PRICE_BREAKUP"]}', 'table:PRICE_BREAKUP not found in parsed document', 0.9, 'attach_missing_doc'),
('demo-fail-001', 'RULE-DATE-001', 'skip', '{}', 'No comparable date available', 0.5, 'manual_review'),
('demo-fail-001', 'RULE-DATE-002', 'skip', '{}', 'No comparable date available', 0.5, 'manual_review'),
('demo-fail-001', 'RULE-FIN-001', 'fail', '{"found":"Financial Year 2025-26 turnover of Rs. 25 lakh (below 1 crore)"}', 'Extracted 2.5e+06 < required 1e+07', 0.9, 'attach_missing_doc'),
('demo-fail-001', 'RULE-XCHK-001', 'pass', '{"found":"COMPANY_NAME consistent across 2 document(s)"}', 'consistent', 0.9, 'none'),
('demo-fail-001', 'RULE-XCHK-002', 'pass', '{"found":"PAN consistent across 2 document(s)"}', 'consistent', 0.9, 'none'),
('demo-fail-001', 'RULE-XCHK-003', 'pass', '{"found":"GSTIN consistent across 2 document(s)"}', 'consistent', 0.9, 'none'),
('demo-fail-001', 'RULE-XCHK-004', 'pass', '{"found":"CIN consistent across 2 document(s)"}', 'consistent', 0.9, 'none'),
('demo-fail-001', 'RULE-XCHK-005', 'pass', '{"found":"COMPANY_REGISTRATION_NUMBER consistent across 2 document(s)"}', 'consistent', 0.9, 'none'),
('demo-fail-001', 'RULE-XCHK-006', 'pass', '{"found":"INCORPORATION_DATE consistent across 2 document(s)"}', 'consistent', 0.9, 'none');

-- -- CONFLICT: Sri Ganesh Electricals -> DISCREPANT (XCHK identity streak) ---
INSERT OR IGNORE INTO bids (bid_id, tender_id, supplier, category, request_id, overall_status)
VALUES ('demo-conflict-001', 'GeM/2026/B/123456', 'Sri Ganesh Electricals', 'Electrical Goods', 'req-demo-conflict-001', 'DISCREPANT');

INSERT OR IGNORE INTO documents
    (file_id, bid_id, file_name, file_type, doc_role, size_bytes, sha256, store_path, stage, stage_status) VALUES
('demo-file-conflict-fin',  'demo-conflict-001', 'financial_bid_ganesh.pdf', 'pdf', 'financial_bid', 298644, '2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f', 'demo/conflict/financial_bid_ganesh.pdf', 'validated', 'ok'),
('demo-file-conflict-cert', 'demo-conflict-001', 'certificate_ganesh.pdf', 'pdf', 'certificates', 1145100, '1010101010101010101010101010101010101010101010101010101010101010', 'demo/conflict/certificate_ganesh.pdf', 'validated', 'ok');

INSERT INTO rule_results (bid_id, rule_id, status, evidence, reason, confidence, suggested_action) VALUES
('demo-conflict-001', 'RULE-EMD-001', 'pass', '{"found":"EMD of Rs. 60,000 furnished via Bank Guarantee"}', 'Extracted 60000.0 >= required 50000.0', 0.95, 'none'),
('demo-conflict-001', 'RULE-DOC-001', 'pass', '{"found":"33AACCS1234F1Z8"}', 'GSTIN present in parsed document', 0.9, 'none'),
('demo-conflict-001', 'RULE-DOC-002', 'pass', '{"found":"AACCS1234K"}', 'PAN present in parsed document', 0.9, 'none'),
('demo-conflict-001', 'RULE-DOC-003', 'pass', '{"found":"Itemized price breakup table detected"}', 'table:PRICE_BREAKUP present in parsed document', 0.9, 'none'),
('demo-conflict-001', 'RULE-DATE-001', 'pass', '{"found":"valid till 2028-06-30"}', 'CERT_VALIDITY 2028-06-30 is after 2026-06-30', 0.9, 'none'),
('demo-conflict-001', 'RULE-DATE-002', 'pass', '{"found":"Date of Incorporation: 2016-04-01"}', 'INCORPORATION_DATE 2016-04-01 is before 2020-01-01', 0.9, 'none'),
('demo-conflict-001', 'RULE-FIN-001', 'pass', '{"found":"Financial Year 2025-26 turnover of Rs. 1.80 crore"}', 'Extracted 1.8e+07 >= required 1e+07', 0.95, 'none'),
('demo-conflict-001', 'RULE-XCHK-001', 'fail',
 '{"found":"COMPANY_NAME disagrees across 2 document(s): SRI GANESH ELECTRICALS PVT LTD, SRI GANESH ELECTRONICS PVT LTD","source_span":null,"file_id":null,"table_id":null,"distinct_values":["SRI GANESH ELECTRICALS PVT LTD","SRI GANESH ELECTRONICS PVT LTD"],"conflict_records":[{"field":"COMPANY_NAME","status":"conflict","file_id":"demo-file-conflict-fin","doc_role":"financial_bid","value":"Sri Ganesh Electricals Pvt Ltd","normalized_value":"SRI GANESH ELECTRICALS PVT LTD","confidence":0.86},{"field":"COMPANY_NAME","status":"conflict","file_id":"demo-file-conflict-cert","doc_role":"certificates","value":"Sri Ganesh Electronics Pvt Ltd","normalized_value":"SRI GANESH ELECTRONICS PVT LTD","confidence":0.86}],"cross_check_conflict":true}',
 'COMPANY_NAME disagrees across 2 document(s)', 0.86, 'manual_review'),
('demo-conflict-001', 'RULE-XCHK-002', 'pass', '{"found":"PAN consistent across 2 document(s)"}', 'consistent', 0.9, 'none'),
('demo-conflict-001', 'RULE-XCHK-003', 'pass', '{"found":"GSTIN consistent across 2 document(s)"}', 'consistent', 0.9, 'none'),
('demo-conflict-001', 'RULE-XCHK-004', 'pass', '{"found":"CIN consistent across 1 document(s)"}', 'consistent', 0.9, 'none'),
('demo-conflict-001', 'RULE-XCHK-005', 'pass', '{"found":"COMPANY_REGISTRATION_NUMBER consistent across 1 document(s)"}', 'consistent', 0.9, 'none'),
('demo-conflict-001', 'RULE-XCHK-006', 'fail',
 '{"found":"INCORPORATION_DATE disagrees across 2 document(s): 2016-04-01, 2018-11-25","source_span":null,"file_id":null,"table_id":null,"distinct_values":["2016-04-01","2018-11-25"],"conflict_records":[{"field":"INCORPORATION_DATE","status":"conflict","file_id":"demo-file-conflict-fin","doc_role":"financial_bid","value":"2016-04-01","normalized_value":"2016-04-01","confidence":0.9},{"field":"INCORPORATION_DATE","status":"conflict","file_id":"demo-file-conflict-cert","doc_role":"certificates","value":"2018-11-25","normalized_value":"2018-11-25","confidence":0.94}],"cross_check_conflict":true}',
 'INCORPORATION_DATE disagrees across 2 document(s)', 0.9, 'manual_review');

-- Pipeline timelines (per-event idempotency: guard on request_id + stage + message)
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-pass-001', 'demo-pass-001', 'upload', 'done', '2026-09-10T09:30:00+00:00', 0, '4 file(s) accepted'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-pass-001' AND stage='upload' AND message='4 file(s) accepted');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-pass-001', 'demo-pass-001', 'ocr', 'running', '2026-09-10T09:30:00+00:00', 0, 'Extracting text and layout regions'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-pass-001' AND stage='ocr' AND status='running');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-pass-001', 'demo-pass-001', 'ocr', 'done', '2026-09-10T09:30:04+00:00', 4210, '14 page(s), 98 block(s), 6 table(s), 2 region(s)'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-pass-001' AND stage='ocr' AND status='done');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-pass-001', 'demo-pass-001', 'nlp', 'running', '2026-09-10T09:30:04+00:00', 0, 'Structuring sections and extracting entities'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-pass-001' AND stage='nlp' AND status='running');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-pass-001', 'demo-pass-001', 'nlp', 'done', '2026-09-10T09:30:06+00:00', 1820, '4 doc(s), 19 section(s), 47 entit(ies)'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-pass-001' AND stage='nlp' AND status='done');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-pass-001', 'demo-pass-001', 'validation', 'running', '2026-09-10T09:30:06+00:00', 0, 'Evaluating compliance rules'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-pass-001' AND stage='validation' AND status='running');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-pass-001', 'demo-pass-001', 'validation', 'done', '2026-09-10T09:30:06+00:00', 130, '13 rule(s) evaluated -> COMPLIANT'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-pass-001' AND stage='validation' AND message='13 rule(s) evaluated -> COMPLIANT');

INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-fail-001', 'demo-fail-001', 'upload', 'done', '2026-09-11T11:45:00+00:00', 0, '3 file(s) accepted'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-fail-001' AND stage='upload' AND message='3 file(s) accepted');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-fail-001', 'demo-fail-001', 'ocr', 'running', '2026-09-11T11:45:00+00:00', 0, 'Extracting text and layout regions'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-fail-001' AND stage='ocr' AND status='running');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-fail-001', 'demo-fail-001', 'ocr', 'error', '2026-09-11T11:45:02+00:00', 0, 'File demo-file-fail-cert failed (fitz.FileDataError: cannot open broken document)'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-fail-001' AND stage='ocr' AND status='error');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-fail-001', 'demo-fail-001', 'ocr', 'done', '2026-09-11T11:45:03+00:00', 3150, '6 page(s), 41 block(s), 1 table(s), 0 region(s) - 1 corrupt file(s) isolated; remaining 2 doc(s) validated'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-fail-001' AND stage='ocr' AND status='done');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-fail-001', 'demo-fail-001', 'nlp', 'running', '2026-09-11T11:45:03+00:00', 0, 'Structuring sections and extracting entities'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-fail-001' AND stage='nlp' AND status='running');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-fail-001', 'demo-fail-001', 'nlp', 'done', '2026-09-11T11:45:05+00:00', 1420, '2 doc(s), 11 section(s), 26 entit(ies)'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-fail-001' AND stage='nlp' AND status='done');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-fail-001', 'demo-fail-001', 'validation', 'running', '2026-09-11T11:45:05+00:00', 0, 'Evaluating compliance rules'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-fail-001' AND stage='validation' AND status='running');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-fail-001', 'demo-fail-001', 'validation', 'done', '2026-09-11T11:45:05+00:00', 120, '13 rule(s) evaluated -> DISCREPANT'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-fail-001' AND stage='validation' AND message='13 rule(s) evaluated -> DISCREPANT');

INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-conflict-001', 'demo-conflict-001', 'upload', 'done', '2026-09-12T15:20:00+00:00', 0, '2 file(s) accepted'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-conflict-001' AND stage='upload' AND message='2 file(s) accepted');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-conflict-001', 'demo-conflict-001', 'ocr', 'running', '2026-09-12T15:20:00+00:00', 0, 'Extracting text and layout regions'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-conflict-001' AND stage='ocr' AND status='running');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-conflict-001', 'demo-conflict-001', 'ocr', 'done', '2026-09-12T15:20:03+00:00', 3120, '9 page(s), 60 block(s), 2 table(s), 1 region(s)'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-conflict-001' AND stage='ocr' AND status='done');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-conflict-001', 'demo-conflict-001', 'nlp', 'running', '2026-09-12T15:20:03+00:00', 0, 'Structuring sections and extracting entities'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-conflict-001' AND stage='nlp' AND status='running');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-conflict-001', 'demo-conflict-001', 'nlp', 'done', '2026-09-12T15:20:05+00:00', 1540, '2 doc(s), 10 section(s), 31 entit(ies)'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-conflict-001' AND stage='nlp' AND status='done');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-conflict-001', 'demo-conflict-001', 'validation', 'running', '2026-09-12T15:20:05+00:00', 0, 'Evaluating compliance rules'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-conflict-001' AND stage='validation' AND status='running');
INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)
SELECT 'req-demo-conflict-001', 'demo-conflict-001', 'validation', 'done', '2026-09-12T15:20:05+00:00', 140, '13 rule(s) evaluated -> DISCREPANT (cross-check conflict detected)'
WHERE NOT EXISTS (SELECT 1 FROM pipeline_events WHERE request_id='req-demo-conflict-001' AND stage='validation' AND message='13 rule(s) evaluated -> DISCREPANT (cross-check conflict detected)');

INSERT OR REPLACE INTO adjudications (bid_id, decision, officer, comment, ts)
VALUES ('demo-conflict-001', 'rework_requested', 'Review Desk',
        'Company legal name on the Certificate of Incorporation does not match the financial sheet. Please re-submit consistent identity documents.',
        '2026-09-13T10:05:00+00:00');