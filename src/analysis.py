"""Turn snapshots into numbers (daily use, forecast) and alerts. No I/O here."""
from __future__ import annotations

import calendar
import datetime as dt

from i18n import T, n


def pct(a, b) -> int:
    return round(100 * a / b) if b else 0


def daily_series(history: dict[str, dict], env_id: str | None = None) -> list[tuple[str, float]]:
    """[(data date, credits used that day)] from month-to-date counters in the daily snapshots.

    Keyed by the data date of the source (PPAC updates once a day, one day behind), so a day that was
    not updated yet is not counted twice. A new month restarts the counter.
    """
    points: dict[str, float] = {}
    for snap in history.values():
        pk = snap.get("pack") or {}
        d = pk.get("dataDate")
        if not d:
            continue
        if env_id:
            c = (snap.get("consumption") or {}).get(env_id)
            if c is None:
                continue
            points[d] = c["consumed"]
        else:
            points[d] = pk.get("consumed", 0)
    out, prev_d, prev_v = [], None, None
    for d in sorted(points):
        v = points[d]
        if prev_d is None or d[:7] != prev_d[:7]:
            used = v if d.endswith("-01") else None   # unknown without the previous day
        else:
            used = max(v - prev_v, 0)
        if used is not None:
            out.append((d, round(used, 2)))
        prev_d, prev_v = d, v
    return out


def forecast(snap: dict, series: list[tuple[str, float]]) -> dict:
    pk = snap.get("pack") or {}
    if not pk.get("dataDate"):
        return {}
    d = dt.date.fromisoformat(pk["dataDate"])
    last_day = calendar.monthrange(d.year, d.month)[1]
    recent = [v for _, v in series[-7:]]
    avg = sum(recent) / len(recent) if recent else pk["consumed"] / max(d.day, 1)
    projected = pk["consumed"] + avg * (last_day - d.day)
    remaining = pk["entitled"] - pk["consumed"]
    runout = None
    if avg > 0 and remaining > 0:
        r = d + dt.timedelta(days=int(remaining / avg))
        if r < dt.date(d.year, d.month, last_day):
            runout = r.isoformat()
    elif remaining <= 0:
        runout = d.isoformat()
    return {"avg": round(avg), "projected": round(projected), "runout": runout,
            "last": series[-1] if series else None}


