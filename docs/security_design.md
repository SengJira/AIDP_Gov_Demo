# Security design

All controls below are **native SEP BIAC** - verified by connecting as each
real identity. Nothing is simulated in application code.

## Roles and least-privilege grants

| Object / privilege | gov_data_admin | gov_fraud_analyst | gov_business_analyst | gov_thailand_analyst | gov_auditor |
| --- | --- | --- | --- | --- | --- |
| `gov_demo` schema usage | Yes | Yes | Yes | Yes | metadata only |
| `customer_transactions` SELECT | Full | Filtered + masked | **Denied** | TH rows + masked | **Denied** |
| `payment_business_summary` SELECT | Yes | Yes | Yes | TH rows only | metadata only |
| Unmasked `national_id` | Yes | No | No | No | No |
| Full `mobile_number` / `email` | Yes | No | No | No | No |
| Fraud fields (`fraud_type`, `investigation_status`) | Yes | Yes | n/a (no table) | visible on TH rows | No |
| Write / DDL on `gov_demo` | (admin persona; verified for setup only) | Denied | Denied | Denied | Denied |
| Policy management (roles/masks/filters) | via admin path | Denied | Denied | Denied | Denied |

Deny is implemented as **absence of grant** - no `DENY` effects are needed.

## Group -> role assignments (BIAC)

| Keycloak group | BIAC role | Demo user |
| --- | --- | --- |
| `governance-admins` | `gov_data_admin` | `gov-admin` |
| `fraud-analysts` | `gov_fraud_analyst` | `gov-fraud` |
| `business-analysts` | `gov_business_analyst` | `gov-biz` |
| `thailand-analysts` | `gov_thailand_analyst` | `gov-tha` |
| `data-auditors` | `gov_auditor` | `gov-audit` |

### Removed scaffolding (documented, reversible)

Before the demo, every demo group also held `jirawut_demo` and
`pystarburst`, which grant broad SELECT/write across `js_financial_ice`
and `js_mysql_customer360`. Those assignments would have defeated
least-privilege for the demo personas, so `configure_rbac.py` removes
them from the five demo groups only, and records them in the rollback
file. `reset_demo.py --restore-scaffolding` puts them back.

## Column masks (query-time, BIAC)

Applied to `js_financial_ice.gov_demo.customer_transactions`:

| Column | gov_data_admin | gov_fraud_analyst | gov_thailand_analyst | expression approach |
| --- | --- | --- | --- | --- |
| `customer_name` | `Somchai Prasert` | `Somchai P******` | `Protected Customer` | first token + first initial of last token |
| `national_id` | `1234567890123` | `*********0123` | `*************` | last-4 vs full `array_join(repeat('*',length(...)),'')` |
| `mobile_number` | `0812345678` | `******5678` | `**********` | last-4 vs full mask |
| `email` | `jirawut@example.com` | `j******@example.com` | `hidden@example.com` | first char + `******` + domain; NULL-safe |
| `account_id` | `ACC-TH-00001234` | `ACC-TH-00001234` | `************1234` | last-4 mask for regional |

Edge cases handled and verified: NULLs (stay NULL), short strings, emails
without `@`, single-token names, values shorter than the visible suffix.
Expressions were validated in SQL before upload - Trino's `repeat()`
returns an array, so masks use `array_join(repeat('*', n), '')`.

## Row filters (BIAC, exclusion semantics)

BIAC row filters **exclude rows where the expression is TRUE**, so
visibility rules are written inverted:

| Filter | Attached to | Expression (excludes...) | Visible result |
| --- | --- | --- | --- |
| `gov_demo_fraud_only` | `customer_transactions` -> `gov_fraud_analyst` | `NOT (fraud_flag OR risk_score >= 0.70)` | 14 fraud/high-risk rows |
| `gov_demo_thailand_only` | `customer_transactions` -> `gov_thailand_analyst` | `country_code <> 'TH'` | 12 TH rows |
| `gov_demo_thailand_only` | `payment_business_summary` -> `gov_thailand_analyst` | `country_code <> 'TH'` | TH aggregate rows only |
| `gov_demo_approved_only` | (defined, unattached) | `transaction_status <> 'APPROVED'` | ready if biz detail access is ever needed |

Business analyst gets **no grant** on the raw table - aggregate view only,
which is stricter and simpler than a filtered detail grant.

## Bypass resistance (verified as `gov-tha` / `gov-fraud`)

- `WHERE country_code='VN'` -> 0 rows
- Subquery `FROM (SELECT * FROM t)` -> still TH-only / fraud-only
- `UNION ALL` of the table with itself -> still filtered
- Self-JOIN -> still filtered
- `CREATE VIEW`/`CREATE TABLE AS` on the table -> denied (no CREATE grant)
- `INSERT`/`DELETE`/`UPDATE` -> denied
- Reading via `payment_business_summary` -> the TH filter follows the role

## `SECURITY DEFINER` view caveat (verified)

SEP 479-e.4 evaluates `SECURITY DEFINER` views against the definer's
grants **and requires the owner to hold the underlying privilege WITH
GRANT OPTION**. The summary view is owned by `jirawut` (the
data-engineering identity), and `jirawut_demo` was given
`ALLOW ... SELECT ... WITH GRANT OPTION` on `gov_demo.*`. Without the
grant option, other users get `View owner does not have sufficient
privileges`. This is a BIAC quirk documented for the runbook.

## Audit

BIAC records every access decision (`/audit/accessLogs`: user, enabled
roles, action, entity, ALLOW/DENY) and every policy change
(`/audit/changeLogs`). `collect_audit_evidence.py` filters these to
demo-relevant events and writes sanitized CSVs - query text and
credentials never appear in the API output.
