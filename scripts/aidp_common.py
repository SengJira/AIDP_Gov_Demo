"""Shared client library for the AIDP Data Governance Showcase.

All credentials come from the environment (optionally seeded from a local
``.env`` file that is never committed). Nothing in this module prints or logs
secret values.

Supported control surfaces (discovered against the lab appliance):

* Trino/SEP SQL over HTTPS (Basic auth) -- DDL, DML, SHOW, SET ROLE.
* Starburst Enterprise built-in access control (BIAC) REST API at
  ``https://<host>/api/v1/biac/*`` -- roles, grants, column masks, row
  filters, role assignments, audit logs. Requires the
  ``X-Trino-Role: system=ROLE{sysadmin}`` header for privileged calls.
* Keycloak Admin REST API (realm ``ddae``) -- identity management only.
* OpenMetadata REST API -- governance metadata enrichment.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import requests

log = logging.getLogger("aidp-gov")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
ENV_FILE = PROJECT_ROOT / ".env"

DEFAULT_CA_BUNDLE = "/home/kiran/jirawut-demo/.certs/devin-ca-bundle.pem"
SYSADMIN_HEADER = "system=ROLE{sysadmin}"


class ConfigError(Exception):
    pass


def load_env(path: Path = ENV_FILE) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def env_get(env: dict, name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name) or env.get(name) or default
    if required and not value:
        raise ConfigError(f"{name} is not set (export it or add it to {ENV_FILE})")
    return value or ""


@dataclass(frozen=True)
class Settings:
    endpoint: str
    host: str
    admin_user: str
    admin_password: str
    demo_user_password: str
    verify: str  # path to CA bundle or bool-ish
    keycloak_url: str
    keycloak_realm: str
    om_base: str
    om_service: str
    om_admin_email: str
    om_admin_password: str

    @property
    def api_base(self) -> str:
        return f"{self.endpoint.rstrip('/')}/api/v1"

    @property
    def trino_verify(self):
        if self.verify.lower() in ("false", "0", "no"):
            return False
        return self.verify


def load_settings() -> Settings:
    env = load_env()
    endpoint = env_get(env, "AIDP_ENDPOINT", "https://ddae.lab9bgp.com").rstrip("/")
    host = endpoint.split("://", 1)[-1].split("/")[0]
    verify = env_get(env, "AIDP_CA_BUNDLE", DEFAULT_CA_BUNDLE)
    if env_get(env, "AIDP_VERIFY_TLS", "true").lower() in ("false", "0", "no"):
        verify = "false"
    return Settings(
        endpoint=endpoint,
        host=host,
        admin_user=env_get(env, "AIDP_ADMIN_USER", "dv-admin"),
        admin_password=env_get(env, "AIDP_ADMIN_PASSWORD", required=True),
        demo_user_password=env_get(env, "AIDP_DEMO_USER_PASSWORD", required=True),
        verify=verify,
        keycloak_url=env_get(env, "KEYCLOAK_URL", "https://ddlh.lab9bgp.com/auth").rstrip("/"),
        keycloak_realm=env_get(env, "KEYCLOAK_REALM", "ddae"),
        om_base=env_get(env, "OM_BASE", "http://10.246.25.115:8585").rstrip("/"),
        om_service=env_get(env, "OM_SERVICE", "js_aidp_starburst"),
        om_admin_email=env_get(env, "OM_ADMIN_EMAIL", "admin@open-metadata.org"),
        om_admin_password=env_get(env, "OM_ADMIN_PASSWORD", ""),
    )


# ---------------------------------------------------------------------------
# Trino / SEP SQL
# ---------------------------------------------------------------------------

def trino_connect(settings: Settings, user: str, password: str,
                  catalog: str = "system", schema: str = "information_schema",
                  role: str | None = None, source: str = "aidp-gov-showcase"):
    """Open a trino.dbapi connection. If ``role`` is given, SET ROLE is issued."""
    import trino.auth
    import trino.dbapi

    conn = trino.dbapi.connect(
        host=settings.host,
        port=443,
        http_scheme="https",
        auth=trino.auth.BasicAuthentication(user, password),
        catalog=catalog,
        schema=schema,
        verify=settings.trino_verify,
        source=source,
        request_timeout=60,
    )
    if role:
        cur = conn.cursor()
        cur.execute(f"SET ROLE {role}")
    return conn


def run_sql(settings: Settings, user: str, password: str, sql: str,
            role: str | None = None, catalog: str = "system",
            schema: str = "information_schema"):
    """Execute one statement, return (columns, rows). Raises on server error."""
    conn = trino_connect(settings, user, password, catalog=catalog, schema=schema, role=role)
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in (cur.description or [])]
    return cols, cur.fetchall()


def run_sql_statements(settings: Settings, user: str, password: str,
                       statements: list[str], role: str | None = None,
                       catalog: str = "system", schema: str = "information_schema"):
    """Run a list of statements on one session; returns list of row-sets."""
    conn = trino_connect(settings, user, password, catalog=catalog, schema=schema, role=role)
    cur = conn.cursor()
    results = []
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        cur.execute(stmt)
        results.append(cur.fetchall())
    return results


def sql_error_text(exc: BaseException) -> str:
    text = str(exc)
    # keep the server message, drop stack noise
    return text.replace("\n", " ")[:400]


# ---------------------------------------------------------------------------
# Starburst BIAC REST API
# ---------------------------------------------------------------------------

class BiacClient:
    """Client for the SEP built-in access control REST API.

    All mutating calls run as the configured user with the sysadmin role
    enabled via the ``X-Trino-Role`` header.
    """

    def __init__(self, settings: Settings, user: str | None = None,
                 password: str | None = None, role: str = "sysadmin"):
        self.settings = settings
        self.user = user or settings.admin_user
        self.session = requests.Session()
        self.session.auth = (self.user, password or settings.admin_password)
        self.session.verify = settings.trino_verify
        if role:
            self.session.headers["X-Trino-Role"] = f"system=ROLE{{{role}}}"
        self.session.headers["Accept"] = "application/json"

    def _url(self, path: str) -> str:
        return f"{self.settings.api_base}/biac{path}"

    def request(self, method: str, path: str, ok=(200, 201, 204), **kw):
        r = self.session.request(method, self._url(path), timeout=60, **kw)
        if r.status_code not in ok:
            raise RuntimeError(f"BIAC {method} {path} -> {r.status_code}: {r.text[:500]}")
        if r.content and r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
        return {}

    def _paged(self, path: str, page_size: int = 300):
        out, token = [], None
        while True:
            sep = "&" if "?" in path else "?"
            p = f"{path}{sep}pageSize={page_size}"
            if token:
                p += f"&pageToken={token}"
            d = self.request("GET", p)
            out.extend(d.get("result", []))
            token = d.get("nextPageToken")
            if not token:
                return out

    # -- roles ------------------------------------------------------------
    def list_roles(self):
        return self._paged("/roles")

    def role_id(self, name: str) -> int | None:
        for r in self.list_roles():
            if r["name"] == name:
                return r["id"]
        return None

    def create_role(self, name: str, description: str = ""):
        return self.request("POST", "/roles", json={"name": name, "description": description})

    def delete_role(self, role_id: int, mode: str = "RESTRICT"):
        return self.request("DELETE", f"/roles/{role_id}?mode={mode}", ok=(200, 204))

    # -- role assignments ---------------------------------------------------
    def list_role_assignments(self, role_id: int):
        return self._paged(f"/roles/{role_id}/assignments")

    def list_subject_assignments(self, kind: str, name: str):
        return self._paged(f"/subjects/{kind}/{quote(name, safe='')}/assignments")

    def assign_role(self, kind: str, name: str, role_id: int, role_admin: bool = False):
        return self.request(
            "POST", f"/subjects/{kind}/{quote(name, safe='')}/assignments",
            json={"roleId": role_id, "roleAdmin": role_admin})

    def delete_assignment(self, kind: str, name: str, assignment_id: int):
        return self.request(
            "DELETE", f"/subjects/{kind}/{quote(name, safe='')}/assignments/{assignment_id}",
            ok=(200, 204))

    # -- grants -------------------------------------------------------------
    def list_grants(self, role_id: int):
        return self._paged(f"/roles/{role_id}/grants")

    def create_grant(self, role_id: int, effect: str, action: str, entity: dict):
        body = {"effect": effect, "action": action, "entity": entity}
        return self.request("POST", f"/roles/{role_id}/grants", json=body)

    def delete_grant(self, role_id: int, grant_id: int):
        return self.request("DELETE", f"/roles/{role_id}/grants/{grant_id}", ok=(200, 204))

    # -- expressions ----------------------------------------------------------
    def list_expressions(self, kind: str):  # kind: columnMask | rowFilter
        return self._paged(f"/expressions/{kind}")

    def expression_id(self, kind: str, name: str) -> int | None:
        for e in self.list_expressions(kind):
            if e["name"] == name:
                return e["id"]
        return None

    def create_expression(self, kind: str, name: str, expression: str, description: str = ""):
        return self.request("POST", f"/expressions/{kind}",
                            json={"name": name, "expression": expression, "description": description})

    def delete_expression(self, kind: str, expr_id: int):
        return self.request("DELETE", f"/expressions/{kind}/{expr_id}", ok=(200, 204))

    # -- role masks / filters ---------------------------------------------------
    def list_role_masks(self, role_id: int):
        return self._paged(f"/roles/{role_id}/columnMasks")

    def add_role_mask(self, role_id: int, entity: dict, expression_id: int):
        return self.request("POST", f"/roles/{role_id}/columnMasks",
                            json={"entity": entity, "expressionId": expression_id})

    def delete_role_mask(self, role_id: int, mask_id: int):
        return self.request("DELETE", f"/roles/{role_id}/columnMasks/{mask_id}", ok=(200, 204))

    def list_role_filters(self, role_id: int):
        return self._paged(f"/roles/{role_id}/rowFilters")

    def add_role_filter(self, role_id: int, entity: dict, expression_id: int):
        return self.request("POST", f"/roles/{role_id}/rowFilters",
                            json={"entity": entity, "expressionId": expression_id})

    def delete_role_filter(self, role_id: int, filter_id: int):
        return self.request("DELETE", f"/roles/{role_id}/rowFilters/{filter_id}", ok=(200, 204))

    # -- audit ------------------------------------------------------------------
    def access_logs(self, page_size: int = 200, start: str | None = None, end: str | None = None):
        path = "/audit/accessLogs"
        sep = "?"
        if start:
            path += f"?startDate={start}"; sep = "&"
        if end:
            path += f"{sep}endDate={end}"
        return self._paged(path, page_size)

    def change_logs(self, page_size: int = 200, start: str | None = None, end: str | None = None):
        path = "/audit/changeLogs"
        sep = "?"
        if start:
            path += f"?startDate={start}"; sep = "&"
        if end:
            path += f"{sep}endDate={end}"
        return self._paged(path, page_size)


# ---------------------------------------------------------------------------
# Keycloak Admin (identity management only)
# ---------------------------------------------------------------------------

class KeycloakAdmin:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._token = None
        self.session = requests.Session()
        self.session.verify = settings.trino_verify

    @property
    def token(self) -> str:
        if not self._token:
            r = self.session.post(
                f"{self.settings.keycloak_url}/realms/{self.settings.keycloak_realm}"
                "/protocol/openid-connect/token",
                data={"grant_type": "password", "client_id": "admin-cli",
                      "username": self.settings.admin_user,
                      "password": self.settings.admin_password},
                timeout=30)
            r.raise_for_status()
            self._token = r.json()["access_token"]
        return self._token

    def _req(self, method: str, path: str, **kw):
        r = self.session.request(
            method,
            f"{self.settings.keycloak_url}/admin/realms/{self.settings.keycloak_realm}{path}",
            headers={"Authorization": f"Bearer {self.token}"}, timeout=30, **kw)
        if r.status_code == 401:  # refresh once
            self._token = None
            r = self.session.request(
                method,
                f"{self.settings.keycloak_url}/admin/realms/{self.settings.keycloak_realm}{path}",
                headers={"Authorization": f"Bearer {self.token}"}, timeout=30, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"Keycloak {method} {path} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    def find_user(self, username: str) -> dict | None:
        users = self._req("GET", f"/users?username={username}&exact=true")
        return users[0] if users else None

    def user_groups(self, user_id: str):
        return self._req("GET", f"/users/{user_id}/groups")

    def reset_password(self, user_id: str, password: str):
        self._req("PUT", f"/users/{user_id}/reset-password",
                  json={"type": "password", "value": password, "temporary": False})

    def list_groups(self):
        return self._req("GET", "/groups")


# ---------------------------------------------------------------------------
# OpenMetadata
# ---------------------------------------------------------------------------

class OmClient:
    def __init__(self, settings: Settings):
        import base64
        self.settings = settings
        self.api = f"{settings.om_base}/api/v1"
        self.session = requests.Session()
        if not settings.om_admin_password:
            raise ConfigError("OM_ADMIN_PASSWORD is not set")
        r = requests.post(f"{self.api}/users/login",
                          json={"email": settings.om_admin_email,
                                "password": base64.b64encode(
                                    settings.om_admin_password.encode()).decode()},
                          timeout=30)
        r.raise_for_status()
        self.session.headers["Authorization"] = f"Bearer {r.json()['accessToken']}"

    def request(self, method: str, path: str, **kw):
        r = self.session.request(method, f"{self.api}{path}", timeout=60, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"OM {method} {path} -> {r.status_code}: {r.text[:400]}")
        return r.json() if r.content else {}

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, **kw):
        return self.request("POST", path, **kw)

    def put(self, path, **kw):
        return self.request("PUT", path, **kw)

    def patch(self, path: str, ops: list):
        return self.request("PATCH", path, json=ops,
                            headers={"Content-Type": "application/json-patch+json"})


def om_list_all(client: OmClient, collection: str, params: dict | None = None):
    params = dict(params or {})
    params.setdefault("limit", 100)
    out, after = [], None
    while True:
        p = dict(params)
        if after:
            p["after"] = after
        r = client.get(f"/{collection}", params=p)
        out.extend(r.get("data", []))
        after = (r.get("paging") or {}).get("after")
        if not after or not r.get("data"):
            return out


# ---------------------------------------------------------------------------
# Plan / dry-run / rollback framework
# ---------------------------------------------------------------------------

@dataclass
class Action:
    description: str
    kind: str                      # e.g. "create_role", "grant", "mask", "filter", "assignment", "delete_assignment"
    detail: dict = field(default_factory=dict)
    fn: object = None              # callable -> result
    rollback: dict = field(default_factory=dict)  # info needed to undo
    skipped: bool = False          # already exists -> idempotent no-op


class Plan:
    """Collects actions; executes only in apply mode; emits rollback file."""

    def __init__(self, name: str, apply: bool):
        self.name = name
        self.apply = apply
        self.actions: list[Action] = []
        self.errors: list[str] = []

    def add(self, action: Action):
        self.actions.append(action)

    def summary(self) -> str:
        lines = []
        for i, a in enumerate(self.actions, 1):
            mark = "SKIP (exists)" if a.skipped else ("APPLY" if self.apply else "WOULD")
            lines.append(f"{i:3}. [{mark}] {a.description}")
        return "\n".join(lines)

    def execute(self):
        applied = []
        for i, a in enumerate(self.actions, 1):
            if a.skipped:
                print(f"{i:3}. [SKIP] {a.description}")
                continue
            print(f"{i:3}. [APPLY] {a.description}")
            try:
                result = a.fn() if a.fn else None
            except Exception as exc:
                msg = f"FAILED action {i} ({a.description}): {sql_error_text(exc)}"
                self.errors.append(msg)
                print(f"     ERROR: {sql_error_text(exc)}")
                raise SystemExit(f"\nStopped on failure. {msg}\nRe-run with --apply after fixing; completed actions are idempotent.")
            applied.append({"description": a.description, "kind": a.kind,
                            "detail": a.detail, "rollback": a.rollback,
                            "result": _safe_json(result)})
        return applied

    def write_rollback(self, applied: list[dict]):
        REPORTS_DIR.mkdir(exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = REPORTS_DIR / f"rollback_{self.name}_{ts}.json"
        path.write_text(json.dumps({"plan": self.name, "applied_at": ts,
                                    "actions": applied}, indent=2, default=str))
        print(f"\nRollback data written to {path}")
        return path


def _safe_json(obj):
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)[:500]


def require_apply_flag(argv: list[str]) -> bool:
    """Standard dry-run/apply CLI contract shared by all configure scripts."""
    if "--apply" in argv:
        return True
    if "--dry-run" in argv:
        return False
    return False


def print_mode(apply: bool, what: str):
    mode = "APPLY (changes will be made)" if apply else "DRY-RUN (no changes; use --apply to execute)"
    print(f"=== {what} — {mode} ===\n")
