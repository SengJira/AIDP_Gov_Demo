# Manual policy steps (UI / SQL / API equivalents)

Everything the scripts do can be reproduced manually through three
supported surfaces. Nothing requires Kubernetes or appliance access.

## 1. AIDP / SEP web UI

`https://ddae.lab9bgp.com/ui` - sign in through Keycloak SSO as `dv-admin`,
then enable the `sysadmin` role in the session.

- **Roles & grants**: *Access control -> Roles*. Create the `gov_*` roles,
  add privileges (catalog -> schema -> table -> column), and assign the
  roles to the Keycloak **groups** (subject type GROUP).
- **Column masks**: *Access control -> Column masks*. Create the mask
  expression (uses the `"@column"` placeholder), then attach it to a
  role + catalog/schema/table/column.
- **Row filters**: *Access control -> Row filters*. Create the filter
  expression - remember it is an **exclusion** predicate (TRUE hides the
  row) - and attach to a role + table.
- **Audit**: *Access control -> Audit log* shows the same allow/deny and
  change events the REST API returns.

## 2. BIAC REST API (what the scripts use)

Base: `https://ddae.lab9bgp.com/api/v1/biac`
Auth: Basic `dv-admin` + header `X-Trino-Role: system=ROLE{sysadmin}`.
OpenAPI spec: `https://ddae.lab9bgp.com/api/v1/openApi`.

| Task | Endpoint |
| --- | --- |
| List/create/delete roles | `GET/POST /roles`, `DELETE /roles/{id}` |
| Role grants | `GET/POST /roles/{id}/grants`, `DELETE .../grants/{gid}` |
| Group assignments | `GET/POST/DELETE /subjects/groups/{name}/assignments` |
| Mask expressions | `GET/POST/DELETE /expressions/columnMask` |
| Filter expressions | `GET/POST/DELETE /expressions/rowFilter` |
| Attach masks/filters | `POST /roles/{id}/columnMasks`, `POST /roles/{id}/rowFilters` |
| Access audit | `GET /audit/accessLogs` |
| Change audit | `GET /audit/changeLogs` |

Grant entity examples:

```json
{"catalog":"js_financial_ice"}
{"catalog":"js_financial_ice","schema":"gov_demo"}
{"catalog":"js_financial_ice","schema":"gov_demo","table":"customer_transactions"}
{"catalog":"js_financial_ice","schema":"gov_demo","table":"customer_transactions","column":"national_id"}
```

Effects: `ALLOW`, `DENY`, `ALLOW_WITH_GRANT_OPTION`. For schema-scoped
`SHOW` visibility grant `SHOW` on the schema entity; `SELECT` on a table
grants column reads; masks/filters layer on top per-role.

## 3. SQL (role session)

```sql
SET ROLE sysadmin;

-- catalog + schema visibility
SHOW ROLES;
SHOW ROLE GRANTS gov_fraud_analyst;

-- view ownership for SECURITY DEFINER views must hold GRANT OPTION
GRANT SELECT ON js_financial_ice.gov_demo.* TO jirawut_demo WITH GRANT OPTION;
```

Notes verified on 479-e.4:

- `CREATE ROLE`/`DROP ROLE` work via SQL, but group assignments, masks,
  row filters and audit are **API/UI-only** - there is no SQL DDL for them.
- `dv-admin` must `SET ROLE sysadmin` per session; the role is not
  enabled by default.
- `SECURITY DEFINER` views require the owner to hold the underlying
  privileges **with grant option**, or other users get
  `View owner does not have sufficient privileges`.

## 4. Keycloak (identity)

`https://ddlh.lab9bgp.com/auth` realm `ddae`. Users/groups already exist;
password resets use the realm admin API (`admin-cli` token in the `ddae`
realm). Minimum password length is 9.

## 5. OpenMetadata

`http://10.246.25.115:8585` - enrich via UI (*Explore -> table ->
Description/Tags/Domain/Owner*) or the REST API used by
`configure_openmetadata.py` (JSON-Patch on `/tables/{id}`, plus
`PUT /domains/FraudAndRisk/assets/add`). Re-run the
`js_aidp_starburst_metadata` ingestion pipeline after creating new
schemas so OM discovers them.
