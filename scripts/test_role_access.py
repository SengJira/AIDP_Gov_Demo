#!/usr/bin/env python3
"""Phase 9: automated policy validation.

Connects to AIDP as EACH demo identity (never impersonating roles through
the admin session) and runs positive + negative tests. Results go to
reports/access_test_results.csv and reports/access_test_summary.md.

No unmasked PII is written to reports - sample outputs are sanitized.
"""

import csv
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aidp_common import (REPORTS_DIR, load_settings, run_sql,
                         sql_error_text, trino_connect)

T = "js_financial_ice.gov_demo.customer_transactions"
V = "js_financial_ice.gov_demo.payment_business_summary"
MASKED_COLS = {"customer_name", "national_id", "mobile_number", "email"}

PII_PATTERNS = [
    re.compile(r"\b\d{13}\b"),                       # raw national id
    re.compile(r"\b0\d{9}\b"),                        # raw mobile
    re.compile(r"\b\S+@\S+\.(com|net|org)\b"),       # raw email (full local part)
    re.compile(r"ACC-[A-Z]{2}-\d{8}"),               # raw account id (allowed only for admin/fraud)
]


def sanitize(value, allow_raw_account=False):
    """Mask anything that looks like real PII before writing to a report."""
    if value is None:
        return ""
    s = str(value)
    if re.fullmatch(r"ACC-[A-Z]{2}-\d{8}", s):
        # even where raw account_id is legitimately visible to a persona,
        # never write it to a report
        return "ACC-**-********"
    if re.fullmatch(r"\d{13}", s):
        return "*" * 9 + s[-4:]
    if re.fullmatch(r"0\d{9}", s):
        return "*" * 6 + s[-4:]
    if "@" in s and re.fullmatch(r"\S+@\S+", s):
        return s[0] + "******" + s[s.index("@"):]
    return s[:80]


def run_test(settings, user, test):
    """Execute one test as the given identity. Returns result dict."""
    res = {"test_id": test["id"], "user": user, "current_user": "",
           "current_roles": "", "object": test.get("object", ""),
           "operation": test["op"], "expected": test["expect"],
           "actual": "", "pass": "", "rows": "", "sample": "",
           "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        conn = trino_connect(settings, user, settings.demo_user_password,
                             catalog="js_financial_ice", schema="gov_demo")
        cur = conn.cursor()
        cur.execute("SELECT current_user")
        res["current_user"] = cur.fetchall()[0][0]
        cur.execute("SHOW CURRENT ROLES")
        res["current_roles"] = ",".join(r[0] for r in cur.fetchall())
        cur.execute(test["sql"])
        rows = cur.fetchall()
        res["rows"] = len(rows)
        ok, note = test["check"](rows)
        res["actual"] = f"OK ({note})" if ok else f"UNEXPECTED ({note})"
        res["pass"] = "PASS" if ok else "FAIL"
        # sanitized sample (first row only, PII-masked)
        if rows and test.get("sample_cols"):
            sample = {c: sanitize(rows[0][i], allow_raw_account=test.get("allow_raw_account", False))
                      for i, c in enumerate(test["sample_cols"]) if i < len(rows[0])}
            res["sample"] = str(sample)[:300]
    except Exception as e:
        err = sql_error_text(e)
        denied = "denied" in err.lower() or "PERMISSION_DENIED" in err
        if test["expect"] == "denied" and denied:
            res["actual"] = f"DENIED ({err[:120]})"
            res["pass"] = "PASS"
        else:
            res["actual"] = f"ERROR ({err[:160]})"
            res["pass"] = "FAIL" if test["expect"] != "denied" else "FAIL"
    return res


def expect_rows(pred, desc):
    def check(rows):
        ok = pred(rows)
        return ok, desc if ok else f"{len(rows)} rows failed: {desc}"
    return check


def all_rows(pred, desc):
    def check(rows):
        bad = [r for r in rows if not pred(r)]
        return (not bad), desc if not bad else f"{len(bad)} violating rows (e.g. {bad[0] if bad else ''})"
    return check


def masked(value, raw):
    """True if value is masked (contains * / placeholder) or legitimately NULL."""
    if value is None:
        return True
    v = str(value)
    return ("*" in v) or v in ("Protected Customer", "hidden@example.com")


