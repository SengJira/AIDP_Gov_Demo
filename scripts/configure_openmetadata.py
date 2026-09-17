#!/usr/bin/env python3
"""Phase 8: OpenMetadata governance enrichment for gov_demo assets.

Adds descriptions, domain (FraudAndRisk), owner (Fraud and Risk Team),
and sensitivity tags to js_aidp_starburst.js_financial_ice.gov_demo.*.

OM 1.9.3 mechanics used:
  - PATCH /tables/{id}  (application/json-patch+json)
      /description, /owners/-, /tags/-, /columns/{idx}/tags/-,
      /columns/{idx}/description
  - PUT /domains/{name}/assets/add  {"assets":[{"id","type"}]}
  - POST /classifications, POST /tags (create missing governance tags)

Dry-run by default; --apply to change. Idempotent: existing tags/owners
are not duplicated. Tags document sensitivity only - enforcement lives
in AIDP/SEP BIAC.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aidp_common import (PROJECT_ROOT, REPORTS_DIR, OmClient, load_settings,
                         om_list_all)

CONFIG_DIR = PROJECT_ROOT / "config"

SCHEMA_FQN = "js_aidp_starburst.js_financial_ice.gov_demo"
PATCH_H = {"Content-Type": "application/json-patch+json"}


def tag_ref(fqn):
    return {"tagFQN": fqn, "source": "Classification",
            "labelType": "Manual", "state": "Confirmed"}


class TagResolver:
    """Resolve bare config tag names (PII, Governed, ...) to OM tag FQNs,
    creating missing tags under a Governance classification."""

    PREFERRED = {  # bare name -> candidate FQNs in preference order
        "PII": ["Sensitivity.PII", "PII.Sensitive"],
        "HighlySensitivePII": ["Sensitivity.HighlySensitivePII"],
        "FinancialData": ["Sensitivity.FinancialData"],
        "Restricted": ["Sensitivity.Restricted"],
        "CustomerData": ["DataCategory.CustomerData"],
        "TransactionData": ["DataCategory.TransactionData"],
        "FraudData": ["DataCategory.FraudData"],
        "DataProduct": ["DataLayer.DataProduct", "DataObservability.DataProduct"],
        "Governed": ["Governance.Governed", "DataCategory.Governed"],
    }

    def __init__(self, om, apply_mode):
        self.om = om
        self.apply_mode = apply_mode
        self.existing = {t["fullyQualifiedName"] for t in
                         om_list_all(om, "tags", {"limit": 500})}
        self.resolved = {}
        self.to_create = []

    def resolve(self, name):
        if name in self.resolved:
            return self.resolved[name]
        for cand in self.PREFERRED.get(name, []) + [name,
                                                    f"Governance.{name}"]:
            if cand in self.existing:
                self.resolved[name] = cand
                return cand
        fqn = f"Governance.{name}"
        self.resolved[name] = fqn
        self.to_create.append(name)
        return fqn

    def ensure_created(self):
        if not self.to_create:
            return
        try:
            self.om.post("/classifications",
                         json={"name": "Governance",
                               "description": "AIDP governance showcase tags"})
        except RuntimeError as e:
            if "409" not in str(e) and "already" not in str(e).lower():
                raise
        for name in self.to_create:
            try:
                self.om.post("/tags", json={
                    "name": name, "classification": "Governance",
                    "description": f"Governance tag '{name}' for the AIDP "
                                   "governance showcase"})
                print(f"    + created tag Governance.{name}")
            except RuntimeError as e:
                if "409" not in str(e) and "already" not in str(e).lower():
                    raise


def plan_table(om, tid, cfg_entry, resolver, owner_id):
    """Return (patch_ops, notes, needs_domain_asset) for one table."""
    ops, notes = [], []
    full = om.get(f"/tables/{tid}", params={"fields": "tags,owners,domains"})

    want_desc = cfg_entry["description"].strip()
    if (full.get("description") or "").strip() != want_desc:
        ops.append({"op": "add", "path": "/description",
                    "value": want_desc})
        notes.append("description")

    if owner_id not in {o["id"] for o in (full.get("owners") or [])}:
        ops.append({"op": "add", "path": "/owners/-",
                    "value": {"id": owner_id, "type": "team"}})
        notes.append("owner")

    existing = {t["tagFQN"] for t in (full.get("tags") or [])}
    for name in cfg_entry.get("table_tags", []):
        fqn = resolver.resolve(name)
        if fqn not in existing:
            ops.append({"op": "add", "path": "/tags/-", "value": tag_ref(fqn)})
            notes.append(f"tag {fqn}")

    col_tags = cfg_entry.get("column_tags", {})
    for idx, col in enumerate(full.get("columns") or []):
        ctags = {t["tagFQN"] for t in (col.get("tags") or [])}
        for name in col_tags.get(col["name"], []):
            fqn = resolver.resolve(name)
            if fqn not in ctags:
                ops.append({"op": "add", "path": f"/columns/{idx}/tags/-",
                            "value": tag_ref(fqn)})
                notes.append(f"col {col['name']} -> {fqn}")

    needs_domain = True
    for d in (full.get("domains") or []):
        if d["name"] == "FraudAndRisk":
            needs_domain = False
    return ops, notes, needs_domain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    settings = load_settings()
    cfg = yaml.safe_load((CONFIG_DIR / "openmetadata_governance.yaml").read_text())
    om = OmClient(settings)

    team = next(t for t in om_list_all(om, "teams", {"limit": 200})
                if t["name"] == cfg["owner_team"])
    domain = next(d for d in om_list_all(om, "domains", {"limit": 200})
                  if d["name"] == cfg["domain"])
    tables = {t["name"]: t for t in om_list_all(
        om, "tables", {"databaseSchema": SCHEMA_FQN, "limit": 200})}

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== Phase 8 - OpenMetadata enrichment ({mode}) ===")
    print(f"  service={cfg['service']} domain={domain['name']} owner={team['name']}\n")

    resolver = TagResolver(om, args.apply)
    if args.apply:
        # pre-resolve all tag names so creation happens first
        for entry in cfg["table_enrichment"].values():
            for name in entry.get("table_tags", []):
                resolver.resolve(name)
            for names in entry.get("column_tags", {}).values():
                for name in names:
                    resolver.resolve(name)
        resolver.ensure_created()

    rollback = []
    for fqn_suffix, entry in cfg["table_enrichment"].items():
        tname = fqn_suffix.split(".")[-1]
        if tname not in tables:
            print(f"  !! {tname} not in OpenMetadata - trigger metadata ingestion")
            continue
        tid = tables[tname]["id"]
        ops, notes, needs_domain = plan_table(om, tid, entry, resolver,
                                              team["id"])
        print(f"  {tname}: {', '.join(notes) if notes else 'already enriched'}"
              + (" (+domain)" if needs_domain else ""))
        if not args.apply:
            continue
        if ops:
            om.request("PATCH", f"/tables/{tid}", json=ops, headers=PATCH_H)
        if needs_domain:
            om.request("PUT", f"/domains/{domain['name']}/assets/add",
                       json={"assets": [{"id": tid, "type": "table"}]})
        rollback.append({"entity": tname, "id": tid,
                         "remove": "PATCH /tables/{id} replace /tags, /owners, "
                                   "/description; PUT /domains/FraudAndRisk/"
                                   "assets/remove"})

    if args.apply:
        REPORTS_DIR.mkdir(exist_ok=True)
        rb = REPORTS_DIR / f"rollback_openmetadata_{time.strftime('%Y%m%d_%H%M%S')}.json"
        rb.write_text(json.dumps(rollback, indent=2))
        print("\n=== Verification ===")
        for fqn_suffix in cfg["table_enrichment"]:
            tname = fqn_suffix.split(".")[-1]
            if tname not in tables:
                continue
            f = om.get(f"/tables/{tables[tname]['id']}",
                       params={"fields": "tags,owners,domains"})
            print(f"  {tname}:")
            print(f"    domain : {[d['name'] for d in (f.get('domains') or [])]}")
            print(f"    owner  : {[o['name'] for o in (f.get('owners') or [])]}")
            print(f"    tags   : {[t['tagFQN'] for t in (f.get('tags') or [])]}")
            for c in (f.get("columns") or []):
                ct = [t["tagFQN"] for t in (c.get("tags") or [])]
                if ct:
                    print(f"    col {c['name']}: {ct}")
        print(f"\nRollback notes -> {rb}")
    else:
        print("\n(dry-run - re-run with --apply)")


if __name__ == "__main__":
    main()
