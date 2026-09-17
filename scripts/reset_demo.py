#!/usr/bin/env python3
"""Rollback / teardown for the AIDP governance showcase.

Removes, in dependency order and only if present:
  1. BIAC row filters + column masks attached to gov_* roles
  2. BIAC grants held by gov_* roles
  3. BIAC expression entities (gov_demo_*)
  4. Group assignments of demo groups to gov_* roles
  5. gov_* roles
  6. SQL objects (view, table, schema) - only with --drop-data

Optionally restores the pre-demo scaffolding assignments
(jirawut_demo, pystarburst) to the demo Keycloak groups with
--restore-scaffolding.

Dry-run by default; --apply executes. Never touches original
banking datasets or non-gov objects.
"""

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aidp_common import (PROJECT_ROOT, BiacClient, load_settings,
                         run_sql_statements, sql_error_text)

GOV_ROLES = ["gov_data_admin", "gov_fraud_analyst", "gov_business_analyst",
             "gov_thailand_analyst", "gov_auditor"]


def assignment_role_name(a):
    r = a.get("role") or {}
    return r.get("name") or a.get("roleName")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore-scaffolding", action="store_true",
                    help="re-add jirawut_demo/pystarburst to demo groups")
    ap.add_argument("--drop-data", action="store_true",
                    help="also drop the gov_demo schema objects")
    args = ap.parse_args()
    settings = load_settings()
    biac = BiacClient(settings)
    mapping = yaml.safe_load((PROJECT_ROOT / "config/role_mapping.yaml").read_text())
    scaffold = mapping.get("scaffolding_assignments_to_remove", {})

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== reset_demo ({mode}) ===\n")
    roles = {r["name"]: r for r in biac.list_roles()}
    exprs = {"columnMask": {e["name"]: e for e in biac.list_expressions("columnMask")},
             "rowFilter": {e["name"]: e for e in biac.list_expressions("rowFilter")}}

    steps = []

    for rn in GOV_ROLES:
        if rn not in roles:
            continue
        rid = roles[rn]["id"]
        for f in biac.list_role_filters(rid):
            steps.append((f"detach row filter {f['id']} from {rn}",
                          lambda rid=rid, fid=f["id"]: biac.delete_role_filter(rid, fid)))
        for m in biac.list_role_masks(rid):
            steps.append((f"detach column mask {m['id']} from {rn}",
                          lambda rid=rid, mid=m["id"]: biac.delete_role_mask(rid, mid)))
        for g in biac.list_grants(rid):
            steps.append((f"revoke grant {g['id']} from {rn}",
                          lambda rid=rid, gid=g["id"]: biac.delete_grant(rid, gid)))

    for kind, d in exprs.items():
        for name, e in d.items():
            if name.startswith("gov_demo_"):
                steps.append((f"delete {kind} expression {name}",
                              lambda k=kind, eid=e["id"]: biac.delete_expression(k, eid)))

    for m in mapping.get("mappings", []):
        group, role_name = m["keycloak_group"], m["biac_role"]
        if role_name not in roles:
            continue
        for a in biac.list_subject_assignments("groups", group):
            if assignment_role_name(a) == role_name:
                steps.append((f"unassign {role_name} from group {group}",
                              lambda g=group, aid=a["id"]:
                              biac.delete_assignment("groups", g, aid)))

    if args.restore_scaffolding:
        for group in scaffold.get("groups", []):
            have = {assignment_role_name(a)
                    for a in biac.list_subject_assignments("groups", group)}
            for srole in scaffold.get("roles", []):
                if srole in roles and srole not in have:
                    srid = roles[srole]["id"]
                    steps.append((f"restore {srole} -> group {group}",
                                  lambda g=group, rid=srid:
                                  biac.assign_role("groups", g, rid)))

    for rn in GOV_ROLES:
        if rn in roles:
            steps.append((f"delete role {rn}",
                          lambda rid=roles[rn]["id"]: biac.delete_role(rid, "RESTRICT")))

    if args.drop_data:
        sql = (PROJECT_ROOT / "sql/99_cleanup.sql").read_text()
        steps.append(("drop gov_demo view/table/schema (99_cleanup.sql)",
                      lambda: run_sql_statements(settings, settings.admin_user,
                                                 settings.admin_password, sql,
                                                 role="sysadmin")))

    for i, (label, fn) in enumerate(steps, 1):
        print(f"  {i:2}. [{mode}] {label}")
        if args.apply:
            try:
                fn()
            except Exception as e:
                print(f"      FAILED: {sql_error_text(e)[:160]}")

    print(f"\n{len(steps)} step(s) {'executed' if args.apply else 'planned'}.")
    if not args.apply:
        print("(dry-run - re-run with --apply; add --drop-data to remove schema,")
        print(" --restore-scaffolding to re-add pre-demo group assignments)")


if __name__ == "__main__":
    main()
