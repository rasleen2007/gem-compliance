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