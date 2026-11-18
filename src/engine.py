"""Orchestration: the scheduled daily run and on-demand reports."""
from __future__ import annotations

import datetime as dt

import reports
from analysis import evaluate
from collect import Tokens, collect, http
from store import Store

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def post(webhook: str | None, card: dict) -> None:
    if webhook:
        http("POST", webhook, None, card, raw=True)


def _alerts_log(store: Store, end: dt.date, days: int) -> list[dict]:
    log = []
    for d, s in store.history(end, days).items():
        for a in s.get("alerts", []):
            log.append({**a, "day": d})
    return log


def _reuse_report(snap: dict, history: dict, always: bool = False) -> None:
    """Show the last licensing-report figures of this month when there is no fresh report in `snap`
    (on request: never asked; daily run: Microsoft still building it)."""
    if not always and (snap.get("agents") or {}).get("source") != "pending":
        return
    for day in sorted(history, reverse=True):
        ag = history[day].get("agents") or {}
        if ag.get("source") == "report" and history[day].get("month") == snap["month"]:
            snap["agents"] = ag
            return


def scheduled(cfg: dict, tokens: Tokens, store: Store, webhook: str | None, now: dt.datetime | None = None) -> dict:
    """Daily run: collect, remember, alert; weekly and monthly reports on their days."""
    now = now or dt.datetime.now(dt.timezone.utc)
    prev = store.get("state.json")
    history = store.history(now.date() - dt.timedelta(days=1), 62)
    snap, errors = collect(cfg, tokens, now, state=prev)
    _reuse_report(snap, history)
    alerts, seen = evaluate(cfg, snap, prev, history, errors)
    # keep the last good value of a failed part, so tomorrow's comparison still works
    for k in ("allocations", "environments", "payg"):
        if k not in snap and prev and k in prev:
            snap[k] = prev[k]
    snap["alerts"] = [{"level": a["level"], "title": a["title"], "text": a["text"]} for a in alerts]
    store.put_day({k: v for k, v in snap.items() if k not in ("audit", "reportJob")})
    store.put("state.json", {**{k: snap[k] for k in ("month", "allocations", "environments", "payg", "reportJob")
                                if k in snap},
                             "notified": seen, "time": snap["time"]})

    sch = cfg.get("schedule", {})
    sent = []
    if alerts or sch.get("dailyPost", "alerts-only") == "always":
        post(webhook, reports.daily(cfg, snap, history, alerts))
        sent.append("daily")
    if DAYS[now.weekday()] == str(sch.get("weeklyDay", "Monday")).lower():
        post(webhook, reports.weekly(cfg, snap, history, _alerts_log(store, now.date(), 7)))
        sent.append("weekly")
    if now.day == int(sch.get("monthlyDay", 1)):
        prev_month = (now.date().replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")
        post(webhook, reports.monthly(cfg, snap, history, prev_month))
        sent.append("monthly")
    return {"alerts": alerts, "errors": errors, "sent": sent, "snapshot": snap}


def on_demand(cfg: dict, tokens: Tokens, store: Store, webhook: str | None, kind: str,
              now: dt.datetime | None = None) -> dict:
    """Report on request: fresh data, history for trends; changes nothing in the stored state."""
    now = now or dt.datetime.now(dt.timezone.utc)
    history = store.history(now.date() - dt.timedelta(days=1), 62)
    # the licensing report takes minutes; on request use the one from the last daily run of this month
    snap, errors = collect(cfg, tokens, now, skip=("agentsReport",))
    _reuse_report(snap, history, always=True)
    alerts, _ = evaluate(cfg, snap, None, history, errors)   # everything current, not only what is new
    if kind == "weekly":
        card = reports.weekly(cfg, snap, history, _alerts_log(store, now.date(), 7) + [{**a, "day": snap["day"]} for a in alerts])
    elif kind == "monthly":
        card = reports.monthly(cfg, snap, history)
    elif kind == "daily":
        card = reports.daily(cfg, snap, history, alerts)
    else:
        card = reports.status(cfg, snap, history, alerts)
    post(webhook, card)
    return {"alerts": alerts, "errors": errors, "card": card, "snapshot": snap}
