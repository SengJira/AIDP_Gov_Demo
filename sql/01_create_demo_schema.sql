-- Phase 2: dedicated schema for the governance showcase.
-- Executed by scripts/setup_demo_data.py as dv-admin with SET ROLE sysadmin.
-- Existing schemas/roles/grants are not touched.
-- Iceberg requires an explicit schema location in this catalog; the same
-- warehouse prefix convention as banking/ is used.
CREATE SCHEMA IF NOT EXISTS js_financial_ice.gov_demo
WITH (location = 's3://js-demo/warehouse/gov_demo');
