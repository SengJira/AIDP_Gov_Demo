#!/usr/bin/env python3
"""Phase 2: create the isolated gov_demo dataset (schema, table, synthetic
rows, aggregated view). Existing banking source tables are never modified.

Dry-run by default; pass --apply to execute.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aidp_common import (Action, Plan, REPORTS_DIR, env_get, load_env,
                         load_settings, print_mode, require_apply_flag,
                         run_sql, sql_error_text, trino_connect)

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
SCHEMA = "js_financial_ice.gov_demo"
TABLE = f"{SCHEMA}.customer_transactions"
VIEW = f"{SCHEMA}.payment_business_summary"


def split_statements(path: Path) -> list[str]:
    """Split a .sql file into statements (handles -- comments, incl. inline)."""
    import re
    lines = []
    for line in path.read_text().splitlines():
        # strip -- comments that are not inside single quotes
        out, in_q, i = [], False, 0
        while i < len(line):
            if line[i] == "'":
                in_q = not in_q
                out.append(line[i])
            elif not in_q and line[i:i+2] == "--":
                break
            else:
                out.append(line[i])
            i += 1
        lines.append("".join(out))
    text = "\n".join(lines)
    return [s.strip() for s in text.split(";") if s.strip()]


def main():
    apply = require_apply_flag(sys.argv)
    settings = load_settings()
    print_mode(apply, "Phase 2 - setup demo data")

    # current state checks (read-only)
    conn = trino_connect(settings, settings.admin_user, settings.admin_password,
                         catalog="js_financial_ice", role="sysadmin")
    cur = conn.cursor()

    def exists(q):
        cur.execute(q)
        return bool(cur.fetchall())

    schema_exists = exists(
        "SELECT 1 FROM js_financial_ice.information_schema.schemata "
        "WHERE schema_name='gov_demo'")
    table_exists = exists(
        "SELECT 1 FROM js_financial_ice.information_schema.tables "
        "WHERE table_schema='gov_demo' AND table_name='customer_transactions'")
    view_exists = exists(
        "SELECT 1 FROM js_financial_ice.information_schema.tables "
        "WHERE table_schema='gov_demo' AND table_name='payment_business_summary'")
    rowcount = 0
    if table_exists:
        cur.execute(f"SELECT count(*) FROM {TABLE}")
        rowcount = cur.fetchall()[0][0]

    print(f"schema exists={schema_exists} table exists={table_exists} "
          f"view exists={view_exists} rows={rowcount}\n")

    env = load_env()
    view_owner = env_get(env, "AIDP_VIEW_OWNER_USER", "jirawut")
    view_owner_pw = env_get(env, "AIDP_VIEW_OWNER_PASSWORD")

    ddl_statements = []
    for f in ["01_create_demo_schema.sql", "02_create_demo_table.sql",
              "03_load_synthetic_data.sql"]:
        ddl_statements += split_statements(SQL_DIR / f)
    view_statements = split_statements(SQL_DIR / "04_create_business_summary.sql")

    plan = Plan("setup_demo_data", apply)
    if schema_exists:
        plan.add(Action("schema gov_demo already exists", "schema", skipped=True))

    for i, stmt in enumerate(ddl_statements):
        label = stmt.split("\n")[0][:90]
        skip = table_exists and "CREATE TABLE" in stmt.upper()
        plan.add(Action(
            f"[sql:{i}] {label}", "ddl",
            detail={"sql": stmt[:400]},
            skipped=skip,
            fn=(lambda s=stmt: run_sql(settings, settings.admin_user,
                                       settings.admin_password, s,
                                       role="sysadmin", catalog="js_financial_ice",
                                       schema="gov_demo")),
            rollback={"note": "see sql/99_cleanup.sql"}))

    # The summary view is SECURITY DEFINER: SEP evaluates it with the
    # definer's *default-enabled* roles. dv-admin only has 'public' enabled
    # by default, so the view must be owned by an identity whose default
    # roles can read gov_demo (the data-engineering user jirawut).
    for i, stmt in enumerate(view_statements):
        label = stmt.split("\n")[0][:90]
        if view_owner_pw:
            fn = (lambda s=stmt: run_sql(settings, view_owner, view_owner_pw, s,
                                         catalog="js_financial_ice", schema="gov_demo"))
            who = view_owner
        else:
            fn = (lambda s=stmt: run_sql(settings, settings.admin_user,
                                         settings.admin_password, s,
                                         catalog="js_financial_ice", schema="gov_demo"))
            who = settings.admin_user
        plan.add(Action(
            f"[sql:view:{i}] {label}  (as {who})", "view",
            detail={"sql": stmt[:400], "definer": who},
            fn=fn,
            rollback={"sql": "DROP VIEW js_financial_ice.gov_demo.payment_business_summary"}))

    if not apply:
        print(plan.summary())
        print("\nDry-run complete. Re-run with --apply to execute.")
        return

    applied = plan.execute()
    plan.write_rollback(applied)

    # verification on a fresh session
    _, rows = run_sql(settings, settings.admin_user, settings.admin_password,
                      f"SELECT count(*), count(DISTINCT country_code) FROM {TABLE}",
                      role="sysadmin", catalog="js_financial_ice")
    total, countries = rows[0]
    _, per_country = run_sql(settings, settings.admin_user, settings.admin_password,
                             f"SELECT country_code, count(*) FROM {TABLE} GROUP BY 1 ORDER BY 1",
                             role="sysadmin", catalog="js_financial_ice")
    _, vr = run_sql(settings, settings.admin_user, settings.admin_password,
                    f"SELECT count(*) FROM {VIEW}",
                    role="sysadmin", catalog="js_financial_ice")
    summary_rows = vr[0][0]
    print(f"\nVerification: {total} rows across {countries} countries; "
          f"summary view has {summary_rows} rows")
    for c, n in per_country:
        print(f"  {c}: {n}")
    assert total >= 30 and countries >= 4, "dataset coverage check failed"
    print("\nDone.")


if __name__ == "__main__":
    main()
