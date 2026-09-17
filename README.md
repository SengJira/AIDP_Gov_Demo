# AIDP Data Governance Showcase

**Protecting Customer and Payment Data with AIDP Governance**

A repeatable demonstration of least-privilege governance on Dell AIDP /
Starburst Enterprise (SEP 479-e.4) using **native built-in access control
(BIAC)**: roles, grants, dynamic column masks, row filters, and audit logs -
validated end-to-end with five real Keycloak identities.

The same SQL query returns different results depending on who runs it:

| Persona | `SELECT ... FROM customer_transactions` |
| --- | --- |
| `gov-admin` (gov_data_admin) | all 36 rows, unmasked |
| `gov-fraud` (gov_fraud_analyst) | 14 fraud/high-risk rows, partial masks |
| `gov-biz` (gov_business_analyst) | denied - aggregate view only |
| `gov-tha` (gov_thailand_analyst) | 12 `TH` rows only, strong masks |
| `gov-audit` (gov_auditor) | denied - metadata only |

## Environment

| Item | Value |
| --- | --- |
| AIDP endpoint | `https://ddae.lab9bgp.com` |
| Engine | Starburst Enterprise 479-e.4, BIAC |
| Identity | Keycloak realm `ddae` (`https://ddlh.lab9bgp.com/auth`) |
| OpenMetadata | `http://10.246.25.115:8585`, service `js_aidp_starburst` |
| Demo objects | `js_financial_ice.gov_demo.customer_transactions` (36 synthetic rows), `...gov_demo.payment_business_summary` (aggregate view) |

All demo data is synthetic. Original banking datasets are never modified.

## Quick start

```bash
cp .env.example .env       # fill in secrets - never commit .env

python scripts/inspect_environment.py        # Phase 1 reports

python scripts/setup_demo_data.py --dry-run
python scripts/setup_demo_data.py --apply    # Phase 2: schema/table/view

python scripts/configure_rbac.py --apply     # Phases 3+5: roles/grants/groups
python scripts/configure_masking.py --apply  # Phase 6: column masks
python scripts/configure_row_filters.py --apply   # Phase 7: row filters
python scripts/configure_openmetadata.py --apply  # Phase 8: tags/domain/owner

python scripts/test_role_access.py           # Phase 9: 36 per-identity tests
python scripts/collect_audit_evidence.py     # Phase 10: sanitized audit
python scripts/validate_demo.py              # all success criteria
```

Every configuration script is **dry-run by default** and writes a rollback
file to `reports/` before changing anything.

## Rollback

```bash
python scripts/reset_demo.py            # dry-run teardown plan
python scripts/reset_demo.py --apply    # remove masks/filters/grants/roles/assignments
python scripts/reset_demo.py --apply --drop-data             # + drop gov_demo objects
python scripts/reset_demo.py --apply --restore-scaffolding   # + restore pre-demo group roles
```

`sql/99_cleanup.sql` is the SQL-only equivalent for schema objects.

## Layout

- `config/` - personas, role mapping, masking/filter policies, OM plan
- `sql/` - reference SQL executed by the scripts (also runnable manually)
- `scripts/` - automation (all dry-run default)
- `reports/` - generated evidence: environment assessment, access tests,
  audit evidence, validation, rollback plans
- `docs/` - architecture, security design, presenter workflow, runbooks

## Key docs

- [docs/architecture.md](docs/architecture.md) - how BIAC enforcement works here
- [docs/security_design.md](docs/security_design.md) - roles, grants, masks, filters
- [docs/identity_role_mapping.md](docs/identity_role_mapping.md) - Keycloak -> BIAC
- [docs/demo_script.md](docs/demo_script.md) - 15-minute presenter flow
- [docs/manual_policy_steps.md](docs/manual_policy_steps.md) - UI equivalents
- [docs/troubleshooting.md](docs/troubleshooting.md) - known quirks + fixes
- [docs/spark_connect.md](docs/spark_connect.md) - DDPE Spark Connect access + governance boundary

## Spark / notebooks

`notebooks/ddpe_spark_governance.ipynb` connects to the DDPE Spark Connect
instance `jirawut-demo` and contrasts direct storage access (unenforced)
with governed Trino access. Requires `scripts/start_spark_proxy.sh`
running first on this dev host - see
[docs/spark_connect.md](docs/spark_connect.md).
