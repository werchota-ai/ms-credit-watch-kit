"""Read-only data collection: Copilot / AI Builder credits and Power Platform admin state.

Tenant-independent: everything is derived from config["tenantId"].
Tokens come from the managed identity in Azure, or from the az CLI when run locally.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request

PUB = "https://api.powerplatform.com/licensing"
BAP = "https://api.bap.microsoft.com/providers/Microsoft.BusinessAppPlatform/scopes/admin"
FLOW = "https://api.flow.microsoft.com/providers/Microsoft.ProcessSimple/scopes/admin"
GRAPH = "https://graph.microsoft.com/v1.0"

RES = {
    "pp": "https://api.powerplatform.com",
    "bap": "https://service.powerapps.com/",
    "flow": "https://service.flow.microsoft.com/",
    "graph": "https://graph.microsoft.com",
    "mgmt": "https://manage.office.com",
    "storage": "https://storage.azure.com/",
}

AUDIT_OPS = {
    "CurrencyEnvironmentAllocate": "allocation_changed",
    "EnvironmentCreated": "environment_created",
    "EnvironmentDeleted": "environment_deleted",
    "BillingPolicyCreated": "payg_created",
    "BillingPolicyUpdated": "payg_changed",
    "BillingPolicyEnvironmentAdded": "payg_linked",
    "BillingPolicyEnvironmentRemoved": "payg_unlinked",
}


def lic_base(tenant_id: str) -> str:
    """Internal PPAC licensing host: tenant id without dashes, a dot before the last two characters."""
    t = tenant_id.replace("-", "").lower()
    return f"https://{t[:-2]}.{t[-2:]}.tenant.api.powerplatform.com/licensing"


# ---------------------------------------------------------------- tokens / http
class Tokens:
    """Managed identity in Azure (IDENTITY_ENDPOINT set), otherwise az CLI (your own login)."""

    def __init__(self):
        self._cache: dict[str, str] = {}

    def get(self, key_or_resource: str) -> str:
        res = RES.get(key_or_resource, key_or_resource)
        if res in self._cache:
            return self._cache[res]
        ep, hdr = os.environ.get("IDENTITY_ENDPOINT"), os.environ.get("IDENTITY_HEADER")
        if ep and hdr:
            q = urllib.parse.urlencode({"resource": res, "api-version": "2019-08-01"})
            req = urllib.request.Request(f"{ep}?{q}", headers={"X-IDENTITY-HEADER": hdr})
            with urllib.request.urlopen(req, timeout=30) as r:
                tok = json.load(r)["access_token"]
        else:
            az = "az.cmd" if os.name == "nt" else "az"
            tok = subprocess.run([az, "account", "get-access-token", "--resource", res,
                                  "--query", "accessToken", "-o", "tsv"],
                                 capture_output=True, text=True, check=True).stdout.strip()
        self._cache[res] = tok
        return tok


def http(method: str, url: str, token: str | None = None, body=None, headers=None, raw=False):
    h = {"Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        h.setdefault("Content-Type", "application/json")
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read()
        if raw:
            return b
        return json.loads(b) if b else None


def paged(tokens: Tokens, key: str, url: str, headers=None) -> list:
    out = []
    while url:
        r = http("GET", url, tokens.get(key), headers=headers)
        out += r.get("value", [])
        url = r.get("nextLink") or r.get("@odata.nextLink")
    return out


def _err(name: str, e: Exception) -> str:
    if isinstance(e, urllib.error.HTTPError):
        try:
            detail = e.read().decode(errors="replace")[:200]
        except Exception:  # noqa: BLE001
            detail = ""
        return f"{name}: HTTP {e.code} {detail}".strip()
    return f"{name}: {type(e).__name__}: {str(e)[:200]}"


# ---------------------------------------------------------------- collect
def collect(cfg: dict, tokens: Tokens, now: dt.datetime, skip: tuple = ()) -> tuple[dict, list[str]]:
    """Return (snapshot, errors). Each part runs and fails on its own; a failure is reported, never hidden."""
    checks = cfg.get("checks", {})
    lic = lic_base(cfg["tenantId"])
    snap: dict = {"time": now.isoformat(timespec="seconds"), "day": now.strftime("%Y-%m-%d"),
                  "month": now.strftime("%Y-%m")}
    errors: list[str] = []

    def part(name, flag, fn):
        if name in skip or not checks.get(flag, True):
            return
        try:
            snap[name] = fn()
        except Exception as e:  # noqa: BLE001
            errors.append(_err(name, e))

    # -- tenant pack and AI Builder pool
    def pack():
        t = http("GET", f"{lic}/entitlements/MCSMessages?api-version=1", tokens.get("pp"))["entitlement"]["capacity"]
        r = {"entitled": t["entitled"]["value"], "consumed": round(t["consumed"]["value"], 2),
             "dataDate": (t["consumed"].get("lastUpdatedOn") or "")[:10]}
        for c in http("GET", f"{lic}/tenantCapacity/CurrencyReports?includeAllocations=True&includeConsumptions=True&api-version=1",
                      tokens.get("pp")):
            if c["currencyType"] == "AI":
                r["aiPurchased"] = c["purchased"]
                r["aiConsumed"] = (c.get("consumed") or {}).get("unitsConsumed", 0)
            if c["currencyType"] == "MCSMessages":
                r["allocated"] = c["allocated"]
        return r

    def environments():
        envs = paged(tokens, "bap", f"{BAP}/environments?api-version=2020-10-01&$expand=properties.billingPolicy")
        return {e["name"]: {"name": e["properties"]["displayName"],
                            "sku": e["properties"].get("environmentSku"),
                            "created": (e["properties"].get("createdTime") or "")[:10],
                            "url": ((e["properties"].get("linkedEnvironmentMetadata") or {}).get("instanceUrl") or "").rstrip("/"),
                            "billingPolicy": (e["properties"].get("billingPolicy") or {}).get("id")} for e in envs}

    part("pack", "credits", pack)
    part("environments", "environments", environments)
    envs = snap.get("environments", {})

    def consumption():
        r = http("GET", f"{lic}/environments/entitlementConsumptions/MCSMessages?api-version=1", tokens.get("pp"))
        out = {}
        for e in r.get("value", []):
            cap = e["entitlement"]["capacity"]
            out[e["environmentId"]] = {"name": e["environmentName"], "allocated": cap["allocated"]["value"],
                                       "consumed": round(cap["consumed"]["value"], 2), "status": cap.get("status")}
        return out

    def allocations():
        out = {}
        for env_id in envs:
            try:
                a = http("GET", f"{PUB}/environments/{env_id}/allocations?api-version=2022-03-01-preview", tokens.get("pp"))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                raise
            v = sum(x.get("allocated", 0) for x in a.get("currencyAllocations", []) if x["currencyType"] == "MCSMessages")
            if v:
                out[env_id] = v
        return out

    def payg():
        out = {}
        try:
            for b in http("GET", f"{PUB}/billingPolicies?api-version=2022-03-01-preview", tokens.get("pp")).get("value", []):
                le = http("GET", f"{PUB}/billingPolicies/{b['id']}/environments?api-version=2022-03-01-preview", tokens.get("pp"))
                out[b["id"]] = {"name": b["name"], "environments": sorted(x["environmentId"] for x in le.get("value", []))}
        except urllib.error.HTTPError:
            pass   # the list is often refused to service principals; the environments' own link below still works
        for env_id, e in envs.items():
            pid = e.get("billingPolicy")
            if pid:
                p = out.setdefault(pid, {"name": pid[:8], "environments": []})
                if env_id not in p["environments"]:
                    p["environments"] = sorted(p["environments"] + [env_id])
        return out

    part("consumption", "credits", consumption)
    part("allocations", "allocations", allocations)
    part("payg", "payAsYouGo", payg)

    def orphan_flows():
        """Active flows whose owner account is disabled or deleted (they keep failing or run as nobody)."""
        alive = {u["id"]: bool(u.get("accountEnabled"))
                 for u in paged(tokens, "graph", f"{GRAPH}/users?$select=id,accountEnabled&$top=999")}
        out: dict = {}
        # 1) solution-aware flows: Dataverse of the configured environments (application user with a read role)
        wanted = cfg.get("powerPlatform", {}).get("flowCheckEnvironments", ["default"])
        for env_id, e in envs.items():
            is_wanted = ("default" in wanted and env_id.lower().startswith("default-")) or e["name"] in wanted \
                or env_id in wanted or (e["url"] and e["url"] in wanted) or "all" in wanted
            if not is_wanted or not e["url"]:
                continue
            try:
                url = (f"{e['url']}/api/data/v9.2/workflows?$select=workflowid,resourceid,name,clientdata"
                       f"&$filter=category%20eq%205%20and%20statecode%20eq%201"
                       f"&$expand=owninguser($select=azureactivedirectoryobjectid,isdisabled)")
                rows = paged(tokens, e["url"], url)
            except urllib.error.HTTPError as ex:
                errors.append(f"orphanFlows: {e['name']}: Dataverse HTTP {ex.code} (reader role missing?)")
                continue
            for w in rows:
                u = w.get("owninguser") or {}
                oid = u.get("azureactivedirectoryobjectid")
                if not oid or (alive.get(oid) and not u.get("isdisabled")):
                    continue
                trig = ""
                try:
                    t = json.loads(w.get("clientdata") or "{}")["properties"]["definition"]["triggers"]
                    trig = ",".join(v.get("type", "") for v in t.values())
                except Exception:  # noqa: BLE001
                    pass
                out[(w.get("resourceid") or w["workflowid"]).lower()] = {
                    "env": e["name"], "name": w["name"], "trigger": trig,
                    "owner": "disabled" if oid in alive else "deleted"}
        # 2) classic (non-solution) flows of all environments via the Flow admin API
        for env_id, e in envs.items():
            try:
                lst = paged(tokens, "flow", f"{FLOW}/environments/{env_id}/v2/flows?api-version=2016-11-01")
            except urllib.error.HTTPError:
                continue
            for f in lst:
                p = f["properties"]
                creator = (p.get("creator") or {}).get("objectId")
                if p.get("state") != "Started" or not creator or alive.get(creator) or f["name"].lower() in out:
                    continue
                trig = ""
                try:
                    d = http("GET", f"{FLOW}/environments/{env_id}/flows/{f['name']}?api-version=2016-11-01&$expand=properties.definitionSummary",
                             tokens.get("flow"))
                    trig = ",".join(t.get("type", "") for t in d["properties"].get("definitionSummary", {}).get("triggers", []))
                except Exception:  # noqa: BLE001
                    pass
                out[f["name"].lower()] = {"env": e["name"], "name": p.get("displayName"), "trigger": trig,
                                          "owner": "disabled" if creator in alive else "deleted"}
        return out

    part("orphanFlows", "orphanFlows", orphan_flows)

    def agents():
        """Credits per agent this month. Documented per-resource API first; if the tenant does not have it yet (403),
        the agent limits list, which carries month-to-date consumption per agent."""
        first = now.strftime("%Y-%m-01")
        out: dict = {}
        source = "resources"
        try:
            url = f"{PUB}/entitlements/MCSMessages/resources?fromDate={first}&toDate={now.strftime('%Y-%m-%d')}&api-version=2024-10-01"
            while url:
                r = http("GET", url, tokens.get("pp"))
                for x in r.get("value", []):
                    out[x["resourceId"].lower()] = {"env": x.get("environmentId"), "consumed": round(x.get("consumed", 0), 2),
                                                    "feature": (x.get("metadata") or {}).get("Feature")}
                url = r.get("@odata.nextLink")
        except urllib.error.HTTPError as e:
            if e.code not in (403, 404):
                raise
            source = "thresholds"
            try:
                rows = http("GET", f"{PUB}/entitlements/MCSMessages/resourceThresholds?api-version=2024-10-01", tokens.get("pp")) or []
            except urllib.error.HTTPError as e2:
                if e2.code not in (403, 404):
                    raise
                # a known Microsoft limit for service identities, not a broken check -> note in the report, no red line
                return {"source": "unavailable", "items": {}}
            for x in rows:
                out[x["resourceId"].lower()] = {"env": x.get("environmentId"), "consumed": round(x.get("resourceConsumption", 0), 2),
                                                "limit": x.get("limit") or 0, "stop": x.get("stopResource")}
        # names: Copilot Studio agents are Dataverse "bot" rows (reader role includes prvReadbot)
        for env_id, e in envs.items():
            ids = [k for k, v in out.items() if v.get("env") == env_id]
            if not ids or not e["url"]:
                continue
            try:
                for b in paged(tokens, e["url"], f"{e['url']}/api/data/v9.2/bots?$select=botid,name"):
                    if b["botid"].lower() in out:
                        out[b["botid"].lower()]["name"] = b["name"]
            except urllib.error.HTTPError:
                pass
        return {"source": source, "items": out}

    part("agents", "agents", agents)

    def activity():
        """Optional: agent activity from Application Insights (Copilot Studio environment-level telemetry, KQL)."""
        ws = cfg.get("appInsights", {}).get("workspaceId")
        if not ws:
            return None
        q = """AppDependencies
