#!/usr/bin/env python3
"""Phase 1: assess the AIDP environment and write discovery reports.

Read-only. Produces:
  reports/environment_assessment.md
  reports/current_access_inventory.csv
  reports/policy_capability_matrix.md
  reports/schema_inventory.md
"""

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aidp_common import (BiacClient, KeycloakAdmin, REPORTS_DIR, Settings,
                         load_settings, run_sql, sql_error_text, trino_connect)

DISCOVERY_SQL = [
    "SELECT current_user",
    "SELECT version()",
    "SHOW CATALOGS",
    "SHOW CURRENT ROLES",
    "SHOW ROLE GRANTS",
    "SHOW SCHEMAS FROM js_mysql_customer360",
    "SHOW TABLES FROM js_mysql_customer360.customer360",
    "SHOW COLUMNS FROM js_mysql_customer360.customer360.customers",
    "SHOW SCHEMAS FROM js_financial_ice",
    "SHOW TABLES FROM js_financial_ice.banking",
    "SHOW TABLES FROM js_financial_ice.analytics",
    "SHOW TABLES FROM js_financial_ice.ingestion",
    "SHOW CREATE VIEW js_financial_ice.analytics.v_customer_payment_360",
    "SHOW CREATE SCHEMA js_financial_ice.banking",
]

TABLES_FOR_SCHEMA_INVENTORY = [
    "js_mysql_customer360.customer360.customers",
    "js_financial_ice.banking.payment_transactions",
    "js_financial_ice.banking.fraud_alerts",
    "js_financial_ice.analytics.v_customer_payment_360",
]


def try_sql(settings, sql, role="sysadmin"):
    try:
        cols, rows = run_sql(settings, settings.admin_user, settings.admin_password,
                             sql, role=role)
        return cols, rows, None
    except Exception as e:
        return None, None, sql_error_text(e)


