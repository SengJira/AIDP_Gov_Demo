# 15-minute demo script

**Protecting Customer and Payment Data with AIDP Governance**

Prep: run the [presenter checklist](presenter_checklist.md) first.
Terminal tip: keep six shell profiles or tmux panes ready, one per
identity. All SQL below is in `sql/09_validation_queries.sql`.

The demo query used throughout:

```sql
SELECT customer_name, national_id, mobile_number, email, account_id,
       country_code, risk_score, fraud_flag, fraud_type
FROM js_financial_ice.gov_demo.customer_transactions
ORDER BY transaction_id;
```

---

## Scene 1 - Governance context (2 min) - OpenMetadata

Open `http://10.246.25.115:8585` -> `js_aidp_starburst` ->
`js_financial_ice` -> `gov_demo` -> `customer_transactions`.

Show: business description, `FraudAndRisk` domain, owner `Fraud and Risk
Team`, column tags (`Sensitivity.PII`, `HighlySensitivePII`,
`FinancialData`, `Restricted`), table tag `Governance.Governed`, and
`payment_business_summary` tagged `DataLayer.DataProduct`.

> "OpenMetadata tells users what the data means, who owns it, and which
> fields are sensitive. AIDP enforces who can access the data and what
> they are allowed to see. Tags document; BIAC enforces."

## Scene 2 - Governance administrator (2 min) - `gov-admin`

```sql
SELECT current_user;           -- gov-admin
SHOW CURRENT ROLES;            -- gov_data_admin
```

Run the demo query -> **all 36 rows, fully unmasked** (`Somchai Prasert`,
`1234567890123`, `0812345678`, real-looking synthetic emails/accounts).

> "The governance administrator has explicitly authorized access for
> policy verification and investigation."

## Scene 3 - Fraud analyst (3 min) - `gov-fraud`

```sql
SELECT current_user;           -- gov-fraud
SHOW CURRENT ROLES;            -- gov_fraud_analyst
```

Same demo query -> **14 rows only** (every row `fraud_flag` or
`risk_score >= 0.70`), names like `Somchai P******`, national ID
`*********0123`, mobile `******5678`, email `j******@example.com`,
full `account_id` and fraud fields for investigation.

Then the denied write:

```sql
INSERT INTO js_financial_ice.gov_demo.customer_transactions (customer_id)
VALUES ('HACK');               -- Access Denied
```

> "The fraud analyst gets everything needed for the investigation - row
> scope and full fraud attributes - while unnecessary personal details
> stay protected."

## Scene 4 - Business analyst (2 min) - `gov-biz`

```sql
SHOW CURRENT ROLES;            -- gov_business_analyst
SELECT * FROM js_financial_ice.gov_demo.payment_business_summary
ORDER BY country_code, event_date;
```

Aggregated metrics by country/date/channel/category - **no PII columns
exist in this view**. Then:

```sql
SELECT count(*) FROM js_financial_ice.gov_demo.customer_transactions;
                               -- Access Denied
```

> "The business analyst answers business questions without ever touching
> personal data."

## Scene 5 - Regional analyst (3 min) - `gov-tha`

```sql
SHOW CURRENT ROLES;            -- gov_thailand_analyst
```

Run the demo query **with no WHERE clause** -> only the 12 `TH` rows, all
PII strongly masked (`Protected Customer`, `*************`, masked
mobile/email, account `************1234`).

Bypass attempts, each returning 0 rows or staying TH-only:

```sql
SELECT count(*) FROM js_financial_ice.gov_demo.customer_transactions
WHERE country_code = 'VN';                       -- 0
SELECT count(*) FROM (SELECT * FROM js_financial_ice.gov_demo.customer_transactions) x
WHERE country_code = 'SG';                       -- 0
```

> "Row-level policy follows the user's authorization - it cannot be
> bypassed by changing the query filter, wrapping in a subquery, or
> unioning."

## Scene 6 - Audit evidence (3 min)

```bash
python scripts/collect_audit_evidence.py
```

Show `reports/audit_evidence_summary.md`: ALLOW/DENY counts per demo
user, denied `SELECT`/`INSERT` events, and the change log entries for
role/mask/filter creation. Optionally open the SEP UI *Access control ->
Audit log* for the same events.

> "AIDP provides enforcement; the audit log supports investigation and
> regulatory accountability - every allowed and denied access is recorded
> with user, roles, action and target object."

## Close (1 min)

One query, five identities, five different governed results - native
engine enforcement, no application-code shortcuts, everything auditable
and reversible (`scripts/reset_demo.py`).
