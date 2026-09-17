# Policy capability matrix — AIDP / Starburst Enterprise 479-e.4

Captured 2026-09-17 10:32:23 CDT. Verified live against `https://ddae.lab9bgp.com`.

| Capability | Mechanism | Status | Where |
| --- | --- | --- | --- |
| Catalog access control | BIAC grant on TABLES entity (catalog key) | Confirmed native AIDP/SEP | REST `/api/v1/biac/roles/{id}/grants`, UI, SQL `GRANT` |
| Schema access control | BIAC grant scoped to schema | Confirmed native | same |
| Table/view access control | BIAC grant scoped to table | Confirmed native | same |
| Column-level access | BIAC grant with `columns` list | Confirmed native | REST API / UI |
| Dynamic column masking | BIAC column-mask expression + role attachment | Confirmed native | REST `/api/v1/biac/expressions/columnMask`, `/roles/{id}/columnMasks`; UI Access control > Masks and filters |
| Row-level filtering | BIAC row-filter expression + role attachment | Confirmed native | REST `/api/v1/biac/expressions/rowFilter`, `/roles/{id}/rowFilters`; UI |
| Role create/drop | SQL `CREATE ROLE`/`DROP ROLE` or REST `/biac/roles` | Confirmed both | SQL + REST |
| Privilege grants | SQL `GRANT ... TO ROLE` (TABLES) or REST | Confirmed both | SQL limited to table privileges; non-TABLES categories via REST |
| Role -> user assignment | REST `/biac/subjects/users/{u}/assignments` | Confirmed native | REST / UI |
| Role -> IdP group assignment | REST `/biac/subjects/groups/{g}/assignments` | Confirmed native; groups resolve at login | REST / UI |
| Audit: access decisions | BIAC access log (ALLOW/DENY/ROW_FILTER/COLUMN_MASK) | Confirmed native | REST `/api/v1/biac/audit/accessLogs`, UI Access control > Audit log |
| Audit: policy changes | BIAC change log | Confirmed native | REST `/api/v1/biac/audit/changeLogs`, UI |
| SQL for masks/filters | not exposed | Unsupported by design | UI/REST only |
| Direct grants to users/groups via SQL | rejected by BIAC | Unsupported | privileges go to roles only |
| Object ownership / `GRANTED BY` | not supported by BIAC | Unsupported | documented SEP limitation |
| Aggregated curated view | `SECURITY DEFINER` view | Confirmed (view mechanism, not native masking) | SQL `CREATE VIEW` |

Legend: "Confirmed native" = tested live on this cluster; "Unsupported" =
rejected or not offered by the product on this version.
