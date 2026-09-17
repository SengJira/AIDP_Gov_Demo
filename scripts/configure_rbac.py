#!/usr/bin/env python3
"""Phase 3/5: create the five governance roles, least-privilege grants and
Keycloak-group role assignments via the SEP BIAC REST API.

Also removes the pre-existing scaffolding that assigned the broad
`jirawut_demo` / `pystarburst` roles to all five demo groups - those would
defeat least privilege (every analyst would get full catalog access).
Removals are recorded in the rollback file and can be restored.

Dry-run by default; pass --apply to execute.
"""

import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aidp_common import (Action, BiacClient, Plan, load_settings,
                         print_mode, require_apply_flag)

CONFIG = Path(__file__).resolve().parent.parent / "config"
SCAFFOLD_ROLES = ["jirawut_demo", "pystarburst"]
DEMO_GROUPS = ["governance-admins", "fraud-analysts", "business-analysts",
               "thailand-analysts", "data-auditors"]
VIEW_OWNER_ROLE = "jirawut_demo"


def table_entity(e: dict) -> dict:
    ent = {"category": "TABLES", "allEntities": False}
    if e.get("catalog"):
        ent["catalog"] = e["catalog"]
    if e.get("schema"):
        ent["schema"] = e["schema"]
    if e.get("table"):
        ent["table"] = e["table"]
    if e.get("columns"):
        ent["columns"] = e["columns"]
    return ent


def category_entity(e: dict) -> dict:
    ent = {"category": e["category"], "allEntities": e.get("allEntities", True)}
    if e.get("entityKey"):
        ent["entityKey"] = e["entityKey"]
    return ent


def grant_key(g: dict) -> tuple:
    e = g.get("entity", {})
    detail = tuple(sorted((k, str(v)) for k, v in e.items() if k != "allEntities"))
    return (g.get("action"), g.get("effect"), detail)


