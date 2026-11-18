"""Teams Adaptive Cards: daily, weekly, monthly and status reports, help and the request acknowledgement."""
from __future__ import annotations

import datetime as dt

from analysis import daily_series, forecast, free_pool, pct
from i18n import T, n

COLOR = {"red": "Attention", "amber": "Warning", "info": "Default", "good": "Good"}
PPAC = "https://admin.powerplatform.microsoft.com/billing/licenses/copilotStudio/overview"


class Card:
    def __init__(self, cfg: dict, kind: str, snap: dict):
        self.lang = cfg.get("report", {}).get("language", "en")
        self.cfg = cfg
        title = f"{cfg.get('report', {}).get('title', 'Copilot credit watch')} · {T(self.lang, kind)}"
        pk = snap.get("pack") or {}
        self.body = [
            {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium", "wrap": True},
            {"type": "TextBlock", "isSubtle": True, "spacing": "None", "size": "Small", "wrap": True,
             "text": f"{cfg.get('customer', '')} · " + T(self.lang, "data_as_of", d=pk.get("dataDate", "?"),
                                                        t=snap.get("time", "")[:16].replace("T", " "))}]
        self.plain = [title]

    def heading(self, text, color="Default"):
        self.body.append({"type": "TextBlock", "text": text, "weight": "Bolder", "color": color,
                          "wrap": True, "spacing": "Medium"})
        self.plain.append(f"\n{text}")

    def text(self, text, subtle=False):
        self.body.append({"type": "TextBlock", "text": text, "wrap": True, "spacing": "None", "isSubtle": subtle})
        self.plain.append(text)

    def facts(self, rows: list[tuple[str, str]]):
        if rows:
            self.body.append({"type": "FactSet", "spacing": "Small",
                              "facts": [{"title": a, "value": b} for a, b in rows]})
            self.plain += [f"{a}: {b}" for a, b in rows]

    def alerts(self, alerts: list[dict]):
        for a in alerts:
            self.heading(a["title"], COLOR[a["level"]])
            self.text(a["text"])

    def build(self) -> dict:
        self.body.append({"type": "TextBlock", "size": "Small", "isSubtle": True, "wrap": True, "spacing": "Medium",
                          "text": f"[{T(self.lang, 'open')}]({PPAC})"})
        actions = [{"type": "Action.ShowCard", "title": T(self.lang, "copy"), "card": {
            "type": "AdaptiveCard", "body": [{"type": "Input.Text", "id": "plain", "isMultiline": True,
                                              "value": "\n".join(self.plain).strip()}]}}]
        return {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive",
                "content": {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard",
                            "version": "1.4", "msteams": {"width": "Full"}, "body": self.body, "actions": actions}}]}


# ---------------------------------------------------------------- blocks
def _bar(v: float, top: float, width: int = 14) -> str:
    k = 0 if not top else max(1 if v > 0 else 0, round(width * v / top))
    return "▇" * k


def _pack_block(c: Card, snap: dict, series: list) -> None:
    pk = snap.get("pack")
    if not pk:
        return
    L = c.lang
    fc = forecast(snap, series)
    rows = [(T(L, "pack"), T(L, "pack_line", c=n(pk["consumed"], L), e=n(pk["entitled"], L),
                             p=pct(pk["consumed"], pk["entitled"])))]
    if fc.get("last"):
        rows.append((T(L, "yesterday"), f"{n(fc['last'][1], L)} ({fc['last'][0]})"))
    if len(series) >= 2:
        rows.append((T(L, "avg7"), n(fc["avg"], L)))
    if fc:
        rows.append((T(L, "projection"), f"{n(fc['projected'], L)} / {n(pk['entitled'], L)}"))
        rows.append((T(L, "runout"), fc["runout"] or T(L, "no_runout")))
    free = free_pool(snap)
    if free is not None:
        rows.append((T(L, "free"), n(max(free, 0), L)))
    if pk.get("aiPurchased"):
        rows.append((T(L, "ai"), f"{n(pk.get('aiConsumed', 0), L)} / {n(pk['aiPurchased'], L)}"))
    price = c.cfg.get("pricing", {}).get("packPricePerMonth") or 0
    if price and pk.get("entitled"):
        cur = c.cfg.get("pricing", {}).get("currency", "EUR")
        rows.append((T(L, "cost"), f"{price * pk['consumed'] / pk['entitled']:,.0f} {cur} "
                                   f"/ {price:,.0f} {cur}"))
    c.facts(rows)


