# Completion report - AIDP Data Governance Showcase

**Protecting Customer and Payment Data with AIDP Governance**

Date: 2026-09-17. All results verified with real identities - nothing is
simulated in application code.

## Confirmed AIDP access-control capabilities

Platform: Starburst Enterprise **479-e.4** behind `https://ddae.lab9bgp.com`,
using **Built-In Access Control (BIAC)** - confirmed native, not Ranger or
file-based.

| Capability | Mechanism | Status |
| --- | --- | --- |
| Roles | BIAC role + grant entities | Confirmed native |
| Group->role mapping | BIAC group-subject assignments (Keycloak groups resolved at login) | Confirmed native |
| Catalog/schema/table/column grants | `ALLOW`/`DENY`/`ALLOW_WITH_GRANT_OPTION` effects | Confirmed native |
| Column masking | BIAC mask expressions (`"@column"`), query-time | Confirmed native |
| Row filtering | BIAC row-filter expressions - **exclusion predicates** | Confirmed native |
| Access audit | `/api/v1/biac/audit/accessLogs` (allow/deny per user/role/entity) | Confirmed native |
| Change audit | `/api/v1/biac/audit/changeLogs` | Confirmed native |
| SQL DDL for masks/filters | not available - REST API or SEP UI only | Verified limitation |
| `SECURITY DEFINER` views | supported; owner needs privilege **WITH GRANT OPTION** | Verified (fallback usable, not needed) |

Admin path: `dv-admin` holds `sysadmin` (admin option, off by default) -
`SET ROLE sysadmin` in SQL, `X-Trino-Role: system=ROLE{sysadmin}` for REST.
Kubernetes/appliance access was **not** used, per instruction; everything
went through the AIDP API + Keycloak admin API + OpenMetadata API.

## Governance architecture

Keycloak users -> Keycloak groups -> BIAC group assignments -> roles ->
grants (deny-by-absence) + column masks (query-time) + row filters
(pre-scan exclusion). Enforcement is entirely in the SEP engine;
OpenMetadata documents domain/owner/tags but does not enforce.

See [docs/architecture.md](../docs/architecture.md) and
[docs/security_design.md](../docs/security_design.md).

## Roles and identity mappings

| Keycloak user | Keycloak group | BIAC role | Verified `SHOW CURRENT ROLES` |
| --- | --- | --- | --- |
| `gov-admin` | `governance-admins` | `gov_data_admin` | yes |
| `gov-fraud` | `fraud-analysts` | `gov_fraud_analyst` | yes |
| `gov-biz` | `business-analysts` | `gov_business_analyst` | yes |
| `gov-tha` | `thailand-analysts` | `gov_thailand_analyst` | yes |
| `gov-audit` | `data-auditors` | `gov_auditor` | yes |

Documented change: the broad pre-existing `jirawut_demo`/`pystarburst`
group assignments were removed from the five demo groups (they granted
catalog-wide SELECT and would have defeated least privilege). Reversible
via `reset_demo.py --restore-scaffolding`; recorded in rollback files.

## Grants applied (least-privilege, deny by absence)

- `gov_data_admin`: catalog access + `SHOW`/`SELECT` on
  `js_financial_ice.gov_demo` (schema + both objects).
- `gov_fraud_analyst`: same SELECT scope; row filter + column masks
  narrow visibility.
- `gov_business_analyst`: SELECT on `payment_business_summary` only.
- `gov_thailand_analyst`: SELECT on both objects; TH row filter + strong
  masks.
- `gov_auditor`: schema `SHOW` only (metadata), no SELECT.
- `jirawut_demo`: `ALLOW_WITH_GRANT_OPTION` SELECT on `gov_demo.*` -
  required for the `SECURITY DEFINER` summary view owned by `jirawut`.

## Masking policies (BIAC column masks, query-time)

On `customer_transactions` - all NULL/short-string/malformed-safe:

| Column | gov_fraud_analyst sees | gov_thailand_analyst sees |
| --- | --- | --- |
| `customer_name` | `Somchai P******` | `Protected Customer` |
| `national_id` | `*********0123` | `*************` |
| `mobile_number` | `******5678` | `**********` |
| `email` | `j******@example.com` | `hidden@example.com` |
| `account_id` | unmasked | `************1234` |

`gov_data_admin` sees original values; `gov_business_analyst`/`gov_auditor`
have no table grant at all.

## Row filters (BIAC exclusion semantics)

| Expression | Role / object | Result |
| --- | --- | --- |
| `NOT (fraud_flag OR risk_score >= 0.70)` | `gov_fraud_analyst` on `customer_transactions` | 14 fraud/high-risk rows |
| `country_code <> 'TH'` | `gov_thailand_analyst` on `customer_transactions` | 12 TH rows |
| `country_code <> 'TH'` | `gov_thailand_analyst` on `payment_business_summary` | TH aggregates only |
| `transaction_status <> 'APPROVED'` | defined, unattached (business analyst has view-only access instead) | - |

