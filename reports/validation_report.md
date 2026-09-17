# Validation report

Run: 2026-09-17 10:46:15
Result: **19/19 checks passed**

| check | name | result | detail |
| --- | --- | --- | --- |
| C01-synthetic | demo data is synthetic | PASS | 36 synthetic rows in gov_demo.customer_transactions |
| C02-originals | original datasets intact | PASS | payment_transactions=2687202, customers=10000 (readable, unmodified) |
| C03-roles | gov roles exist | PASS | roles present: ['gov_auditor', 'gov_business_analyst', 'gov_data_admin', 'gov_fraud_analyst', 'gov_thailand_analyst'] |
| C03b-mapping | identity->role mapping | PASS | all 5 users resolve to their role  |
| C04-admin-unmasked | admin sees unmasked data | PASS | no mask chars in admin result |
| C05-fraud-filter | fraud analyst sees only fraud/high-risk | PASS | 0 low-risk rows visible |
| C06-fraud-mask | fraud analyst PII partially masked | PASS | national_id masked |
| C07-biz-summary | business analyst gets aggregates | PASS | summary view readable |
| C08-biz-denied | business analyst denied source table | PASS | denied |
| C09-tha-only | thailand analyst sees TH only | PASS | 0 non-TH rows |
| C10-tha-bypass | row filter not bypassable | PASS | subquery/join/UNION all still TH-only |
| C11-auditor | auditor cannot read PII | PASS | denied |
| C12-writes | unauthorized writes denied | PASS | insert denied for all 4 non-admin personas |
| C13-openmetadata | OpenMetadata enriched | PASS | domain=['FraudAndRisk'] owner=['Fraud and Risk Team'] table_tags=5 col_tags=True |
| C14-audit | audit evidence has allow+deny | PASS | 915 demo events (allow=518 deny=397) |
| C15-real-identities | tests ran as real identities | PASS | access_test_results.csv contains per-identity current_user |
| C16-idempotent | re-run produces no duplicates | PASS | pending changes: none |
| C17-sanitized | no secrets/PII in reports | PASS | clean (no secrets/PII found) |
| C18-rollback | rollback documented | PASS | 8 rollback files + reset_demo.py + 99_cleanup.sql |