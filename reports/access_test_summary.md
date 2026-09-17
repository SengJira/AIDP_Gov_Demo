# Access test summary

Run: 2026-09-17 10:56:11
Result: **36/36 tests passed**

| test | user | current_user | roles | object | expected | actual | pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gov-admin-T00-identity | gov-admin | gov-admin | gov_data_admin,public | session | ok | OK (ok) | PASS |
| gov-fraud-T00-identity | gov-fraud | gov-fraud | gov_fraud_analyst,public | session | ok | OK (ok) | PASS |
| gov-biz-T00-identity | gov-biz | gov-biz | gov_business_analyst,public | session | ok | OK (ok) | PASS |
| gov-tha-T00-identity | gov-tha | gov-tha | gov_thailand_analyst,public | session | ok | OK (ok) | PASS |
| gov-audit-T00-identity | gov-audit | gov-audit | gov_auditor,public | session | ok | OK (ok) | PASS |
| gov-admin-T01-all-rows | gov-admin | gov-admin | gov_data_admin,public | customer_transactions | ok | OK (all 36 rows visible) | PASS |
| gov-admin-T02-all-countries | gov-admin | gov-admin | gov_data_admin,public | customer_transactions | ok | OK (all 4 countries) | PASS |
| gov-admin-T03-unmasked | gov-admin | gov-admin | gov_data_admin,public | customer_transactions | ok | OK (name+id unmasked) | PASS |
| gov-admin-T04-fraud-fields | gov-admin | gov-admin | gov_data_admin,public | customer_transactions | ok | OK (fraud fields readable) | PASS |
| gov-admin-T05-show-roles | gov-admin | gov-admin | gov_data_admin,public | metadata | ok | OK (roles visible) | PASS |
| gov-fraud-T01-filter | gov-fraud | gov-fraud | gov_fraud_analyst,public | customer_transactions | ok | OK (only 14 fraud/high-risk rows) | PASS |
| gov-fraud-T02-no-low-risk | gov-fraud | gov-fraud | gov_fraud_analyst,public | customer_transactions | ok | OK (every row fraud_flag or risk>=0.70) | PASS |
| gov-fraud-T03-nid-masked | gov-fraud | gov-fraud | gov_fraud_analyst,public | customer_transactions | ok | OK (national_id strongly masked) | PASS |
| gov-fraud-T04-pii-partial | gov-fraud | gov-fraud | gov_fraud_analyst,public | customer_transactions | ok | OK (name/nid/mobile/email partially masked) | PASS |
| gov-fraud-T05-write-denied | gov-fraud | gov-fraud | gov_fraud_analyst,public | customer_transactions | denied | DENIED (TrinoUserError(type=USER_ERROR, name=PERMISSION_DENIED, message="Access  | PASS |
| gov-fraud-T06-ctas-denied | gov-fraud | gov-fraud | gov_fraud_analyst,public | customer_transactions | denied | DENIED (TrinoUserError(type=USER_ERROR, name=PERMISSION_DENIED, message="Access  | PASS |
| gov-fraud-T07-role-mgmt-denied | gov-fraud | gov-fraud | gov_fraud_analyst,public | roles | denied | DENIED (TrinoUserError(type=USER_ERROR, name=PERMISSION_DENIED, message="Access  | PASS |
| gov-fraud-T08-view-denied | gov-fraud | gov-fraud | gov_fraud_analyst,public | customer_transactions | denied | DENIED (TrinoUserError(type=USER_ERROR, name=PERMISSION_DENIED, message="Access  | PASS |
| gov-biz-T01-summary-ok | gov-biz | gov-biz | gov_business_analyst,public | payment_business_summary | ok | OK (summary accessible) | PASS |
| gov-biz-T02-no-pii-cols | gov-biz | gov-biz | gov_business_analyst,public | payment_business_summary | ok | OK (no PII/investigation columns in summary) | PASS |
| gov-biz-T03-table-denied | gov-biz | gov-biz | gov_business_analyst,public | customer_transactions | denied | DENIED (TrinoUserError(type=USER_ERROR, name=PERMISSION_DENIED, message="Access  | PASS |
| gov-biz-T04-nid-denied | gov-biz | gov-biz | gov_business_analyst,public | customer_transactions | denied | DENIED (TrinoUserError(type=USER_ERROR, name=PERMISSION_DENIED, message="Access  | PASS |
| gov-biz-T05-fraud-denied | gov-biz | gov-biz | gov_business_analyst,public | customer_transactions | denied | DENIED (TrinoUserError(type=USER_ERROR, name=PERMISSION_DENIED, message="Access  | PASS |
| gov-tha-T01-th-only | gov-tha | gov-tha | gov_thailand_analyst,public | customer_transactions | ok | OK (every row is TH) | PASS |
| gov-tha-T02-other-country | gov-tha | gov-tha | gov_thailand_analyst,public | customer_transactions | ok | OK (VN query returns 0) | PASS |
| gov-tha-T03-no-predicate | gov-tha | gov-tha | gov_thailand_analyst,public | customer_transactions | ok | OK (only 1 country without predicate) | PASS |
| gov-tha-T04-subquery | gov-tha | gov-tha | gov_thailand_analyst,public | customer_transactions | ok | OK (subquery still TH-only) | PASS |
| gov-tha-T05-union | gov-tha | gov-tha | gov_thailand_analyst,public | customer_transactions | ok | OK (UNION still TH-only) | PASS |
| gov-tha-T06-join | gov-tha | gov-tha | gov_thailand_analyst,public | customer_transactions | ok | OK (self-join stays TH-only) | PASS |
| gov-tha-T07-pii-masked | gov-tha | gov-tha | gov_thailand_analyst,public | customer_transactions | ok | OK (all PII + account masked) | PASS |
| gov-tha-T08-write-denied | gov-tha | gov-tha | gov_thailand_analyst,public | customer_transactions | denied | DENIED (TrinoUserError(type=USER_ERROR, name=PERMISSION_DENIED, message="Access  | PASS |
| gov-audit-T01-show-tables | gov-audit | gov-audit | gov_auditor,public | customer_transactions | ok | OK (object metadata visible) | PASS |
| gov-audit-T02-select-denied | gov-audit | gov-audit | gov_auditor,public | customer_transactions | denied | DENIED (TrinoUserError(type=USER_ERROR, name=PERMISSION_DENIED, message="Access  | PASS |
| gov-audit-T03-pii-denied | gov-audit | gov-audit | gov_auditor,public | customer_transactions | denied | DENIED (TrinoUserError(type=USER_ERROR, name=PERMISSION_DENIED, message="Access  | PASS |
| gov-audit-T04-write-denied | gov-audit | gov-audit | gov_auditor,public | customer_transactions | denied | DENIED (TrinoUserError(type=USER_ERROR, name=PERMISSION_DENIED, message="Access  | PASS |
| gov-audit-T05-roles-visible | gov-audit | gov-audit | gov_auditor,public | metadata | ok | OK (roles listable) | PASS |