def main():
    apply = require_apply_flag(sys.argv)
    settings = load_settings()
    print_mode(apply, "Phase 3/5 - configure RBAC")

    personas = yaml.safe_load((CONFIG / "personas.yaml").read_text())["personas"]
    biac = BiacClient(settings)

    roles_by_name = {r["name"]: r for r in biac.list_roles()}
    scaff_ids = {roles_by_name[n]["id"] for n in SCAFFOLD_ROLES if n in roles_by_name}

    plan = Plan("configure_rbac", apply)

    # 1. roles ------------------------------------------------------------
    role_ids = {}
    for name, spec in personas.items():
        existing = roles_by_name.get(name)
        if existing:
            role_ids[name] = existing["id"]
            plan.add(Action(f"role {name} exists (id={existing['id']})", "role", skipped=True))
        else:
            desc = (spec.get("purpose") or "").strip()[:400]
            def make(n=name, d=desc):
                r = biac.create_role(n, d)
                rid = (r.get("result") or r).get("id")
                role_ids[n] = rid if rid is not None else biac.role_id(n)
                return r
            plan.add(Action(f"CREATE ROLE {name}", "role",
                            detail={"name": name}, fn=make,
                            rollback={"api": f"DELETE /biac/roles/{{id}}"}))

    # 2. grants -----------------------------------------------------------
    existing_grants = {}
    for name in personas:
        rid = roles_by_name.get(name, {}).get("id")
        if rid is not None:
            existing_grants[name] = {grant_key(g) for g in biac.list_grants(rid)}
        else:
            existing_grants[name] = set()

    for name, spec in personas.items():
        for gspec in spec.get("grants", []):
            e = gspec["entity"]
            entity = table_entity(e) if "catalog" in e else category_entity(e)
            for action in gspec["actions"]:
                key = (action, "ALLOW", tuple(sorted(
                    (k, str(v)) for k, v in entity.items() if k != "allEntities")))
                desc = (f"GRANT {action} on {entity} -> {name}"
                        + (f" ({gspec['note']})" if gspec.get("note") else ""))
                if key in existing_grants[name]:
                    plan.add(Action(desc + " — already granted", "grant",
                                    detail=entity, skipped=True))
                    continue
                def make(n=name, a=action, en=entity):
                    return biac.create_grant(role_ids[n], "ALLOW", a, en)
                plan.add(Action(desc, "grant", detail=entity, fn=make,
                                rollback={"role": name, "entity": entity,
                                          "action": action}))

    # 3. grant-option SELECT on gov_demo for the view-owner role ----------
    # Required so the SECURITY DEFINER summary view (owned by jirawut) can
    # be queried by other users - SEP evaluates "owner can create view
    # selecting from X" which needs SELECT WITH GRANT OPTION.
    vo_entity = {"category": "TABLES", "allEntities": False,
                 "catalog": "js_financial_ice", "schema": "gov_demo"}
    vo_key = ("SELECT", "ALLOW_WITH_GRANT_OPTION",
              tuple(sorted((k, str(v)) for k, v in vo_entity.items() if k != "allEntities")))
    vo_grants = {grant_key(g) for g in biac.list_grants(roles_by_name[VIEW_OWNER_ROLE]["id"])} \
        if VIEW_OWNER_ROLE in roles_by_name else set()
    if vo_key in vo_grants:
        plan.add(Action("jirawut_demo already has SELECT WITH GRANT OPTION on gov_demo",
                        "grant", detail=vo_entity, skipped=True))
    else:
        plan.add(Action(
            "GRANT SELECT WITH GRANT OPTION on gov_demo -> jirawut_demo "
            "(needed by the SECURITY DEFINER summary view; additive grant "
            "to an existing role, documented)",
            "grant", detail=vo_entity,
            fn=lambda: biac.create_grant(roles_by_name[VIEW_OWNER_ROLE]["id"],
                                         "ALLOW_WITH_GRANT_OPTION", "SELECT", vo_entity),
            rollback={"role": VIEW_OWNER_ROLE, "entity": vo_entity,
                      "action": "SELECT", "effect": "ALLOW_WITH_GRANT_OPTION"}))

    # 4. group -> role assignments ----------------------------------------
    for name, spec in personas.items():
        group = spec["keycloak_group"]
        existing_assign = []
        try:
            existing_assign = biac.list_subject_assignments("groups", group)
        except Exception:
            pass
        rid = role_ids.get(name) or roles_by_name.get(name, {}).get("id")
        already = rid is not None and any(a["roleId"] == rid for a in existing_assign)
        desc = f"ASSIGN role {name} -> group {group}"
        if already:
            plan.add(Action(desc + " — already assigned", "assignment",
                            skipped=True))
            continue
        def make(g=group, n=name):
            resolved = role_ids.get(n) or biac.role_id(n)
            if resolved is None:
                raise RuntimeError(f"role {n} does not exist at apply time")
            return biac.assign_role("groups", g, resolved)
        plan.add(Action(desc, "assignment",
                        detail={"group": group, "role": name}, fn=make,
                        rollback={"delete_assignment": {"kind": "groups",
                                                       "name": group}}))

    # 5. remove scaffolding assignments ------------------------------------
    for group in DEMO_GROUPS:
        try:
            assigns = biac.list_subject_assignments("groups", group)
        except Exception as e:
            plan.add(Action(f"could not list assignments for {group}: {e}", "check", skipped=True))
            continue
        for a in assigns:
            if a["roleId"] in scaff_ids:
                role_name = next((n for n, r in roles_by_name.items() if r["id"] == a["roleId"]), a["roleId"])
                plan.add(Action(
                    f"REMOVE scaffolding assignment: group {group} <- role {role_name} "
                    f"(broad catalog access would defeat least privilege)",
                    "delete_assignment",
                    detail={"group": group, "roleId": a["roleId"], "assignmentId": a["id"]},
                    fn=(lambda g=group, aid=a["id"]: biac.delete_assignment("groups", g, aid)),
                    rollback={"re_add": {"kind": "groups", "name": group,
                                         "roleId": a["roleId"]}}))

    if not apply:
        print(plan.summary())
        print("\nDry-run complete. Re-run with --apply to execute.")
        return

    applied = plan.execute()
    plan.write_rollback(applied)

    # verify: list assignments per group
    print("\n=== Resulting group assignments ===")
    for group in DEMO_GROUPS:
        assigns = biac.list_subject_assignments("groups", group)
        names = [next((n for n, r in roles_by_name.items() if r["id"] == a["roleId"]), a["roleId"])
                 for a in assigns]
        print(f"  {group}: {names}")


if __name__ == "__main__":
    main()
