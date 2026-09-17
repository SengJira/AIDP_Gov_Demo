# Presenter checklist

## Before the demo

- [ ] `.env` filled in (`cp .env.example .env`) - `AIDP_ADMIN_PASSWORD`,
      `AIDP_DEMO_USER_PASSWORD`, `AIDP_VIEW_OWNER_PASSWORD`, `OM_ADMIN_PASSWORD`.
- [ ] Demo password (in `AIDP_DEMO_USER_PASSWORD`) is 9+ chars - realm
      minimum is 9, `P@ssword` is rejected. Confirm each `gov-*` login works.
- [ ] `python scripts/validate_demo.py` -> 19/19 PASS.
- [ ] `python scripts/test_role_access.py` -> 36/36 PASS (regenerates
      `reports/access_test_*`).
- [ ] `python scripts/collect_audit_evidence.py` run *after* the test
      suite so allow/deny events exist.
- [ ] Six terminals/panes prepared, one per identity:
  - `gov-admin`, `gov-fraud`, `gov-biz`, `gov-tha`, `gov-audit`, `dv-admin`
- [ ] OpenMetadata tab open at
      `http://10.246.25.115:8585` -> `js_aidp_starburst` ->
      `js_financial_ice` -> `gov_demo`.
- [ ] SEP UI tab open at `https://ddae.lab9bgp.com/ui` (signed in as
      `dv-admin`, sysadmin enabled) for Access Control + Audit log screens.
- [ ] `sql/09_validation_queries.sql` open for copy/paste.

## If something fails mid-demo

| Symptom | Fix |
| --- | --- |
| `Access Denied` on catalogs as `dv-admin` | `SET ROLE sysadmin` / send `X-Trino-Role` header |
| `View owner does not have sufficient privileges` | re-run `sql/06_apply_grants.sql` grant-option grant for `jirawut_demo` |
| gov user sees scaffolding-wide access | `configure_rbac.py --apply` removed `jirawut_demo`/`pystarburst` - verify `SHOW CURRENT ROLES` |
| Inverted filter results (fraud sees clean rows) | filters are exclusion predicates - re-apply `configure_row_filters.py --apply` |
| Mask expression rejected | must return the column's type; use `array_join(repeat('*',n),'')`, not `repeat()` |
| `gov-*` login fails | Keycloak min length 9 - check `AIDP_DEMO_USER_PASSWORD` in `.env` |

## Reset after the demo

```bash
python scripts/reset_demo.py --apply                  # policies/roles only
python scripts/reset_demo.py --apply --drop-data      # + gov_demo objects
python scripts/reset_demo.py --apply --restore-scaffolding  # restore pre-demo groups
```
