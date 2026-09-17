#!/usr/bin/env python3
"""Phase 7: row-level filtering via SEP BIAC.

Creates row-filter expressions (POST /api/v1/biac/expressions/rowFilter)
and attaches them to role table-entities
(POST /api/v1/biac/roles/{id}/rowFilters).

SEMANTICS: the expression is an EXCLUSION condition - rows where it
evaluates TRUE are removed from the result set.

Dry-run by default; pass --apply to execute.
"""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aidp_common import (Action, BiacClient, Plan, load_settings,
                         print_mode, require_apply_flag)

CONFIG = Path(__file__).resolve().parent.parent / "config" / "row_filters.yaml"


def main():
    apply = require_apply_flag(sys.argv)
    settings = load_settings()
    print_mode(apply, "Phase 7 - configure row filters")

    cfg = yaml.safe_load(CONFIG.read_text())
    expressions = cfg["expressions"]
    role_filters = cfg["role_filters"]

    biac = BiacClient(settings)
    roles_by_name = {r["name"]: r for r in biac.list_roles()}
    existing_exprs = {e["name"]: e for e in biac.list_expressions("rowFilter")}

    plan = Plan("configure_row_filters", apply)

    # 1. expressions ---------------------------------------------------------
    expr_ids = {}
    for name, spec in expressions.items():
        if name in existing_exprs:
            expr_ids[name] = existing_exprs[name]["id"]
            if existing_exprs[name]["expression"].strip() == spec["expression"].strip():
                plan.add(Action(f"filter expression {name} exists (id={expr_ids[name]})",
                                "expr", skipped=True))
            else:
                plan.add(Action(
                    f"filter expression {name} exists with DIFFERENT definition - "
                    f"manual review required (id={expr_ids[name]})", "expr", skipped=True))
            continue
        def make(n=name, s=spec):
            r = biac.create_expression("rowFilter", n, s["expression"],
                                     s.get("description", ""))
            expr_ids[n] = (r.get("result") or r).get("id") or biac.expression_id("rowFilter", n)
            return r
        plan.add(Action(
            f"CREATE filter expression {name}  [keeps: {spec.get('keeps','')}]",
            "expr", detail={"expression": spec["expression"]}, fn=make,
            rollback={"delete_expression": {"kind": "rowFilter", "name": name}}))

    # 2. attach filters to roles ----------------------------------------------
    for role_name, tables in role_filters.items():
        rid = roles_by_name.get(role_name, {}).get("id")
        if rid is None:
            plan.add(Action(f"role {role_name} missing - run configure_rbac.py first",
                            "check", skipped=True))
            continue
        existing = biac.list_role_filters(rid)
        for table_fqn, expr_name in tables.items():
            catalog, schema, table = table_fqn.split(".")
            entity = {"category": "TABLES", "allEntities": False,
                      "catalog": catalog, "schema": schema, "table": table}
            already = any(
                f["entity"].get("table") == table
                and f.get("expressionId") == expr_ids.get(expr_name, existing_exprs.get(expr_name, {}).get("id"))
                for f in existing)
            desc = f"ROW FILTER {table} with {expr_name} -> {role_name}"
            if already:
                plan.add(Action(desc + " — already applied", "filter", skipped=True))
                continue
            def make(r=rid, en=entity, ename=expr_name):
                eid = expr_ids.get(ename) or biac.expression_id("rowFilter", ename)
                if eid is None:
                    raise RuntimeError(f"expression {ename} does not exist at apply time")
                return biac.add_role_filter(r, en, eid)
            plan.add(Action(desc, "filter",
                            detail={"entity": entity, "expression": expr_name},
                            fn=make,
                            rollback={"role": role_name, "entity": entity,
                                      "expression": expr_name}))

    if not apply:
        print(plan.summary())
        print("\nDry-run complete. Re-run with --apply to execute.")
        return

    applied = plan.execute()
    plan.write_rollback(applied)

    print("\n=== Resulting role row filters ===")
    for role_name in role_filters:
        rid = roles_by_name.get(role_name, {}).get("id")
        for f in biac.list_role_filters(rid):
            e = f["entity"]
            print(f"  {role_name}: {e.get('table')} expr={f['expressionId']}")


if __name__ == "__main__":
    main()
