-- Phase 9: validation queries (run per identity by test_role_access.py).
-- Identity proof - every session begins with:
SELECT current_user;
SELECT current_role;
SHOW CURRENT ROLES;

-- The canonical "same query, different result" demo query:
SELECT customer_id, customer_name, national_id, mobile_number, email,
       account_id, transaction_id, amount, currency, channel,
       transaction_status, country_code, risk_score, fraud_flag,
       fraud_type, investigation_status
FROM js_financial_ice.gov_demo.customer_transactions
ORDER BY transaction_id;

-- Aggregate surface for the business analyst:
SELECT * FROM js_financial_ice.gov_demo.payment_business_summary
ORDER BY country_code, event_date, channel;

-- Row-filter bypass attempts (must all still obey the filter):
SELECT count(*) AS total FROM js_financial_ice.gov_demo.customer_transactions;
SELECT count(*) AS vn_rows FROM js_financial_ice.gov_demo.customer_transactions
    WHERE country_code = 'VN';
SELECT count(*) AS via_subquery FROM (
    SELECT * FROM js_financial_ice.gov_demo.customer_transactions
) t;
SELECT count(*) AS via_union FROM (
    SELECT transaction_id, country_code FROM js_financial_ice.gov_demo.customer_transactions
    UNION ALL
    SELECT transaction_id, country_code FROM js_financial_ice.gov_demo.customer_transactions
) u;

-- Write attempt (must be denied for analyst roles):
-- INSERT INTO js_financial_ice.gov_demo.customer_transactions
--     (customer_id, transaction_id) VALUES ('X','X');