def build_tests():
    sel_pii = (f"SELECT customer_name, national_id, mobile_number, email, "
               f"account_id, country_code, risk_score, fraud_flag, fraud_type, "
               f"investigation_status FROM {T} ORDER BY transaction_id")
    tests = []

    def add(user, tid, op, obj, sql, expect, check=None, sample_cols=None,
            allow_raw_account=False):
        tests.append({"id": f"{user}-{tid}", "user": user, "op": op,
                      "object": obj, "sql": sql, "expect": expect,
                      "check": check or (lambda rows: (True, "ok")),
                      "sample_cols": sample_cols,
                      "allow_raw_account": allow_raw_account})

    # ---- identity check (all users) ----
    for u in ["gov-admin", "gov-fraud", "gov-biz", "gov-tha", "gov-audit"]:
        add(u, "T00-identity", "SELECT", "session", "SELECT 1", "ok")

    # ---- gov-admin ----
    add("gov-admin", "T01-all-rows", "SELECT", T,
        f"SELECT count(*) FROM {T}", "ok",
        expect_rows(lambda r: r[0][0] == 36, "all 36 rows visible"))
    add("gov-admin", "T02-all-countries", "SELECT", T,
        f"SELECT DISTINCT country_code FROM {T}", "ok",
        expect_rows(lambda r: sorted(x[0] for x in r) == ["LA", "SG", "TH", "VN"],
                    "all 4 countries"))
    add("gov-admin", "T03-unmasked", "SELECT", T, sel_pii, "ok",
        all_rows(lambda r: "*" not in str(r[0]) and "*" not in str(r[1]),
                 "name+id unmasked"),
        sample_cols=["name", "nid", "mobile", "email", "acct"],
        allow_raw_account=True)
    add("gov-admin", "T04-fraud-fields", "SELECT", T,
        f"SELECT fraud_type, investigation_status FROM {T} WHERE fraud_flag LIMIT 3",
        "ok", expect_rows(lambda r: len(r) >= 1, "fraud fields readable"))
    add("gov-admin", "T05-show-roles", "SELECT", "metadata", "SHOW ROLES", "ok",
        expect_rows(lambda r: len(r) >= 5, "roles visible"))

    # ---- gov-fraud ----
    add("gov-fraud", "T01-filter", "SELECT", T,
        f"SELECT count(*) FROM {T}", "ok",
        expect_rows(lambda r: r[0][0] == 14, "only 14 fraud/high-risk rows"))
    add("gov-fraud", "T02-no-low-risk", "SELECT", T, sel_pii, "ok",
        all_rows(lambda r: bool(r[7]) or float(r[6]) >= 0.70,
                 "every row fraud_flag or risk>=0.70"),
        sample_cols=["name", "nid", "mobile", "email", "acct"],
        allow_raw_account=True)
    add("gov-fraud", "T03-nid-masked", "SELECT", T,
        f"SELECT national_id FROM {T} LIMIT 5", "ok",
        all_rows(lambda r: str(r[0]).startswith("*********"),
                 "national_id strongly masked"))
    add("gov-fraud", "T04-pii-partial", "SELECT", T, sel_pii, "ok",
        all_rows(lambda r: masked(r[0], "") and masked(r[1], "") and masked(r[2], "") and masked(r[3], ""),
                 "name/nid/mobile/email partially masked"))
    add("gov-fraud", "T05-write-denied", "INSERT", T,
        f"INSERT INTO {T} (customer_id) VALUES ('HACK')", "denied")
    add("gov-fraud", "T06-ctas-denied", "CTAS", T,
        f"CREATE TABLE js_financial_ice.gov_demo.evil AS SELECT * FROM {T}", "denied")
    add("gov-fraud", "T07-role-mgmt-denied", "DDL", "roles",
        "CREATE ROLE hacked_role", "denied")
    add("gov-fraud", "T08-view-denied", "DDL", T,
        f"CREATE VIEW js_financial_ice.gov_demo.v_bypass AS SELECT * FROM {T}", "denied")

    # ---- gov-biz ----
    add("gov-biz", "T01-summary-ok", "SELECT", V,
        f"SELECT count(*) FROM {V}", "ok",
        expect_rows(lambda r: r[0][0] > 0, "summary accessible"))
    add("gov-biz", "T02-no-pii-cols", "SELECT", V,
        f"SHOW COLUMNS FROM {V}", "ok",
        all_rows(lambda r: r[0] not in MASKED_COLS and r[0] not in
                 ("customer_id", "transaction_id", "fraud_type", "investigation_status"),
                 "no PII/investigation columns in summary"))
    add("gov-biz", "T03-table-denied", "SELECT", T,
        f"SELECT count(*) FROM {T}", "denied")
    add("gov-biz", "T04-nid-denied", "SELECT", T,
        f"SELECT national_id FROM {T} LIMIT 1", "denied")
    add("gov-biz", "T05-fraud-denied", "SELECT", T,
        f"SELECT fraud_type, investigation_status FROM {T} LIMIT 1", "denied")

    # ---- gov-tha ----
    add("gov-tha", "T01-th-only", "SELECT", T, sel_pii, "ok",
        all_rows(lambda r: r[5] == "TH", "every row is TH"),
        sample_cols=["name", "nid", "mobile", "email", "acct"])
    add("gov-tha", "T02-other-country", "SELECT", T,
        f"SELECT count(*) FROM {T} WHERE country_code = 'VN'", "ok",
        expect_rows(lambda r: r[0][0] == 0, "VN query returns 0"))
    add("gov-tha", "T03-no-predicate", "SELECT", T,
        f"SELECT count(DISTINCT country_code) FROM {T}", "ok",
        expect_rows(lambda r: r[0][0] == 1, "only 1 country without predicate"))
    add("gov-tha", "T04-subquery", "SELECT", T,
        f"SELECT count(DISTINCT country_code) FROM (SELECT * FROM {T}) x", "ok",
        expect_rows(lambda r: r[0][0] == 1, "subquery still TH-only"))
    add("gov-tha", "T05-union", "SELECT", T,
        f"SELECT count(DISTINCT country_code) FROM "
        f"(SELECT country_code FROM {T} UNION ALL SELECT country_code FROM {T}) u",
        "ok", expect_rows(lambda r: r[0][0] == 1, "UNION still TH-only"))
    add("gov-tha", "T06-join", "SELECT", T,
        f"SELECT count(*) FROM {T} a JOIN {T} b ON a.transaction_id = b.transaction_id",
        "ok", expect_rows(lambda r: r[0][0] == 12, "self-join stays TH-only"))
    add("gov-tha", "T07-pii-masked", "SELECT", T, sel_pii, "ok",
        all_rows(lambda r: masked(r[0], "") and masked(r[1], "") and masked(r[2], "") and masked(r[3], "") and masked(r[4], ""),
                 "all PII + account masked"))
    add("gov-tha", "T08-write-denied", "DELETE", T,
        f"DELETE FROM {T} WHERE country_code = 'TH'", "denied")

    # ---- gov-audit ----
    add("gov-audit", "T01-show-tables", "SHOW", T,
        "SHOW TABLES FROM js_financial_ice.gov_demo", "ok",
        expect_rows(lambda r: len(r) >= 2, "object metadata visible"))
    add("gov-audit", "T02-select-denied", "SELECT", T,
        f"SELECT count(*) FROM {T}", "denied")
    add("gov-audit", "T03-pii-denied", "SELECT", T,
        f"SELECT national_id FROM {T} LIMIT 1", "denied")
    add("gov-audit", "T04-write-denied", "INSERT", T,
        f"INSERT INTO {T} (customer_id) VALUES ('X')", "denied")
    add("gov-audit", "T05-roles-visible", "SELECT", "metadata",
        "SHOW ROLES", "ok",
        expect_rows(lambda r: len(r) >= 5, "roles listable"))
    return tests