def evaluate(cfg: dict, snap: dict, prev: dict | None, history: dict, errors: list[str]) -> tuple[list[dict], dict]:
    """Alerts for today + the 'already notified this month' memory. Alert = {level, title, text}."""
    lang = cfg.get("report", {}).get("language", "en")
    th = cfg.get("thresholds", {})
    prev = prev or {}
    seen = dict(prev.get("notified", {})) if prev.get("month") == snap["month"] else {}
    alerts: list[dict] = []
    names = {k: v["name"] for k, v in (snap.get("environments") or {}).items()}

    def add(level, title, text):
        alerts.append({"level": level, "title": title, "text": text})

    pk = snap.get("pack")
    if pk:
        used = pct(pk["consumed"], pk["entitled"])
        lvl = max([l for l in th.get("packPercent", [70, 85, 95]) if used >= l], default=0)
        if lvl and lvl > seen.get("pack", 0):
            add("red" if lvl >= 95 else "amber", T(lang, "a_pack", p=used),
                T(lang, "a_pack_t", c=n(pk["consumed"], lang), e=n(pk["entitled"], lang)))
            seen["pack"] = lvl
        series = daily_series({**history, snap["day"]: snap})
        fc = forecast(snap, series)
        if fc.get("runout") and seen.get("runout") != fc["runout"][:7]:
            add("red", T(lang, "a_runout"), T(lang, "a_runout_t", d=fc["runout"]))
            seen["runout"] = fc["runout"][:7]
        if len(series) >= 4:
            d_last, v_last = series[-1]
            base = [v for _, v in series[-8:-1]]
            avg = sum(base) / len(base) if base else 0
            if avg and v_last >= th.get("spikeMinCredits", 200) and v_last > th.get("spikeFactor", 3) * avg \
                    and seen.get("spike") != d_last:
                add("amber", T(lang, "a_spike"), T(lang, "a_spike_t", c=n(v_last, lang), d=d_last, x=round(v_last / avg)))
                seen["spike"] = d_last
        if cfg.get("checks", {}).get("aiBuilder", True) and pk.get("aiPurchased") \
                and pk.get("aiConsumed", 0) > pk["aiPurchased"] and not seen.get("ai"):
            add("amber", T(lang, "a_ai"), T(lang, "a_ai_t", c=n(pk["aiConsumed"], lang), e=n(pk["aiPurchased"], lang),
                                            p=pct(pk["aiConsumed"], pk["aiPurchased"])))
            seen["ai"] = True

    for env_id, c in (snap.get("consumption") or {}).items():
        state = ""
        if c["allocated"] and c["consumed"] > c["allocated"]:
            state = "over"
        elif c["allocated"] and pct(c["consumed"], c["allocated"]) >= th.get("environmentPercent", 80):
            state = "high"
        elif not c["allocated"] and c["consumed"] > 0:
            state = "pool"
        if state and seen.get(f"env:{env_id}") != state:
            title = {"over": T(lang, "a_env_over", n=c["name"]),
                     "high": T(lang, "a_env_high", n=c["name"], p=pct(c["consumed"], c["allocated"])),
                     "pool": T(lang, "a_env_pool", n=c["name"])}[state]
            add("red" if state == "over" else "amber", title,
                T(lang, "a_env_t", c=n(c["consumed"], lang), a=n(c["allocated"], lang)))
            seen[f"env:{env_id}"] = state

    if "allocations" in snap and "allocations" in prev:
        old, new = prev["allocations"], snap["allocations"]
        for env_id in sorted(set(old) | set(new)):
            if old.get(env_id, 0) != new.get(env_id, 0):
                add("amber", T(lang, "a_alloc"), T(lang, "a_alloc_t", n=names.get(env_id, env_id),
                                                    o=n(old.get(env_id, 0), lang), v=n(new.get(env_id, 0), lang)))

    if "environments" in snap and "environments" in prev:
        for env_id in sorted(set(snap["environments"]) - set(prev["environments"])):
            e = snap["environments"][env_id]
            add("info", T(lang, "a_env_new"), T(lang, "a_env_new_t", n=e["name"], s=e["sku"], d=e["created"]))
        for env_id in sorted(set(prev["environments"]) - set(snap["environments"])):
            add("info", T(lang, "a_env_gone"), prev["environments"][env_id]["name"])

    if "payg" in snap and "payg" in prev:
        for pid, p in snap["payg"].items():
            if p["environments"] != prev["payg"].get(pid, {}).get("environments"):
                envs = ", ".join(names.get(e, e) for e in p["environments"]) or T(lang, "nobody")
                add("amber", T(lang, "a_payg"), T(lang, "a_payg_t", n=p["name"], e=envs))

    for fid, f in (snap.get("orphanFlows") or {}).items():
        if not seen.get(f"flow:{fid}") and ("Recurrence" in f["trigger"] or not f["trigger"]):
            seen[f"flow:{fid}"] = True
            add("amber", T(lang, "a_flow"), T(lang, "a_flow_t", n=f["name"], e=f["env"], o=T(lang, f["owner"]),
                                              x="" if f["trigger"] else T(lang, "a_flow_unknown")))

    for ev in snap.get("audit") or []:
        add("info", T(lang, "a_audit"), T(lang, "a_audit_t", k=ev["kind"].replace("_", " "), u=ev["user"],
                                          t=str(ev["time"])[:16].replace("T", " "),
                                          a=f" ({ev['amount']})" if ev.get("amount") else ""))

    if errors:
        add("red", T(lang, "a_errors"), " · ".join(errors))
    return alerts, seen
