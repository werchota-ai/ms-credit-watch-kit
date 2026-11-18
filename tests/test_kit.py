"""Offline tests with synthetic data: python -I -m unittest discover -s tests (run from the kit folder)."""
import base64
import copy
import datetime as dt
import hashlib
import hmac
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import analysis  # noqa: E402
import reports  # noqa: E402
import teams  # noqa: E402
from collect import lic_base  # noqa: E402

CFG = {"customer": "Contoso", "tenantId": "11111111-2222-3333-4444-555555555555",
       "report": {"language": "en"}, "pricing": {"currency": "EUR", "packPricePerMonth": 208},
       "thresholds": {"packPercent": [70, 85, 95], "environmentPercent": 80, "spikeFactor": 3, "spikeMinCredits": 200}}


def snap(day: str, consumed: float, env_used: float, alloc=13000):
    return {"time": day + "T06:00:00+00:00", "day": day, "month": day[:7],
            "pack": {"entitled": 25000, "consumed": consumed, "dataDate": (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat(),
                     "aiPurchased": 5500, "aiConsumed": 9823, "allocated": 23000},
            "environments": {"Default-1": {"name": "Contoso (default)", "sku": "Default", "created": "2024-01-01", "url": "", "billingPolicy": None},
                             "e2": {"name": "Sandbox", "sku": "Sandbox", "created": "2026-10-15", "url": "", "billingPolicy": None}},
            "consumption": {"Default-1": {"name": "Contoso (default)", "allocated": alloc, "consumed": env_used, "status": "WithinCapacity"}},
            "allocations": {"Default-1": alloc, "e2": 8000},
            "payg": {}, "orphanFlows": {"f1": {"env": "Contoso (default)", "name": "Old flow", "trigger": "Recurrence", "owner": "disabled"}},
            "agents": {"source": "thresholds", "items": {"a1": {"env": "Default-1", "consumed": 900, "name": "Brain"}}},
            "activity": [{"agent": "Brain", "turns": 85, "conversations": 20, "users": 4, "toolCalls": 221, "errors": 1}]}


def history(days=10, per_day=300, spike_last=False):
    h = {}
    start = dt.date(2026, 11, 2)
    total = 0
    for i in range(days):
        d = start + dt.timedelta(days=i)
        add = per_day * (8 if spike_last and i == days - 1 else 1)
        total += add
        h[d.isoformat()] = snap(d.isoformat(), total, total * 0.8)
    return h


class Tests(unittest.TestCase):
    def test_lic_host(self):
        self.assertEqual(lic_base(CFG["tenantId"]),
                         "https://111111112222333344445555555555.55.tenant.api.powerplatform.com/licensing")

    def test_series_and_forecast(self):
        h = history(10)
        s = analysis.daily_series(h)
        self.assertTrue(all(v == 300 for _, v in s))
        fc = analysis.forecast(h[max(h)], s)
        self.assertEqual(fc["avg"], 300)

    def test_alerts_first_run(self):
        h = history(10)
        last = h.pop(max(h))
        alerts, seen = analysis.evaluate(CFG, last, None, h, [])
        titles = " | ".join(a["title"] for a in alerts)
        self.assertIn("AI Builder", titles)
        self.assertIn("Flow without a live owner", titles)
        # same day again: nothing new
        alerts2, _ = analysis.evaluate(CFG, last, {"month": last["month"], "notified": seen,
                                                   "allocations": last["allocations"], "environments": last["environments"],
                                                   "payg": {}}, h, [])
        self.assertEqual(alerts2, [])

    def test_spike_and_runout(self):
        h = history(10, per_day=2000, spike_last=True)
        last = h.pop(max(h))
        alerts, _ = analysis.evaluate(CFG, last, None, h, [])
        titles = " | ".join(a["title"] for a in alerts)
        self.assertIn("Unusual credit use", titles)
        self.assertIn("run out", titles)

    def test_allocation_change_and_errors(self):
        h = history(5)
        last = h.pop(max(h))
        prev = {"month": last["month"], "notified": {}, "allocations": {"Default-1": 10000, "e2": 8000},
                "environments": last["environments"], "payg": {}}
        alerts, _ = analysis.evaluate(CFG, last, prev, h, ["audit: HTTP 401"])
        texts = json.dumps(alerts, ensure_ascii=False)
        self.assertIn("10,000 → 13,000", texts)
        self.assertIn("Some checks could not run", texts)

    def test_cards_build_en_de(self):
        for lang in ("en", "de"):
            cfg = copy.deepcopy(CFG)
            cfg["report"]["language"] = lang
            h = history(12)
            last = h.pop(max(h))
            alerts, _ = analysis.evaluate(cfg, last, None, h, [])
            for card in (reports.daily(cfg, last, h, alerts), reports.weekly(cfg, last, h, []),
                         reports.monthly(cfg, last, h), reports.status(cfg, last, h, alerts)):
                body = card["attachments"][0]["content"]["body"]
                self.assertTrue(len(body) > 3)
                json.dumps(card)   # serialisable
        self.assertIn("Brain", json.dumps(reports.weekly(CFG, last, h, [])))

    def test_hmac_and_commands(self):
        secret = base64.b64encode(b"0123456789abcdef").decode()
        body = json.dumps({"text": "<at>Credit Watch</at> weekly", "from": {"name": "Anna"}}).encode()
        sig = "HMAC " + base64.b64encode(hmac.new(b"0123456789abcdef", body, hashlib.sha256).digest()).decode()
        self.assertTrue(teams.verify(secret, body, sig))
        self.assertFalse(teams.verify(secret, body + b"x", sig))
        self.assertFalse(teams.verify("", body, sig))
        self.assertEqual(teams.command(json.loads(body)), "weekly")
        self.assertEqual(teams.command({"text": "<at>X</at> Monat"}), "monthly")
        self.assertEqual(teams.command({"text": "<at>X</at> blabla"}), "help")


if __name__ == "__main__":
    unittest.main()
