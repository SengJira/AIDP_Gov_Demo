# Environment assessment — AIDP governance showcase

Captured 2026-09-17 10:32:23 CDT as `dv-admin` via `https://ddae.lab9bgp.com`.

## Platform

| Item | Value |
| --- | --- |
| AIDP endpoint | https://ddae.lab9bgp.com |
| Engine | Starburst Enterprise platform 479-e.4 (Trino 479 base) |
| Access-control model | **Built-in access control (BIAC)** — roles, grants, column masks, row filters, audit log |
| Authentication | HTTPS Basic (password) backed by Keycloak; UI uses OAuth2/OIDC |
| Identity provider | Keycloak realm `ddae` at `https://ddlh.lab9bgp.com/auth` |
| Control-plane UI | Dell Data Lakehouse System Software at `https://ddlh.lab9bgp.com` |
| SEP web UI | `https://ddae.lab9bgp.com/ui` (Keycloak SSO, client `dv-sep-starburst-ui`) |

## How administration works here

* `dv-admin` holds the SEP `sysadmin` role **with admin option**; it is not
  enabled by default — sessions must `SET ROLE sysadmin` (SQL) or send
  `X-Trino-Role: system=ROLE{sysadmin}` (REST).
* SQL supports `CREATE/DROP ROLE`, `GRANT/REVOKE` on tables, `SET ROLE`,
  `SHOW` variants. Masks, row filters, group role assignments and audit
  logs are managed through the **BIAC REST API** (or the SEP web UI).
* Keycloak groups resolve into SEP at login: group role assignments are
  effective for SQL sessions (verified — see demo_user_readiness.md).

## Keycloak realm `ddae`

Groups present: `/business-analysts`, `/data-auditors`, `/fraud-analysts`, `/governance-admins`, `/thailand-analysts`

Demo identity status:
- `gov-admin`: {'enabled': True, 'groups': ['/governance-admins']}
- `gov-fraud`: {'enabled': True, 'groups': ['/fraud-analysts']}
- `gov-biz`: {'enabled': True, 'groups': ['/business-analysts']}
- `gov-tha`: {'enabled': True, 'groups': ['/thailand-analysts']}
- `gov-audit`: {'enabled': True, 'groups': ['/data-auditors']}
- `dv-admin`: {'enabled': True, 'groups': []}
- `jirawut`: {'enabled': True, 'groups': []}

## Current SEP roles

- `sysadmin` (id=-2)
- `public` (id=-1)
- `ddae_svc_admin` (id=1)
- `jirawut_demo` (id=3)
- `pystarburst` (id=4)

## Pre-existing group assignments found

`jirawut_demo` and `pystarburst` are assigned to **all five** demo groups
(governance-admins, fraud-analysts, business-analysts, thailand-analysts,
data-auditors). Both roles hold catalog-wide privileges on
`js_financial_ice` (SELECT plus DDL/DML). If left in place every demo user
would bypass the governed objects entirely — `configure_rbac.py` removes
those two assignments per group (recorded, reversible). The roles
themselves and all their grants are preserved.

## Discovery command results

| Statement | Result |
| --- | --- |
| `SELECT current_user` | 1 rows |
| `SELECT version()` | 1 rows |
| `SHOW CATALOGS` | 8 rows |
| `SHOW CURRENT ROLES` | 1 rows |
| `SHOW ROLE GRANTS` | 2 rows |
| `SHOW SCHEMAS FROM js_mysql_customer360` | 3 rows |
| `SHOW TABLES FROM js_mysql_customer360.customer360` | 1 rows |
| `SHOW COLUMNS FROM js_mysql_customer360.customer360.customers` | 25 rows |
| `SHOW SCHEMAS FROM js_financial_ice` | 9 rows |
| `SHOW TABLES FROM js_financial_ice.banking` | 5 rows |
| `SHOW TABLES FROM js_financial_ice.analytics` | 4 rows |
| `SHOW TABLES FROM js_financial_ice.ingestion` | 4 rows |
| `SHOW CREATE VIEW js_financial_ice.analytics.v_customer_payment_360` | 1 rows |
| `SHOW CREATE SCHEMA js_financial_ice.banking` | 1 rows |

## Mask/filter expressions present

* Column-mask expressions: 6 (Show last 4, Show first 4, Null, Mask strings, Mask integers, Hash)
* Row-filter expressions: 0

## Authentication methods verified

* SQL clients: Basic auth over HTTPS (`trino.dbapi`, trino-cli, PyStarburst).
* REST API: Basic auth + `X-Trino-Role` header.
* Web UI: Keycloak OAuth2 (authorization-code) via `dv-sep-starburst-ui`.

## Network notes

* Only TCP/443 is exposed on `ddae.lab9bgp.com`; nginx routes `/v1/*`
  (statement API) and `/api/v1/*` (SEP REST API) to the coordinator.
* OpenMetadata: `http://10.246.25.115:8585` (service `js_aidp_starburst`).