| where TimeGenerated > ago(7d) and Name in ("InvokeAgent", "ExecuteTool")
| extend agent = tostring(Properties["gen_ai.agent.name"]), conv = tostring(Properties["gen_ai.conversation.id"]),
         user = tostring(Properties["user.email"]), model = tostring(Properties["gen_ai.request.model"])
| summarize turns = countif(Name == "InvokeAgent"), conversations = dcount(conv), users = dcount(user),
            toolCalls = countif(Name == "ExecuteTool"), errors = countif(Success == false),
            models = make_set(model, 5) by agent
| top 15 by turns desc"""
        r = http("POST", f"https://api.loganalytics.io/v1/workspaces/{ws}/query", tokens.get("https://api.loganalytics.io"),
                 {"query": q})
        t = r["tables"][0]
        cols = [c["name"] for c in t["columns"]]
        return [dict(zip(cols, row)) for row in t["rows"]]

    part("activity", "activity", activity)

    def audit():
        """Power Platform admin events of the last 24 h (Office 365 Management Activity API, max window 24 h)."""
        mgmt = f"https://manage.office.com/api/v1.0/{cfg['tenantId']}/activity/feed"
        tok = tokens.get("mgmt")
        subs = http("GET", f"{mgmt}/subscriptions/list", tok) or []
        if not any(s.get("contentType") == "Audit.General" and s.get("status") == "enabled" for s in subs):
            http("POST", f"{mgmt}/subscriptions/start?contentType=Audit.General", tok, b"")
            return []   # events become available some hours after the first start
        start = (now - dt.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
        url = f"{mgmt}/subscriptions/content?contentType=Audit.General&startTime={start}&endTime={now.strftime('%Y-%m-%dT%H:%M:%S')}"
        events = []
        while url:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
            with urllib.request.urlopen(req, timeout=60) as r:
                blobs = json.load(r)
                url = r.headers.get("NextPageUri")
            for b in blobs:
                for ev in http("GET", b["contentUri"], tok) or []:
                    if ev.get("Operation") in AUDIT_OPS and ev.get("UserId") != "system@powerplatform":
                        props = {p["Name"].split(".")[-1]: p["Value"] for p in ev.get("PropertyCollection", [])}
                        events.append({"time": ev.get("CreationTime"), "user": ev.get("UserId"),
                                       "kind": AUDIT_OPS[ev["Operation"]], "amount": props.get("amount")})
        return events

    part("audit", "audit", audit)
    return snap, errors
