# Identity and role mapping

## Chain

```text
Keycloak user  ->  Keycloak group  ->  BIAC role assignment  ->  grants/masks/filters
```

SEP resolves Keycloak group membership at login (verified with
`SHOW CURRENT ROLES` for each demo user). No user-level assignments are
used - everything flows through groups, matching enterprise IdP practice.

## Mapping

| Keycloak user | Keycloak group | BIAC role | Business purpose |
| --- | --- | --- | --- |
| `gov-admin` | `/governance-admins` | `gov_data_admin` | manage + verify governed data |
| `gov-fraud` | `/fraud-analysts` | `gov_fraud_analyst` | fraud/high-risk investigation |
| `gov-biz` | `/business-analysts` | `gov_business_analyst` | aggregate insights only |
| `gov-tha` | `/thailand-analysts` | `gov_thailand_analyst` | Thailand records only |
| `gov-audit` | `/data-auditors` | `gov_auditor` | governance/audit metadata |

Supporting identities:

| Identity | Role | Use |
| --- | --- | --- |
| `dv-admin` | `sysadmin` (admin option, not enabled by default) | all setup scripts; BIAC REST + `SET ROLE sysadmin` SQL |
| `jirawut` | `jirawut_demo` | owner of the `SECURITY DEFINER` summary view |
| `gov-audit` / auditors | - | verify audit evidence |

## Passwords

- All secrets come from `.env` / environment (`AIDP_ADMIN_PASSWORD`,
  `AIDP_DEMO_USER_PASSWORD`, `AIDP_VIEW_OWNER_PASSWORD`) - never committed.
- The Keycloak `ddae` realm enforces **minimum password length 9**;
  `P@ssword` (8 chars) is rejected, so the demo password in
  `AIDP_DEMO_USER_PASSWORD` was set to a compliant 9+ character value.
  Presenters get the actual value from `.env` - it is never committed.

## Provisioning status

Users and groups were pre-provisioned in Keycloak; passwords were reset
through the Keycloak admin API (realm admin via `admin-cli` token).
Group->role assignments were created through the BIAC REST API by
`configure_rbac.py`, which also removed the broad `jirawut_demo` /
`pystarburst` scaffolding assignments from the five demo groups.

See `reports/demo_user_readiness.md` for per-user verification output.
