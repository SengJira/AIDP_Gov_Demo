# Governance architecture

## Platform

Dell AIDP exposes a Starburst Enterprise (SEP) 479-e.4 coordinator behind
`https://ddae.lab9bgp.com`. Access control is the **built-in access
control (BIAC)** model - not Ranger, not file-based. All enforcement is
native to the SEP engine: no application-code simulation anywhere in this
demo.

```text
                     HTTPS 443
  users  ─────────────────────────────────────────────┐
 (Basic auth for SQL/REST, OIDC for UI)               │
                                                      ▼
   Keycloak realm `ddae`          AIDP / SEP coordinator (ddae.lab9bgp.com)
   https://ddlh.lab9bgp.com/auth  ┌─────────────────────────────────────┐
   users: gov-*                   │  BIAC                               │
   groups: /governance-admins     │   roles ──► grants (deny-by-absence)│
           /fraud-analysts   ───► │     │───► column masks  (query time)│
           /business-analysts     │     │───► row filters   (pre-scan)  │
           /thailand-analysts     │     └───► audit logs                │
           /data-auditors         └───────┬─────────────────────────────┘
                                          │
                          catalogs: js_financial_ice (Iceberg/S3),
                                    js_mysql_customer360 (MySQL)

   OpenMetadata http://10.246.25.115:8585
   service js_aidp_starburst - metadata/tags/domain/owner (documentation,
   NOT enforcement)
```

## Identity flow

1. User authenticates with Keycloak-backed credentials (Basic for JDBC/
   Python/REST, OIDC for the web UI).
2. SEP resolves the user's **Keycloak groups** at login.
3. BIAC maps groups to roles via *role assignments* (subject kind GROUP).
   `SHOW CURRENT ROLES` inside a session shows the resolved roles.
4. Every table access is evaluated against the grants of the enabled
   roles. Access is **denied by absence of a grant** - there are no broad
   grants followed by exceptions.

## Enforcement objects

| Mechanism | Where it lives | How applied |
| --- | --- | --- |
| Role | BIAC (`POST /api/v1/biac/roles`) | assigned to Keycloak groups |
| Grant | BIAC (`/roles/{id}/grants`) | `ALLOW`/`DENY` + `APPLY_*` effects on catalog/schema/table/column |
| Column mask | BIAC expression + attachment | `"@column"` placeholder expression, evaluated per-cell at query time |
| Row filter | BIAC expression + attachment | predicate evaluated **before** data reaches the user; `TRUE` = row excluded |
| Audit | BIAC `/audit/accessLogs`, `/audit/changeLogs` | per-access allow/deny + all policy changes |

Important verified semantics:

- **Row-filter expressions are exclusion predicates.** Rows where the
  expression evaluates `TRUE` are *hidden*. The visibility rule must be
  written inverted (e.g. `country_code <> 'TH'` to keep only TH).
- **Mask expressions use the `"@column"` placeholder** and must return the
  same type as the column.
- Row filters apply before data reaches the source; masks apply to the
  returned values. Filters on a table also apply to views built on it
  (verified on `payment_business_summary`).
- BIAC changes take effect on the next query - no restart needed.

## Admin path

`dv-admin` holds `sysadmin` **with admin option** but it is not enabled by
default:

- SQL: `SET ROLE sysadmin`
- REST: header `X-Trino-Role: system=ROLE{sysadmin}`

The scripts send that header for every BIAC call.

## What OpenMetadata contributes

OpenMetadata holds descriptions, `FraudAndRisk` domain, `Fraud and Risk
Team` ownership, and sensitivity tags (`Sensitivity.PII`,
`Sensitivity.HighlySensitivePII`, `Sensitivity.FinancialData`,
`Sensitivity.Restricted`, `Governance.Governed`, `DataLayer.DataProduct`,
`DataCategory.*`). Tags document sensitivity and lineage; **they do not
enforce anything**. Enforcement is entirely in BIAC. This separation is
part of the demo narrative.

## Demo data isolation

All governed objects live in `js_financial_ice.gov_demo`:

- `customer_transactions` - 36 deterministic synthetic rows across
  TH/SG/VN/LA with normal, high-risk and fraud-flagged payments.
- `payment_business_summary` - `SECURITY DEFINER` aggregate view
  (country/date/channel/category metrics, no PII columns), owned by the
  data-engineering identity `jirawut`.

Original catalogs (`banking`, `customer360`, `analytics`) are read-only
context and were never modified.
