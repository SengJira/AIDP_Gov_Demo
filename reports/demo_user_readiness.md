# Demo user readiness

Verified by connecting to AIDP as each identity (Basic auth) and
reading `SHOW CURRENT ROLES`. Generated during validation.

| user | login | resolved BIAC roles |
| --- | --- | --- |
| gov-admin | OK | gov_data_admin, public |
| gov-fraud | OK | gov_fraud_analyst, public |
| gov-biz | OK | gov_business_analyst, public |
| gov-tha | OK | gov_thailand_analyst, public |
| gov-audit | OK | gov_auditor, public |

## Notes

- Keycloak realm `ddae` minimum password length is 9; the demo
  password is stored in `AIDP_DEMO_USER_PASSWORD` and meets the
  9-char minimum (deviation from the requested `P@ssword`, which
  the realm rejects).
- Group->role assignment is via BIAC group subjects - no
  user-level role assignments exist.
- Scaffolding roles `jirawut_demo`/`pystarburst` were removed
  from the five demo groups (see rollback files).