def _env_block(c: Card, snap: dict, history: dict, days: int | None = None) -> None:
    L = c.lang
    cons = snap.get("consumption") or {}
    allocs = snap.get("allocations") or {}
    names = {k: v["name"] for k, v in (snap.get("environments") or {}).items()}
    rows = []
    for env_id in sorted(set(cons) | set(allocs), key=lambda e: -(cons.get(e, {}).get("consumed", 0))):
        used = cons.get(env_id, {}).get("consumed", 0)
        alloc = cons.get(env_id, {}).get("allocated", allocs.get(env_id, 0))
        if not used and not alloc:
            continue
        delta = ""
        if days:
            s = daily_series({**history, snap["day"]: snap}, env_id)[-days:]
            added = sum(v for _, v in s)
            if n(added, L) != "0":   # no "(+0)" noise for environments without use
                delta = f"  (+{n(added, L)})"
        rows.append((cons.get(env_id, {}).get("name") or names.get(env_id, env_id),
                     T(L, "env_line", c=n(used, L), a=n(alloc, L), d=delta)))
    if rows:
        c.heading(T(L, "by_env"))
        c.facts(rows)


def _pool_block(c: Card, snap: dict) -> None:
    """Environments allowed to take credits from the shared pool (the rest Cowork and Copilot Code live on)."""
    names = {k: v["name"] for k, v in (snap.get("environments") or {}).items()}
    pd = snap.get("poolDraw") or {}
    if pd:
        c.heading(T(c.lang, "pool_title"))
        c.text(", ".join(names.get(e, e) + (f" ({n(d['auto'], c.lang)})" if d.get("auto") else "")
                         for e, d in sorted(pd.items(), key=lambda kv: names.get(kv[0], kv[0]))), subtle=True)


def _agents_block(c: Card, snap: dict, top: int = 10) -> None:
    if (snap.get("agents") or {}).get("source") == "unavailable":
        c.heading(T(c.lang, "agents"))
        c.text(T(c.lang, "agents_na"), subtle=True)
        return
    src = snap.get("agents") or {}
    if src.get("source") == "pending":
        c.heading(T(c.lang, "agents"))
        c.text(T(c.lang, "agents_pending"), subtle=True)
        return
    ag = src.get("items") or {}

    def line(v):
        s = n(v["consumed"], c.lang)
        if v.get("limit"):
            s += f" / {T(c.lang, 'limit')} {n(v['limit'], c.lang)}"
        feats = sorted((v.get("features") or {}).items(), key=lambda kv: -kv[1])
        if feats:
            s += " · " + ", ".join(f"{f} {n(x, c.lang)}" if len(feats) > 1 else f for f, x in feats[:3])
        if v.get("envName"):
            s += f" · {v['envName']}"
        return s

    rows = sorted(ag.items(), key=lambda kv: -kv[1].get("consumed", 0))
    rows = [(v.get("name") or k[:8], line(v)) for k, v in rows[:top] if v.get("consumed")]
    if rows:
        c.heading(T(c.lang, "agents"))
        c.facts(rows)
        if src.get("source") == "report":
            c.text(T(c.lang, "agents_src", d=src.get("to", "")), subtle=True)


def _activity_block(c: Card, snap: dict) -> None:
    act = snap.get("activity") or []
    if act:
        c.heading(T(c.lang, "activity"))
        c.facts([(a.get("agent") or "?", T(c.lang, "activity_line", t=a["turns"], v=a["conversations"], u=a["users"],
                                           x=a["toolCalls"], e=a["errors"])) for a in act])


def _orphans_block(c: Card, snap: dict, alerts: list[dict] | None = None) -> None:
    """Flows without a live owner; those already shown as an alert on the same card are not repeated."""
    flagged = [a["text"] for a in alerts or [] if a.get("title") == T(c.lang, "a_flow")]
    fl = [f for f in (snap.get("orphanFlows") or {}).values()
          if not any(t.startswith(f"{f['name']} ({f['env']}),") for t in flagged)]
    if fl:
        c.heading(T(c.lang, "orphans_more") if flagged else T(c.lang, "orphans"))
        c.facts([(f["name"], f"{f['env']} · {T(c.lang, f['owner'])}"
                  + (f" · {f['trigger']}" if f["trigger"] else "")) for f in fl])


# ---------------------------------------------------------------- reports
def daily(cfg, snap, history, alerts) -> dict:
    c = Card(cfg, "daily", snap)
    series = daily_series({**history, snap["day"]: snap})
    _pack_block(c, snap, series)
    if alerts:
        c.heading(T(c.lang, "changes"))
        c.alerts(alerts)
    _env_block(c, snap, history, days=1)
    if len(history) < 3:
        c.text(T(c.lang, "collecting", n=len(history) + 1), subtle=True)
    return c.build()