BIAC filters **exclude** rows where the expression is TRUE - the first
implementation used visibility predicates and was inverted during
real-identity testing (documented in troubleshooting.md).

## OpenMetadata enrichment

`js_aidp_starburst.js_financial_ice.gov_demo.*` (discovered by re-running
the `js_aidp_starburst_metadata` ingestion pipeline):

- Domain `FraudAndRisk`, owner `Fraud and Risk Team` on both objects.
- Table tags: `Governance.Governed` (new classification/tag created),
  `Sensitivity.Restricted`, `DataCategory.{CustomerData,TransactionData,
  FraudData}`; `DataLayer.DataProduct` on the summary view.
- Column tags per config: `Sensitivity.PII` on name/mobile/email,
  `HighlySensitivePII` on `national_id`, `FinancialData` on account/amount,
  `Restricted`+`FraudData` on risk/fraud fields.
- Governance description explaining that enforcement lives in AIDP roles.

## Test results (all as real identities)

`python scripts/test_role_access.py` -> **36/36 PASS**
(`reports/access_test_results.csv`, `access_test_summary.md`), including:

- Identity proof: every session records `current_user` + `SHOW CURRENT ROLES`.
- Admin: 36 rows, all 4 countries, unmasked.
- Fraud: exactly 14 rows; every row fraud or risk>=0.70; all PII masked;
  INSERT/CTAS/CREATE VIEW/CREATE ROLE denied.
- Business: summary view readable; direct table, `national_id`, fraud
  fields all denied.
- Thailand: every row `TH`; explicit `VN` query -> 0; no-predicate query
  -> 1 country; subquery/UNION/self-join still TH-only; PII + account
  masked; DELETE denied.
- Auditor: `SHOW TABLES`/`SHOW ROLES` OK; SELECT/INSERT denied.

`python scripts/validate_demo.py` -> **19/19 PASS**
(`reports/validation_report.md`) covering all success criteria including
synthetic data, originals untouched (2,687,202 payment rows / 10,000
customers readable and unchanged), idempotent re-runs, sanitized reports,
rollback coverage.

## Audit evidence

`python scripts/collect_audit_evidence.py` -> `audit_access_evidence.csv`,
`audit_change_evidence.csv`, `audit_evidence_summary.md` (sanitized).

At last collection: **915 demo-relevant access events - 518 ALLOW,
397 DENY** - covering allowed selects, denied selects, denied writes,
masked/filtered queries per persona, plus the full change-log trail of
role/grant/mask/filter creation and group assignments.

## Demo commands

See README Quick start. Presenter flow: `docs/demo_script.md`
(6 scenes, ~15 min), prep: `docs/presenter_checklist.md`.

## Navigation

- **SEP UI** `https://ddae.lab9bgp.com/ui` (SSO as `dv-admin`, enable
  `sysadmin`): *Access control* -> Roles / Column masks / Row filters /
  Audit log.
- **OpenMetadata** `http://10.246.25.115:8585` -> service
  `js_aidp_starburst` -> `js_financial_ice` -> `gov_demo`.

## Known limitations and fallbacks

- Masks/filters/group-assignments/audit are **REST-or-UI only** - no SQL
  DDL in 479-e.4. Scripts use the BIAC REST API.
- Row filters are exclusion predicates - must be written inverted
  (verified).
- `SECURITY DEFINER` views require owner privileges **with grant option**
  (verified; the summary view uses this).
- `fraud_alerts` has no `transaction_id` - `account_id` is the real
  correlation key (no invented relationship).
- Keycloak realm minimum password length is 9 - the demo password in
  `AIDP_DEMO_USER_PASSWORD` complies (requested `P@ssword` is rejected).
- `dv-admin`'s `sysadmin` is off by default - scripts send the role
  header; manual SQL sessions must `SET ROLE sysadmin`.

## Rollback

Every mutating script wrote a `reports/rollback_*.json` plan before
applying. Full teardown:

```bash
python scripts/reset_demo.py              # dry-run plan
python scripts/reset_demo.py --apply      # masks/filters/grants/assignments/roles
python scripts/reset_demo.py --apply --drop-data            # + gov_demo objects
python scripts/reset_demo.py --apply --restore-scaffolding  # + pre-demo group roles
```

SQL-only equivalent: `sql/99_cleanup.sql`. Original banking datasets were
never modified - nothing to roll back there.

## Success criteria - final state

All 18 criteria verified PASS via `validate_demo.py` (19/19 checks) plus
manual verification recorded above, including: real-identity tests,
no-credential/no-PII reports, idempotent re-runs, and complete rollback
documentation.