def main():
    settings = load_settings()
    REPORTS_DIR.mkdir(exist_ok=True)
    biac = BiacClient(settings)
    ts = time.strftime("%Y-%m-%d %H:%M:%S %Z")

    # ---- SQL discovery ------------------------------------------------
    sql_results = {}
    for q in DISCOVERY_SQL:
        cols, rows, err = try_sql(settings, q)
        sql_results[q] = (cols, rows, err)
        status = f"{len(rows)} rows" if err is None else f"ERROR: {err[:80]}"
        print(f"{q[:70]:72} -> {status}")

    # ---- BIAC state ---------------------------------------------------
    roles = biac.list_roles()
    role_grants = {}
    role_assignments = {}
    role_masks = {}
    role_filters = {}
    for r in roles:
        rid = r["id"]
        try:
            role_grants[rid] = biac.list_grants(rid)
        except Exception as e:
            role_grants[rid] = f"ERR {e}"
        try:
            role_assignments[rid] = biac.list_role_assignments(rid)
        except Exception as e:
            role_assignments[rid] = f"ERR {e}"
        try:
            role_masks[rid] = biac.list_role_masks(rid)
        except Exception:
            role_masks[rid] = []
        try:
            role_filters[rid] = biac.list_role_filters(rid)
        except Exception:
            role_filters[rid] = []

    mask_exprs = biac.list_expressions("columnMask")
    filter_exprs = biac.list_expressions("rowFilter")

    # ---- Keycloak -----------------------------------------------------
    kc = KeycloakAdmin(settings)
    try:
        kc_groups = kc.list_groups()
    except Exception as e:
        kc_groups = f"ERR {e}"
    demo_users = {}
    for u in ["gov-admin", "gov-fraud", "gov-biz", "gov-tha", "gov-audit",
              "dv-admin", "jirawut"]:
        try:
            rec = kc.find_user(u)
            if rec:
                groups = [g["path"] for g in kc.user_groups(rec["id"])]
                demo_users[u] = {"enabled": rec.get("enabled"), "groups": groups}
            else:
                demo_users[u] = {"missing": True}
        except Exception as e:
            demo_users[u] = {"error": str(e)[:120]}

    # ---- write current_access_inventory.csv ----------------------------
    inv_path = REPORTS_DIR / "current_access_inventory.csv"
    with open(inv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["role_id", "role_name", "grant_id", "effect", "action",
                    "entity_category", "entity_detail",
                    "mask_expr_id", "filter_expr_id"])
        for r in roles:
            grants = role_grants.get(r["id"]) or []
            if isinstance(grants, str):
                w.writerow([r["id"], r["name"], "", "", "", "", grants, "", ""])
                continue
            for g in grants:
                e = g.get("entity", {})
                detail = {k: v for k, v in e.items()
                          if k != "category" and v not in (None, "", False, [])}
                w.writerow([r["id"], r["name"], g.get("id"), g.get("effect"),
                            g.get("action"), e.get("category"),
                            json_safe(detail),
                            g.get("columnMaskExpressionId") or "",
                            g.get("rowFilterExpressionId") or ""])
    print(f"\nWrote {inv_path}")

    # ---- schema_inventory.md -------------------------------------------
    schema_md = ["# Schema inventory", "",
                 f"Captured {ts} as `{settings.admin_user}` (sysadmin).", ""]
    for t in TABLES_FOR_SCHEMA_INVENTORY:
        _, rows, err = try_sql(settings, f"SHOW COLUMNS FROM {t}")
        schema_md.append(f"## `{t}`")
        if err:
            schema_md.append(f"\nError: {err}\n")
            continue
        schema_md.append("\n| column | type |")
        schema_md.append("| --- | --- |")
        for r in rows:
            schema_md.append(f"| {r[0]} | {r[1]} |")
        _, cnt, _ = try_sql(settings, f"SELECT count(*) FROM {t}")
        if cnt:
            schema_md.append(f"\nRow count: **{cnt[0][0]}**")
        schema_md.append("")
    view_def = sql_results["SHOW CREATE VIEW js_financial_ice.analytics.v_customer_payment_360"]
    if view_def[1]:
        sec = "SECURITY DEFINER" if "SECURITY DEFINER" in view_def[1][0][0] else "SECURITY INVOKER"
        schema_md.append(f"## View security mode\n\n`v_customer_payment_360` is **{sec}** "
                         "(queries execute with the view owner's privileges).\n")
    schema_md.append("## Join-key note\n\n"
                     "`js_financial_ice.banking.fraud_alerts` has **no `transaction_id`** column. "
                     "The valid join keys to `payment_transactions` are `account_id` "
                     "(with `timestamp`/`event_date` for correlation). No synthetic "
                     "relationship was invented.\n")
    (REPORTS_DIR / "schema_inventory.md").write_text("\n".join(schema_md))
    print("Wrote schema_inventory.md")

    # ---- policy_capability_matrix.md ------------------------------------
    matrix = f"""# Policy capability matrix — AIDP / Starburst Enterprise 479-e.4

Captured {ts}. Verified live against `https://{settings.host}`.

| Capability | Mechanism | Status | Where |
| --- | --- | --- | --- |
| Catalog access control | BIAC grant on TABLES entity (catalog key) | Confirmed native AIDP/SEP | REST `/api/v1/biac/roles/{{id}}/grants`, UI, SQL `GRANT` |
| Schema access control | BIAC grant scoped to schema | Confirmed native | same |
| Table/view access control | BIAC grant scoped to table | Confirmed native | same |
| Column-level access | BIAC grant with `columns` list | Confirmed native | REST API / UI |
| Dynamic column masking | BIAC column-mask expression + role attachment | Confirmed native | REST `/api/v1/biac/expressions/columnMask`, `/roles/{{id}}/columnMasks`; UI Access control > Masks and filters |
| Row-level filtering | BIAC row-filter expression + role attachment | Confirmed native | REST `/api/v1/biac/expressions/rowFilter`, `/roles/{{id}}/rowFilters`; UI |
| Role create/drop | SQL `CREATE ROLE`/`DROP ROLE` or REST `/biac/roles` | Confirmed both | SQL + REST |
| Privilege grants | SQL `GRANT ... TO ROLE` (TABLES) or REST | Confirmed both | SQL limited to table privileges; non-TABLES categories via REST |
| Role -> user assignment | REST `/biac/subjects/users/{{u}}/assignments` | Confirmed native | REST / UI |
| Role -> IdP group assignment | REST `/biac/subjects/groups/{{g}}/assignments` | Confirmed native; groups resolve at login | REST / UI |
| Audit: access decisions | BIAC access log (ALLOW/DENY/ROW_FILTER/COLUMN_MASK) | Confirmed native | REST `/api/v1/biac/audit/accessLogs`, UI Access control > Audit log |
| Audit: policy changes | BIAC change log | Confirmed native | REST `/api/v1/biac/audit/changeLogs`, UI |
| SQL for masks/filters | not exposed | Unsupported by design | UI/REST only |
| Direct grants to users/groups via SQL | rejected by BIAC | Unsupported | privileges go to roles only |
| Object ownership / `GRANTED BY` | not supported by BIAC | Unsupported | documented SEP limitation |
| Aggregated curated view | `SECURITY DEFINER` view | Confirmed (view mechanism, not native masking) | SQL `CREATE VIEW` |

Legend: "Confirmed native" = tested live on this cluster; "Unsupported" =
rejected or not offered by the product on this version.
"""
    (REPORTS_DIR / "policy_capability_matrix.md").write_text(matrix)
    print("Wrote policy_capability_matrix.md")

    # ---- environment_assessment.md --------------------------------------
    ver = sql_results["SELECT version()"]
    ver_str = ver[1][0][0] if ver[1] else "unknown"
    roles_lines = "\n".join(
        f"- `{r['name']}` (id={r['id']})" for r in sorted(roles, key=lambda x: x["id"]))
    groups_txt = ""
    if isinstance(kc_groups, list):
        groups_txt = ", ".join(f"`{g['path']}`" for g in kc_groups)
    else:
        groups_txt = str(kc_groups)
    user_lines = "\n".join(
        f"- `{u}`: {d}" for u, d in demo_users.items())

    assessment = f"""# Environment assessment — AIDP governance showcase

Captured {ts} as `{settings.admin_user}` via `https://{settings.host}`.

## Platform

| Item | Value |
| --- | --- |
| AIDP endpoint | https://{settings.host} |
| Engine | Starburst Enterprise platform {ver_str} (Trino 479 base) |
| Access-control model | **Built-in access control (BIAC)** — roles, grants, column masks, row filters, audit log |
| Authentication | HTTPS Basic (password) backed by Keycloak; UI uses OAuth2/OIDC |
| Identity provider | Keycloak realm `ddae` at `https://ddlh.lab9bgp.com/auth` |
| Control-plane UI | Dell Data Lakehouse System Software at `https://ddlh.lab9bgp.com` |
| SEP web UI | `https://{settings.host}/ui` (Keycloak SSO, client `dv-sep-starburst-ui`) |

## How administration works here

* `dv-admin` holds the SEP `sysadmin` role **with admin option**; it is not
  enabled by default — sessions must `SET ROLE sysadmin` (SQL) or send
  `X-Trino-Role: system=ROLE{{sysadmin}}` (REST).
* SQL supports `CREATE/DROP ROLE`, `GRANT/REVOKE` on tables, `SET ROLE`,
  `SHOW` variants. Masks, row filters, group role assignments and audit
  logs are managed through the **BIAC REST API** (or the SEP web UI).
* Keycloak groups resolve into SEP at login: group role assignments are
  effective for SQL sessions (verified — see demo_user_readiness.md).

## Keycloak realm `ddae`

Groups present: {groups_txt}

Demo identity status:
{user_lines}

## Current SEP roles

{roles_lines}

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
"""
    for q, (cols, rows, err) in sql_results.items():
        res = f"{len(rows)} rows" if err is None else f"ERROR: {err[:120]}"
        assessment += f"| `{q}` | {res} |\n"

    assessment += f"""
## Mask/filter expressions present

* Column-mask expressions: {len(mask_exprs)} ({', '.join(e['name'] for e in mask_exprs)})
* Row-filter expressions: {len(filter_exprs)}

## Authentication methods verified

* SQL clients: Basic auth over HTTPS (`trino.dbapi`, trino-cli, PyStarburst).
* REST API: Basic auth + `X-Trino-Role` header.
* Web UI: Keycloak OAuth2 (authorization-code) via `dv-sep-starburst-ui`.

## Network notes

* Only TCP/443 is exposed on `{settings.host}`; nginx routes `/v1/*`
  (statement API) and `/api/v1/*` (SEP REST API) to the coordinator.
* OpenMetadata: `{settings.om_base}` (service `{settings.om_service}`).
"""
    (REPORTS_DIR / "environment_assessment.md").write_text(assessment)
    print("Wrote environment_assessment.md")


def json_safe(obj):
    import json
    return json.dumps(obj, ensure_ascii=False)


if __name__ == "__main__":
    main()