def weekly(cfg, snap, history, alerts_log) -> dict:
    c = Card(cfg, "weekly", snap)
    series = daily_series({**history, snap["day"]: snap})
    _pack_block(c, snap, series)
    week = series[-7:]
    if week:
        top = max(v for _, v in week) or 1
        c.heading(T(c.lang, "per_day"))
        c.facts([(dt.date.fromisoformat(d).strftime("%a %d.%m"), f"{_bar(v, top)} {n(v, c.lang)}") for d, v in week])
        c.facts([(T(c.lang, "week_total"), n(sum(v for _, v in week), c.lang))])
    _env_block(c, snap, history, days=7)
    _pool_block(c, snap)
    _agents_block(c, snap)
    _activity_block(c, snap)
    _orphans_block(c, snap, alerts_log)
    c.heading(T(c.lang, "changes"))
    if alerts_log:
        c.facts([(f"{a['day'][5:]} · {a['title']}", a["text"]) for a in alerts_log[-15:]])
    else:
        c.text(T(c.lang, "none"))
    if len(history) < 3:
        c.text(T(c.lang, "collecting", n=len(history) + 1), subtle=True)
    return c.build()


def monthly(cfg, snap, history, month: str | None = None) -> dict:
    """Report for `month` (YYYY-MM): the finished previous month on the 1st, or the running month on request."""
    L = cfg.get("report", {}).get("language", "en")
    all_hist = {**history, snap["day"]: snap}
    month = month or snap["month"]
    in_month = {d: s for d, s in all_hist.items() if (s.get("pack") or {}).get("dataDate", "")[:7] == month}
    last = in_month[max(in_month)] if in_month else snap
    c = Card(cfg, "monthly", last)
    c.heading(month)
    series = [x for x in daily_series(all_hist) if x[0][:7] == month]
    pk = last.get("pack") or {}
    rows = [(T(L, "month_total"), T(L, "pack_line", c=n(pk.get("consumed", 0), L), e=n(pk.get("entitled", 0), L),
                                    p=pct(pk.get("consumed", 0), pk.get("entitled", 0))))]
    if series:
        d, v = max(series, key=lambda x: x[1])
        rows.append((T(L, "peak"), f"{n(v, L)} ({d})"))
    prev_m = (dt.date.fromisoformat(month + "-01") - dt.timedelta(days=1)).strftime("%Y-%m")
    prev = [s for s in all_hist.values() if (s.get("pack") or {}).get("dataDate", "")[:7] == prev_m]
    if prev:
        pp = max(prev, key=lambda s: s["pack"]["dataDate"])["pack"]
        rows.append((T(L, "prev_month"), n(pp["consumed"], L)))
    if pk.get("aiPurchased"):
        rows.append((T(L, "ai"), f"{n(pk.get('aiConsumed', 0), L)} / {n(pk['aiPurchased'], L)}"))
    c.facts(rows)
    if series:
        top = max(v for _, v in series) or 1
        c.heading(T(L, "per_day"))
        c.facts([(d[8:] + "." + d[5:7], f"{_bar(v, top, 10)} {n(v, L)}") for d, v in series])
    _env_block(c, last, history)
    _agents_block(c, last, top=15)
    cons, allocs = last.get("consumption") or {}, last.get("allocations") or {}
    unused = [(cons.get(e, {}).get("name") or (last.get("environments") or {}).get(e, {}).get("name", e), n(a, L))
              for e, a in allocs.items() if a and pct(cons.get(e, {}).get("consumed", 0), a) < 10]
    if unused:
        c.heading(T(L, "unused"), "Warning")
        c.facts(unused)
    _orphans_block(c, last)
    return c.build()


def status(cfg, snap, history, alerts) -> dict:
    c = Card(cfg, "full", snap)
    _pack_block(c, snap, daily_series({**history, snap["day"]: snap}))
    if alerts:
        c.heading(T(c.lang, "changes"))
        c.alerts(alerts)
    _env_block(c, snap, history, days=1)
    _pool_block(c, snap)
    _agents_block(c, snap, top=5)
    _orphans_block(c, snap, alerts)
    return c.build()


def agents(cfg, snap) -> dict:
    """Credits per agent from the licensing report (run_local.py --report agents, with an admin login)."""
    c = Card(cfg, "agents_title", snap)
    _agents_block(c, snap, top=25)
    return c.build()


def m365_users(cfg, snap, users: dict, period: str) -> dict:
    """Microsoft 365 services (Cowork, Copilot Code, …) per person (run_local.py --report m365)."""
    c = Card(cfg, "m365_title", snap)
    c.heading(period)
    rows = sorted(users.values(), key=lambda u: -u["consumed"])
    if rows:
        c.facts([(u.get("name") or "?", T(c.lang, "m365_line", c=n(u["consumed"], c.lang), s=u["sessions"])) for u in rows])
    else:
        c.text(T(c.lang, "none"))
    return c.build()


def help_card(cfg) -> dict:
    L = cfg.get("report", {}).get("language", "en")
    return {"type": "message", "text": f"**{T(L, 'help_title')}**\n\n{T(L, 'help')}"}


def ack(cfg, who: str, kind: str) -> dict:
    L = cfg.get("report", {}).get("language", "en")
    return {"type": "message", "text": T(L, "ack", who=who or "Someone", r=T(L, kind))}
