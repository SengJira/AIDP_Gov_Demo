#!/usr/bin/env python3
"""Phase 6: dynamic column masking via SEP BIAC.

Creates mask expressions (POST /api/v1/biac/expressions/columnMask) and
attaches them to role table-entities (POST /api/v1/biac/roles/{id}/columnMasks).
Masks apply at query time; source values are never modified.

Dry-run by default; pass --apply to execute.
"""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aidp_common import (Action, BiacClient, Plan, load_settings,
                         print_mode, require_apply_flag)

CONFIG = Path(__file__).resolve().parent.parent / "config" / "masking_policies.yaml"


def main():
    apply = require_apply_flag(sys.argv)
    settings = load_settings()
    print_mode(apply, "Phase 6 - configure column masking")

    cfg = yaml.safe_load(CONFIG.read_text())
    expressions = cfg["expressions"]
    role_masks = cfg["role_masks"]

    biac = BiacClient(settings)
    roles_by_name = {r["name"]: r for r in biac.list_roles()}
    existing_exprs = {e["name"]: e for e in biac.list_expressions("columnMask")}

    plan = Plan("configure_masking", apply)

    # 1. expressions --------------------------------------------------------
    expr_ids = {}
    for name, spec in expressions.items():
        if name in existing_exprs:
            expr_ids[name] = existing_exprs[name]["id"]
            if existing_exprs[name]["expression"].strip() == spec["expression"].strip():
                plan.add(Action(f"mask expression {name} exists (id={expr_ids[name]})",
                                "expr", skipped=True))
            else:
                plan.add(Action(
                    f"mask expression {name} exists with DIFFERENT definition - "
                    f"manual review required (id={expr_ids[name]})", "expr", skipped=True))
            continue
        def make(n=name, s=spec):
            r = biac.create_expression("columnMask", n, s["expression"],
                                     s.get("description", ""))
            expr_ids[n] = (r.get("result") or r).get("id") or biac.expression_id("columnMask", n)
            return r
        plan.add(Action(
            f"CREATE mask expression {name}  [{spec.get('example_out','')}]",
            "expr", detail={"expression": spec["expression"]}, fn=make,
            rollback={"delete_expression": {"kind": "columnMask", "name": name}}))

    # 2. attach masks to roles ---------------------------------------------
    existing_masks = {}
    for role_name in role_masks:
        rid = roles_by_name.get(role_name, {}).get("id")
        existing_masks[role_name] = biac.list_role_masks(rid) if rid else []

    for role_name, tables in role_masks.items():
        rid = roles_by_name.get(role_name, {}).get("id")
        if rid is None:
            plan.add(Action(f"role {role_name} missing - run configure_rbac.py first",
                            "check", skipped=True))
            continue
        for table_fqn, cols in tables.items():
            catalog, schema, table = table_fqn.split(".")
            for col, expr_name in cols.items():
                entity = {"category": "TABLES", "allEntities": False,
                          "catalog": catalog, "schema": schema,
                          "table": table, "columns": [col]}
                already = any(
                    m["entity"].get("table") == table
                    and col in (m["entity"].get("columns") or [])
                    and m.get("expressionId") == expr_ids.get(expr_name, existing_exprs.get(expr_name, {}).get("id"))
                    for m in existing_masks[role_name])
                desc = f"MASK {col} on {table} with {expr_name} -> {role_name}"
                if already:
                    plan.add(Action(desc + " — already applied", "mask", skipped=True))
                    continue
                def make(r=rid, en=entity, ename=expr_name):
                    eid = expr_ids.get(ename) or biac.expression_id("columnMask", ename)
                    if eid is None:
                        raise RuntimeError(f"expression {ename} does not exist at apply time")
                    return biac.add_role_mask(r, en, eid)
                plan.add(Action(desc, "mask",
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

    print("\n=== Resulting role masks ===")
    for role_name in role_masks:
        rid = roles_by_name.get(role_name, {}).get("id")
        for m in biac.list_role_masks(rid):
            e = m["entity"]
            print(f"  {role_name}: {e.get('table')}.{e.get('columns')} expr={m['expressionId']}")


if __name__ == "__main__":
    main()
