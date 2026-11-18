"""Card texts in English and German. Add a language by copying the "en" block."""

TEXT = {
    "en": {
        "daily": "Daily report", "weekly": "Weekly report", "monthly": "Monthly report", "full": "Status report",
        "data_as_of": "Data as of {d} · checked {t} UTC",
        "pack": "Credit pack", "pack_line": "{c} of {e} used ({p} %)",
        "yesterday": "Last day", "avg7": "Average per day (7 days)",
        "projection": "Month-end forecast", "runout": "Pack runs out around",
        "no_runout": "lasts until the end of the month",
        "by_env": "By environment (used / allocated)", "env_line": "{c} / {a}{d}",
        "ai": "AI Builder credits", "orphans": "Flows without a live owner",
        "per_day": "Credits per day", "week_total": "This week", "month_total": "This month",
        "prev_month": "Previous month", "peak": "Busiest day", "unused": "Allocated but unused",
        "changes": "Changes and alerts", "none": "Nothing to report.",
        "collecting": "History builds up: {n} day(s) so far. Trends appear after a few days.",
        "cost": "Estimated cost", "help_title": "Commands",
        "help": "Mention me with one word: **daily**, **weekly**, **monthly** or **status**. "
                "The report arrives in this channel within about a minute.",
        "ack": "{who} asked for the {r}. It arrives here in about a minute.",
        "copy": "Copy as text", "open": "Open in Power Platform admin center",
        "agents": "Top agents by credits (this month)", "limit": "limit",
        "agents_na": "Not available yet: Microsoft does not give per-agent figures to service identities in this tenant. "
                     "See PPAC › Licensing › Copilot Studio › Download report.",
        "activity": "Agent activity, last 7 days (Application Insights)",
        "activity_line": "{t} turns · {v} conversations · {u} users · {x} tool calls · {e} errors",
        # alerts
        "a_pack": "Credit pack at {p} %", "a_pack_t": "{c} of {e} credits used this month.",
        "a_runout": "Pack will run out before the month ends", "a_runout_t": "At the current pace it is empty around {d}.",
        "a_spike": "Unusual credit use", "a_spike_t": "{c} credits on {d}, about {x}× the usual daily use.",
        "a_ai": "AI Builder credits over the pack", "a_ai_t": "{c} of {e} used ({p} %).",
        "a_env_over": "{n}: over its allocation", "a_env_high": "{n}: at {p} % of its allocation",
        "a_env_pool": "{n}: using credits without its own allocation", "a_env_t": "{c} used, {a} allocated.",
        "a_alloc": "Credit allocation changed", "a_alloc_t": "{n}: {o} → {v}",
        "a_env_new": "New environment", "a_env_new_t": "{n} ({s}), created {d}",
        "a_env_gone": "Environment removed",
        "a_payg": "Pay-as-you-go link changed", "a_payg_t": "Policy {n} now linked to: {e}",
        "a_flow": "Flow without a live owner", "a_flow_t": "{n} ({e}), owner account {o}{x}",
        "a_flow_unknown": ", schedule unknown",
        "a_audit": "Admin change", "a_audit_t": "{k} by {u} at {t} UTC{a}",
        "a_errors": "Some checks could not run",
        "disabled": "disabled", "deleted": "deleted", "nobody": "none",
    },
    "de": {
        "daily": "Tagesbericht", "weekly": "Wochenbericht", "monthly": "Monatsbericht", "full": "Statusbericht",
        "data_as_of": "Datenstand {d} · geprüft {t} UTC",
        "pack": "Kontingent", "pack_line": "{c} von {e} verbraucht ({p} %)",
        "yesterday": "Letzter Tag", "avg7": "Durchschnitt pro Tag (7 Tage)",
        "projection": "Prognose Monatsende", "runout": "Kontingent aufgebraucht etwa am",
        "no_runout": "reicht bis Monatsende",
        "by_env": "Nach Umgebung (verbraucht / zugewiesen)", "env_line": "{c} / {a}{d}",
        "ai": "AI-Builder-Credits", "orphans": "Flows ohne aktiven Besitzer",
        "per_day": "Credits pro Tag", "week_total": "Diese Woche", "month_total": "Dieser Monat",
        "prev_month": "Vormonat", "peak": "Stärkster Tag", "unused": "Zugewiesen, aber ungenutzt",
        "changes": "Änderungen und Warnungen", "none": "Nichts zu melden.",
        "collecting": "Verlauf wird aufgebaut: bisher {n} Tag(e). Trends erscheinen nach einigen Tagen.",
        "cost": "Geschätzte Kosten", "help_title": "Befehle",
        "help": "Erwähnen Sie mich mit einem Wort: **täglich**, **woche**, **monat** oder **status**. "
                "Der Bericht kommt in etwa einer Minute in diesen Kanal.",
        "ack": "{who} hat den {r} angefordert. Er kommt in etwa einer Minute.",
        "copy": "Als Text kopieren", "open": "Im Power Platform Admin Center öffnen",
        "agents": "Top-Agenten nach Credits (dieser Monat)", "limit": "Limit",
        "agents_na": "Noch nicht verfügbar: Microsoft liefert Werte pro Agent in diesem Tenant nicht an Dienstidentitäten. "
                     "Siehe PPAC › Lizenzierung › Copilot Studio › Bericht herunterladen.",
        "activity": "Agenten-Aktivität, letzte 7 Tage (Application Insights)",
        "activity_line": "{t} Turns · {v} Unterhaltungen · {u} Nutzer · {x} Tool-Aufrufe · {e} Fehler",
        "a_pack": "Kontingent bei {p} %", "a_pack_t": "{c} von {e} Credits in diesem Monat verbraucht.",
        "a_runout": "Kontingent reicht nicht bis Monatsende", "a_runout_t": "Beim aktuellen Tempo leer etwa am {d}.",
        "a_spike": "Ungewöhnlicher Verbrauch", "a_spike_t": "{c} Credits am {d}, etwa {x}× so viel wie üblich.",
        "a_ai": "AI-Builder-Credits über dem Kontingent", "a_ai_t": "{c} von {e} verbraucht ({p} %).",
        "a_env_over": "{n}: über der Zuweisung", "a_env_high": "{n}: bei {p} % der Zuweisung",
        "a_env_pool": "{n}: verbraucht ohne eigene Zuweisung", "a_env_t": "{c} verbraucht, {a} zugewiesen.",
        "a_alloc": "Zuweisung geändert", "a_alloc_t": "{n}: {o} → {v}",
        "a_env_new": "Neue Umgebung", "a_env_new_t": "{n} ({s}), erstellt am {d}",
        "a_env_gone": "Umgebung entfernt",
        "a_payg": "Pay-as-you-go-Verknüpfung geändert", "a_payg_t": "Richtlinie {n} jetzt verknüpft mit: {e}",
        "a_flow": "Flow ohne aktiven Besitzer", "a_flow_t": "{n} ({e}), Besitzerkonto {o}{x}",
        "a_flow_unknown": ", Zeitplan unbekannt",
        "a_audit": "Admin-Änderung", "a_audit_t": "{k} durch {u} um {t} UTC{a}",
        "a_errors": "Einige Prüfungen konnten nicht laufen",
        "disabled": "deaktiviert", "deleted": "gelöscht", "nobody": "keine",
    },
}


def T(lang: str, key: str, **kw) -> str:
    s = TEXT.get(lang, TEXT["en"]).get(key) or TEXT["en"].get(key, key)
    return s.format(**kw) if kw else s


def n(v, lang: str = "en") -> str:
    """Thousands separator: 14,195 (en) / 14.195 (de)."""
    s = f"{float(v):,.0f}"
    return s.replace(",", ".") if lang == "de" else s
