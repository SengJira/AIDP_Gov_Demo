-- Phase 5: least-privilege grants (SQL form, documented equivalent).
-- scripts/configure_rbac.py applies these through the BIAC REST API so
-- that masks/filters and non-TABLES categories are handled uniformly and
-- idempotently. Privileges go to ROLES only (BIAC does not support direct
-- grants to users/groups via SQL).

-- gov_data_admin: full control inside gov_demo + policy/audit visibility
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, SHOW
    ON SCHEMA js_financial_ice.gov_demo TO ROLE gov_data_admin;
-- ROLES / AUDIT_LOGS / expression categories are BIAC-only entities and
-- have no SQL GRANT form -> applied via REST API by configure_rbac.py.

-- gov_fraud_analyst: read-only on demo objects
GRANT SELECT, SHOW ON TABLE js_financial_ice.gov_demo.customer_transactions
    TO ROLE gov_fraud_analyst;
GRANT SELECT, SHOW ON TABLE js_financial_ice.gov_demo.payment_business_summary
    TO ROLE gov_fraud_analyst;

-- gov_business_analyst: aggregated view only (no grant on the source table)
GRANT SELECT, SHOW ON TABLE js_financial_ice.gov_demo.payment_business_summary
    TO ROLE gov_business_analyst;

-- gov_thailand_analyst: read-only on demo objects
GRANT SELECT, SHOW ON TABLE js_financial_ice.gov_demo.customer_transactions
    TO ROLE gov_thailand_analyst;
GRANT SELECT, SHOW ON TABLE js_financial_ice.gov_demo.payment_business_summary
    TO ROLE gov_thailand_analyst;

-- gov_auditor: SHOW only (metadata), no SELECT on business data
GRANT SHOW ON SCHEMA js_financial_ice.gov_demo TO ROLE gov_auditor;

-- Role -> identity mapping (Keycloak groups) is applied through the BIAC
-- REST API subject-assignments endpoints; SQL form (not used by scripts):
--   GRANT gov_data_admin TO USER "gov-admin";          -- per-user fallback
--   GRANT gov_fraud_analyst TO USER "gov-fraud";
