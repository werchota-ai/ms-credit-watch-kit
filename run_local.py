"""Run Credit Watch on your own PC with your az CLI login (for testing before or after installation).

  python -I run_local.py --config config.json                      status report, printed only
  python -I run_local.py --config config.json --report weekly      daily | weekly | monthly | status
  python -I run_local.py --config config.json --report weekly --post   also post to Teams (TEAMS_WEBHOOK_URL env var)
  python -I run_local.py --config config.json --scheduled          simulate the daily run (keeps history in .local-state)

The audit part needs the function's permission (ActivityFeed.Read); with a normal admin login it reports 401.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))
import engine  # noqa: E402
from collect import Tokens  # noqa: E402
from store import Store  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--report", default="status", choices=["daily", "weekly", "monthly", "status", "agents", "m365"],
                help="agents = credits per agent from Microsoft's licensing report (needs your admin login); "
                     "m365 = Cowork, Copilot Code etc. per person this month (needs: az login --scope "
                     "https://graph.microsoft.com/CopilotCostManagement.Read.All)")
ap.add_argument("--post", action="store_true")
ap.add_argument("--scheduled", action="store_true")
ap.add_argument("--json", action="store_true", help="print the Teams card JSON")
ap.add_argument("--with-audit", action="store_true", help="also try the audit feed (needs the function's permission)")
a = ap.parse_args()

with open(a.config, encoding="utf-8") as f:
    cfg = json.load(f)
if not a.with_audit:   # a normal admin login cannot read the audit feed (401); skip instead of a false red line
    cfg.setdefault("checks", {})["audit"] = False
tokens = Tokens()
store = Store(tokens, folder=os.path.join(HERE, ".local-state"))
hook = os.environ.get("TEAMS_WEBHOOK_URL") if a.post else None
if a.post and not hook:
    sys.exit("Set TEAMS_WEBHOOK_URL first.")

if a.report in ("agents", "m365") and not a.scheduled:
    import datetime as dt
    import collect
    import reports
    from engine import post
    now = dt.datetime.now(dt.timezone.utc)
    snap = {"time": now.isoformat(timespec="seconds"), "day": now.strftime("%Y-%m-%d"), "month": now.strftime("%Y-%m"),
            "pack": {"dataDate": (now - dt.timedelta(days=1)).strftime("%Y-%m-%d")}}
    if a.report == "agents":
        first = now.strftime("%Y-%m-01")
        rows = collect.licensing_report(tokens, "FeatureDetailsPerResource", first, now.strftime("%Y-%m-%d"), "Summary")
        snap["agents"] = collect._agents_from_report(rows, first, now.strftime("%Y-%m-%d"))
        card = reports.agents(cfg, snap)
    else:
        days = [(now.date().replace(day=1) + dt.timedelta(days=i)).isoformat() for i in range(now.day - 1)]
        users = collect.m365_usage_by_user(tokens, days)
        card = reports.m365_users(cfg, snap, users, f"{now.strftime('%Y-%m')}-01 … {(now - dt.timedelta(days=1)).strftime('%Y-%m-%d')}")
    post(hook, card)
    print(card["attachments"][0]["content"]["actions"][0]["card"]["body"][0]["value"])
    print("\nposted to Teams." if hook else "\n(dry run - nothing posted)")
    sys.exit(0)

if a.scheduled:
    res = engine.scheduled(cfg, tokens, store, hook)
    print("sent:", res["sent"] or "nothing (no alerts)")
else:
    res = engine.on_demand(cfg, tokens, store, hook, {"status": "full"}.get(a.report, a.report))
for x in res["alerts"]:
    print(f"[{x['level']}] {x['title']}\n    {x['text']}")
if res["errors"]:
    print("\nERRORS:\n  " + "\n  ".join(res["errors"]))
if a.json and "card" in res:
    print(json.dumps(res["card"], indent=1, ensure_ascii=False))
print("\nposted to Teams." if hook else "\n(dry run - nothing posted)")