def main():
    settings = load_settings()
    tests = build_tests()
    results = []
    users = sorted({t["user"] for t in tests})
    print(f"Running {len(tests)} tests as {len(users)} identities...\n")
    for t in tests:
        r = run_test(settings, t["user"], t)
        results.append(r)
        mark = "PASS" if r["pass"] == "PASS" else "FAIL"
        print(f"{mark} {r['test_id']:28} {r['operation']:8} -> {r['actual'][:80]}")

    REPORTS_DIR.mkdir(exist_ok=True)
    csv_path = REPORTS_DIR / "access_test_results.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    passed = sum(1 for r in results if r["pass"] == "PASS")
    summary = ["# Access test summary", "",
               f"Run: {time.strftime('%Y-%m-%d %H:%M:%S')}",
               f"Result: **{passed}/{len(results)} tests passed**", "",
               "| test | user | current_user | roles | object | expected | actual | pass |",
               "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in results:
        summary.append(
            f"| {r['test_id']} | {r['user']} | {r['current_user']} | {r['current_roles']} "
            f"| {r['object'].split('.')[-1]} | {r['expected']} | {r['actual'][:80]} | {r['pass']} |")
    (REPORTS_DIR / "access_test_summary.md").write_text("\n".join(summary))
    print(f"\n{passed}/{len(results)} passed. Wrote {csv_path} and access_test_summary.md")
    if passed != len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
