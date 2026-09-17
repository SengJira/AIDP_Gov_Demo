-- Phase 2: aggregated business metrics view (no personal information).
-- SECURITY DEFINER so business analysts can read aggregates without any
-- privilege on the underlying protected table. This is a curated-view
-- pattern, documented as such - it is NOT presented as native masking or
-- filtering (those are enforced by BIAC row filters / column masks).
CREATE OR REPLACE VIEW js_financial_ice.gov_demo.payment_business_summary
SECURITY DEFINER AS
SELECT
    country_code,
    CAST(event_timestamp AS date)        AS event_date,
    channel,
    merchant_category,
    COUNT(*)                             AS transaction_count,
    SUM(amount)                          AS total_amount,
    AVG(amount)                          AS avg_amount,
    SUM(CASE WHEN transaction_status = 'APPROVED' THEN 1 ELSE 0 END) AS approved_count,
    SUM(CASE WHEN transaction_status = 'DECLINED' THEN 1 ELSE 0 END) AS declined_count,
    SUM(CASE WHEN fraud_flag THEN 1 ELSE 0 END)                      AS fraud_alert_count,
    AVG(risk_score)                      AS avg_risk_score
FROM js_financial_ice.gov_demo.customer_transactions
GROUP BY country_code, CAST(event_timestamp AS date), channel, merchant_category;
