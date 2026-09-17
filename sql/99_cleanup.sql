-- Rollback: remove all demo objects. scripts/reset_demo.py performs the
-- equivalent (plus BIAC objects: masks, filters, grants, roles,
-- assignments) with dry-run default.
DROP VIEW IF EXISTS js_financial_ice.gov_demo.payment_business_summary;
DROP TABLE IF EXISTS js_financial_ice.gov_demo.customer_transactions;
DROP SCHEMA IF EXISTS js_financial_ice.gov_demo;
DROP ROLE IF EXISTS gov_data_admin;
DROP ROLE IF EXISTS gov_fraud_analyst;
DROP ROLE IF EXISTS gov_business_analyst;
DROP ROLE IF EXISTS gov_thailand_analyst;
DROP ROLE IF EXISTS gov_auditor;
