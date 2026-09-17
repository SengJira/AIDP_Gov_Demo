-- Phase 2: synthetic governed dataset (one row per transaction).
-- Combines customer identity attributes with payment detail so a single
-- table can demonstrate column masking and row filtering end to end.
-- ALL VALUES ARE SYNTHETIC. The original banking tables are never modified.
CREATE TABLE IF NOT EXISTS js_financial_ice.gov_demo.customer_transactions (
    customer_id          varchar,
    customer_name        varchar,
    national_id          varchar,
    mobile_number        varchar,
    email                varchar,
    account_id           varchar,
    transaction_id       varchar,
    event_timestamp      timestamp(6) with time zone,
    amount               double,
    currency             varchar,
    channel              varchar,
    merchant_category    varchar,
    transaction_status   varchar,
    country_code         varchar,
    city                 varchar,
    risk_score           double,
    fraud_flag           boolean,
    fraud_type           varchar,
    investigation_status varchar
);
