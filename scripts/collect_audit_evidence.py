#!/usr/bin/env python3
"""Phase 10: collect sanitized audit evidence from the BIAC audit API.

Pulls /audit/accessLogs (allow/deny decisions per user+role+entity) and
/audit/changeLogs (role/grant/mask/filter changes), filters to demo-
relevant events (gov-* users, gov_* roles, gov_demo objects), sanitizes
and writes:

  reports/audit_access_evidence.csv
  reports/audit_change_evidence.csv
  reports/audit_evidence_summary.md

No passwords, tokens or raw PII are written. Long entity strings are
truncated; query text is never logged by BIAC at this API.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aidp_common import REPORTS_DIR, BiacClient, load_settings

DEMO_USERS = {"gov-admin", "gov-fraud", "gov-biz", "gov-tha", "gov-audit"}
DEMO_MARKERS = ("gov_demo", "gov_", "gov-")


def demo_relevant(row) -> bool:
    blob = " ".join(str(v) for v in row.values())
    return (row.get("user") in DEMO_USERS
            or any(m in blob for m in DEMO_MARKERS))


def fetch_all(biac, path, cap=2000):
    out, token = [], None
    while len(out) < cap:
        p = f"{path}{'&' if '?' in path else '?'}pageSize=300"
        if token:
            p += f"&pageToken={token}"
        d = biac.request("GET", p)
        rows = d.get("result", [])
        out.extend(rows)
        token = d.get("nextPageToken")
        if not token or not rows:
            break
    return out


def clip(v, n=160):
    s = "" if v is None else str(v)
    return s if len(s) <= n else s[: n - 3] + "..."


def main():
    settings = load_settings()
    biac = BiacClient(settings)
    REPORTS_DIR.mkdir(exist_ok=True)

    print("Fetching BIAC access logs ...")
    access = fetch_all(biac, "/audit/accessLogs")
    print(f"  {len(access)} access events total")
    print("Fetching BIAC change logs ...")
    changes = fetch_all(biac, "/audit/changeLogs")
    print(f"  {len(changes)} change events total")

    demo_access = [r for r in access if demo_relevant(r)]
    demo_changes = [r for r in changes if demo_relevant(r)]
    print(f"  {len(demo_access)} demo-relevant access events")
    print(f"  {len(demo_changes)} demo-relevant change events")

    a_csv = REPORTS_DIR / "audit_access_evidence.csv"
    with open(a_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "user", "enabled_roles", "action",
                    "entity_category", "entity", "result", "query_id"])
        for r in demo_access:
            w.writerow([r.get("atTime"), r.get("user"),
                        "|".join(r.get("enabledRoles") or []),
                        r.get("action"), r.get("entityCategory"),
                        clip(r.get("entity")), r.get("accessResult"),
                        r.get("queryId", "")])

    c_csv = REPORTS_DIR / "audit_change_evidence.csv"
    with open(c_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "user", "enabled_roles", "operation",
                    "entity_kind", "entity", "what_changed", "affected_role"])
        for r in demo_changes:
            w.writerow([r.get("atTime"), r.get("user"),
                        "|".join(r.get("enabledRoles") or []),
                        r.get("operation"), r.get("entityKind"),
                        clip(r.get("entity")), clip(r.get("whatChanged")),
                        r.get("affectedRole", "")])

    # summary: per-user allow/deny counts + interesting events
    from collections import Counter
    per_user = Counter((r.get("user"), r.get("accessResult"))
                       for r in demo_access)
    denied = [r for r in demo_access if r.get("accessResult") != "ALLOW"]

    md = ["# Audit evidence summary (sanitized)", "",
          "Source: SEP BIAC REST API `/audit/accessLogs`, `/audit/changeLogs`.",
          "Events filtered to demo identities/objects. Query text and",
          "credentials are never present in these APIs.", "",
          "## Access decisions by user", "",
          "| user | ALLOW | DENY |", "| --- | --- | --- |"]
    for u in sorted(DEMO_USERS | {r.get("user") for r in demo_access}):
        a = per_user.get((u, "ALLOW"), 0)
        d = sum(v for (uu, res), v in per_user.items()
                if uu == u and res != "ALLOW")
        if a or d:
            md.append(f"| {u} | {a} | {d} |")
    md += ["", "## Denied operations (sample)", "",
           "| time | user | action | entity |", "| --- | --- | --- | --- |"]
    for r in denied[:15]:
        md.append(f"| {r.get('atTime')} | {r.get('user')} | {r.get('action')} "
                  f"| {clip(r.get('entity'), 70)} |")
    md += ["", "## Policy changes (sample)", "",
           "| time | operation | kind | entity | role |",
           "| --- | --- | --- | --- | --- |"]
    for r in demo_changes[:15]:
        md.append(f"| {r.get('atTime')} | {r.get('operation')} "
                  f"| {r.get('entityKind')} | {clip(r.get('entity'), 50)} "
                  f"| {r.get('affectedRole', '')} |")

    (REPORTS_DIR / "audit_evidence_summary.md").write_text("\n".join(md))
    print(f"\nWrote {a_csv.name}, {c_csv.name}, audit_evidence_summary.md")
    print("\n--- allow/deny by user ---")
    for u in sorted({r.get('user') for r in demo_access}):
        a = per_user.get((u, "ALLOW"), 0)
        d = sum(v for (uu, res), v in per_user.items() if uu == u and res != "ALLOW")
        print(f"  {u:10} allow={a:3} deny={d:3}")


if __name__ == "__main__":
    main()
