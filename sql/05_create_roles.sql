-- Phase 3/5: BIAC roles for the governance personas.
-- CREATE ROLE is supported via SQL in SEP built-in access control.
-- scripts/configure_rbac.py performs the equivalent through the BIAC REST
-- API (idempotent) - this file documents the SQL form.
-- Run as a session with SET ROLE sysadmin.
CREATE ROLE IF NOT EXISTS gov_data_admin;
CREATE ROLE IF NOT EXISTS gov_fraud_analyst;
CREATE ROLE IF NOT EXISTS gov_business_analyst;
CREATE ROLE IF NOT EXISTS gov_thailand_analyst;
CREATE ROLE IF NOT EXISTS gov_auditor;
