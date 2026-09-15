-- Seed rule pack (contract 4) for the demo tender GeM/2026/B/123456.
-- Categories mirror the MVP compliance dashboard: EMD, Eligibility, Technical,
-- Financial, Certificates. Adjust expected_value per actual tender.

INSERT INTO validation_rules
    (rule_id, tender_id, category, description, severity, element, target, operator, expected_value, notes) VALUES
-- EMD
('RULE-EMD-001', 'GeM/2026/B/123456', 'EMD',
 'EMD percentage must be >= 2% of quoted value via BG/DD', 'blocking', 'all',
 'EMD_PERCENTAGE', '>=', '2', 'Auto-extract from EMD/financial sections'),
('RULE-EMD-002', 'GeM/2026/B/123456', 'EMD',
 'EMD instrument (Bank Guarantee / Demand Draft) must be present', 'blocking', 'emd',
 'BANK_GUARANTEE_PRESENT', 'exists', NULL, 'Check stamp/signature + instrument wording'),
('RULE-EMD-003', 'GeM/2026/B/123456', 'EMD',
 'EMD validity must extend 45 days past bid validity', 'mandatory', 'emd',
 'EMD_VALIDITY_DATE', 'date_after', '2026-08-30', 'Compare against tender default validity'),

-- Eligibility
('RULE-ELIG-001', 'GeM/2026/B/123456', 'Eligibility',
 'Supplier must hold valid GSTIN', 'blocking', 'certificates', 'kv.GSTIN', 'regex',
 '^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$', 'GSTIN format check'),

-- Technical
('RULE-TECH-001', 'GeM/2026/B/123456', 'Technical',
 'Technical bid must quote delivery period within 60 days', 'mandatory', 'technical_bid',
 'DELIVERY_PERIOD_DAYS', '<=', '60', 'Extract from price/delivery schedule table'),
('RULE-TECH-002', 'GeM/2026/B/123456', 'Technical',
 'Product must meet IS/ISO spec reference (e.g., IS 1234:2020)', 'advisory', 'technical_bid',
 'word("IS/ISO")', 'regex', 'IS\\s*\\d{3,5}[:\\s]\\d{4}', 'Spec citation present'),

-- Financial
('RULE-FIN-001', 'GeM/2026/B/123456', 'Financial',
 'Financial bid must contain itemised price breakup table', 'blocking', 'financial_bid',
 'table("PRICE_BREAKUP")', 'exists', NULL, 'Detect >2-column table in financial bid'),
('RULE-FIN-002', 'GeM/2026/B/123456', 'Financial',
 'Prices must be quoted inclusive of applicable duties (quote basis)', 'mandatory', 'financial_bid',
 'word("inclusive")', 'contains', 'incl', 'Match duty-inclusive phrasing'),

-- Certificates
('RULE-CERT-001', 'GeM/2026/B/123456', 'Certificates',
 'ISO 9001 certificate must be attached and within validity', 'mandatory', 'certificates',
 'CERT_DATE', 'date_after', '2026-01-01', 'Certificate expiry within last 9 months'),
('RULE-CERT-002', 'GeM/2026/B/123456', 'Certificates',
 'Bidder declaration / No-Conflict form attached', 'advisory', 'certificates',
 'word("declaration")', 'exists', NULL, 'Annexure scan');