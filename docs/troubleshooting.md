# Troubleshooting

Verified quirks of this AIDP/SEP 479-e.4 deployment and their fixes.

## `Access Denied: Cannot show roles` / cannot see catalogs as `dv-admin`

`dv-admin` holds `sysadmin` with admin option but it is **not enabled by
default**. SQL: `SET ROLE sysadmin`. REST: header
`X-Trino-Role: system=ROLE{sysadmin}`. All scripts send the header.

## `View owner does not have sufficient privileges` on SECURITY DEFINER views

SEP evaluates the view owner's privileges **and requires GRANT OPTION**
on the underlying objects. The summary view is owned by `jirawut` via
`jirawut_demo`, which was given `ALLOW_WITH_GRANT_OPTION` SELECT on
`gov_demo.*` (see `sql/06_apply_grants.sql`). A plain `ALLOW` SELECT is
not sufficient.

## Row filter returns the opposite of what was intended

BIAC row-filter expressions are **exclusion** predicates: rows where the
expression is TRUE are hidden. Write visibility rules inverted:

- keep fraud rows -> `NOT (fraud_flag OR risk_score >= 0.70)`
- keep TH rows -> `country_code <> 'TH'`

## Mask expression rejected / `Cannot cast array(varchar(1)) to varchar`

- Trino `repeat()` returns an **array**, not a string - use
  `array_join(repeat('*', n), '')`.
- The mask must return the column's own type; regex helpers were rejected
  by the BIAC validator in this build - stick to `CASE`, `length`,
  `substr`, `strpos`.
- Always NULL-safe: `CASE WHEN "@column" IS NULL THEN NULL ELSE ...`.

## `Schema 'gov_demo' location cannot be determined`

Iceberg schemas on this catalog need an explicit location:
`CREATE SCHEMA ... WITH (location = 's3://js-demo/warehouse/gov_demo')`.

## `gov-*` login fails / password rejected on reset

Keycloak realm `ddae` enforces minimum password length **9**.
`P@ssword` (8 chars) is rejected - the demo password stored in
`AIDP_DEMO_USER_PASSWORD` must be 9+ characters.

## A `gov-*` user sees far more than the role allows

They are probably still inheriting `jirawut_demo` / `pystarburst` through
a group assignment - both grant broad catalog access.
`configure_rbac.py --apply` removes those assignments from the five demo
groups; check `SHOW CURRENT ROLES` as the user. Restore with
`reset_demo.py --restore-scaffolding` if other demos depended on them.

## `Role not found ... entityId: 0` during apply

Role IDs must be resolved **after** role creation, not at plan time -
`configure_rbac.py` resolves them lazily at execution. Re-run is safe;
everything is idempotent.

## Stale `Access Denied` right after a change

BIAC changes take effect on the next query but old sessions/connections
can cache authorization. Open a fresh connection before verifying.

## OpenMetadata table missing or enrichment not visible

- New schema objects appear only after the `js_aidp_starburst_metadata`
  ingestion pipeline runs - trigger it via the OM UI or API
  (`POST /services/ingestionPipelines/trigger/{id}`).
- Column tags require `fields=columns` (or the `tags` field) on
  `GET /tables/{id}` to be returned by the API.

## Audit log shows fewer events than expected

`accessLogs`/`changeLogs` are server-side and appear almost immediately,
but the list is paginated (`pageToken`); `collect_audit_evidence.py`
walks all pages. A second test run adds more entries - the report is a
point-in-time snapshot.
