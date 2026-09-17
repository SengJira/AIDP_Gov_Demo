# Audit evidence summary (sanitized)

Source: SEP BIAC REST API `/audit/accessLogs`, `/audit/changeLogs`.
Events filtered to demo identities/objects. Query text and
credentials are never present in these APIs.

## Access decisions by user

| user | ALLOW | DENY |
| --- | --- | --- |
| dv-admin | 62 | 0 |
| gov-admin | 58 | 0 |
| gov-audit | 48 | 8 |
| gov-biz | 48 | 8 |
| gov-fraud | 87 | 94 |
| gov-tha | 90 | 133 |
| jirawut | 21 | 2 |

## Denied operations (sample)

| time | user | action | entity |
| --- | --- | --- | --- |
| 2026-09-17T15:45:35.454705Z | gov-audit | INSERT | js_financial_ice.gov_demo.customer_transactions.* |
| 2026-09-17T15:45:35.275140Z | gov-audit | SELECT | js_financial_ice.gov_demo.customer_transactions.national_id |
| 2026-09-17T15:45:35.103606Z | gov-audit | SELECT | js_financial_ice.gov_demo.customer_transactions.* |
| 2026-09-17T15:45:34.745270Z | gov-tha | DELETE | js_financial_ice.gov_demo.customer_transactions.* |
| 2026-09-17T15:45:34.549927Z | gov-tha | (ANY) | js_financial_ice.gov_demo.customer_transactions.* |
| 2026-09-17T15:45:34.546847Z | gov-tha | (ANY) | js_financial_ice.gov_demo.customer_transactions.account_id |
| 2026-09-17T15:45:34.546840Z | gov-tha | (ANY) | js_financial_ice.gov_demo.customer_transactions.email |
| 2026-09-17T15:45:34.546833Z | gov-tha | (ANY) | js_financial_ice.gov_demo.customer_transactions.mobile_number |
| 2026-09-17T15:45:34.546823Z | gov-tha | (ANY) | js_financial_ice.gov_demo.customer_transactions.national_id |
| 2026-09-17T15:45:34.546800Z | gov-tha | (ANY) | js_financial_ice.gov_demo.customer_transactions.customer_name |
| 2026-09-17T15:45:34.329754Z | gov-tha | (ANY) | js_financial_ice.gov_demo.customer_transactions.* |
| 2026-09-17T15:45:34.326679Z | gov-tha | (ANY) | js_financial_ice.gov_demo.customer_transactions.account_id |
| 2026-09-17T15:45:34.326672Z | gov-tha | (ANY) | js_financial_ice.gov_demo.customer_transactions.email |
| 2026-09-17T15:45:34.326665Z | gov-tha | (ANY) | js_financial_ice.gov_demo.customer_transactions.mobile_number |
| 2026-09-17T15:45:34.326656Z | gov-tha | (ANY) | js_financial_ice.gov_demo.customer_transactions.national_id |

## Policy changes (sample)

| time | operation | kind | entity | role |
| --- | --- | --- | --- | --- |
| 2026-09-17T15:43:54.643102Z | Create | Row filter | js_financial_ice.gov_demo.payment_business_summary | gov_thailand_analyst |
| 2026-09-17T15:43:54.599887Z | Create | Row filter | js_financial_ice.gov_demo.customer_transactions | gov_thailand_analyst |
| 2026-09-17T15:43:54.564433Z | Create | Row filter | js_financial_ice.gov_demo.customer_transactions | gov_fraud_analyst |
| 2026-09-17T15:43:54.528953Z | Create | Row filter expression | transaction_status = 'APPROVED' |  |
| 2026-09-17T15:43:54.494204Z | Create | Row filter expression | country_code = 'TH' |  |
| 2026-09-17T15:43:54.460031Z | Create | Row filter expression | COALESCE(fraud_flag, false) OR COALESCE(risk_sc... |  |
| 2026-09-17T15:43:54.049592Z | Delete | Row filter expression | transaction_status IS DISTINCT FROM 'APPROVED' |  |
| 2026-09-17T15:43:54.014113Z | Delete | Row filter expression | NOT (COALESCE(fraud_flag, false) OR COALESCE(ri... |  |
| 2026-09-17T15:43:53.979602Z | Delete | Row filter expression | country_code IS DISTINCT FROM 'TH' |  |
| 2026-09-17T15:43:53.910472Z | Delete | Row filter | js_financial_ice.gov_demo.customer_transactions | gov_thailand_analyst |
| 2026-09-17T15:43:53.875023Z | Delete | Row filter | js_financial_ice.gov_demo.payment_business_summary | gov_thailand_analyst |
| 2026-09-17T15:43:53.807810Z | Delete | Row filter | js_financial_ice.gov_demo.customer_transactions | gov_fraud_analyst |
| 2026-09-17T15:43:12.806686Z | Create | Column mask | js_financial_ice.gov_demo.customer_transactions... | gov_thailand_analyst |
| 2026-09-17T15:43:12.772550Z | Create | Column mask | js_financial_ice.gov_demo.customer_transactions... | gov_thailand_analyst |
| 2026-09-17T15:43:12.736802Z | Create | Column mask | js_financial_ice.gov_demo.customer_transactions... | gov_thailand_analyst |