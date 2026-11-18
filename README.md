# Credit Watch

**Know where your Copilot credits go, before they run out.**

Copilot Studio agents, agent flows and Copilot Cowork all draw on the same pool of Copilot Credits.
When the pool or an environment's allocation is empty, agents stop answering. Microsoft's own warnings
reach only some admins, often late, and nothing tells you *which* agent used the credits.

Credit Watch is a small service in your own Azure subscription. Every morning it reads your credit figures
from Microsoft and posts a short card to a Teams channel, and only when something needs attention.

## What you get

| | |
|---|---|
| **Early warning** | Pack at 70 / 85 / 95 %, forecast for the end of the month, the day the pack will run out |
| **Who uses the credits** | Credits per agent and per flow, with the feature behind them (for example *Process Agent*, *Agent action*), taken from Microsoft's official licensing report (optional, needs one extra admin role, see below) |
| **Per environment** | Used versus allocated; environments that use credits without their own allocation |
| **Unusual days** | A day with about three times the usual use is flagged |
| **Changes nobody announces** | Allocations changed, pay-as-you-go linked or unlinked, environments created or removed, and who did it |
| **Forgotten flows** | Flows that still run under a disabled or deleted account |
| **Reports** | Weekly on Monday, monthly on the 1st, in English or German |
| **On request** | Type `@Credit Watch status`, `daily`, `weekly` or `monthly` in the channel |

Example of a weekly card (synthetic data):

```
Copilot credit watch · Weekly report
Contoso GmbH · Data as of 2026-11-17

Credit pack            17,200 of 25,000 used (69 %)
Month-end forecast     30,400 / 25,000
Pack runs out around   2026-11-24

By environment (used / allocated)
Contoso (default)      14,100 / 20,000
Sales Pilot             3,100 / 0

Top agents by credits (this month)
HR Assistant           12,800 · Process Agent
Sales Pilot             3,100 · Agent action 2,700, Classic answer 400
IT Helpdesk             1,300 · Generative answer
```

## Safe by design

- **Read only.** It reads figures and settings and never changes anything in Microsoft 365 or Power Platform.
  Its permissions are read permissions, with one optional exception: credits per agent come from a Microsoft report
  that is only given to Power Platform administrators. If you want those figures, you give the service that role
  (it can then technically change Power Platform settings, although the code only reads). Without it, everything
  else works and the card says that per-agent figures are not available.
- **Runs in your tenant.** Your Azure subscription, your storage, your Teams channel. No data leaves your tenant, and
  no message content is read.
- **No passwords in files.** It signs in with an Azure managed identity; Teams commands are checked with a signature.
- **Low cost.** Usually under €1 per month in Azure (Functions Flex Consumption and a small storage account).
- **Easy to remove.** One command deletes the service and all its permissions.

## Getting started

About 45 minutes, no coding: fill in one file (`config.json`) and run one script.
Step-by-step guide: **[INSTALL.md](INSTALL.md)**. Changes per version: **[CHANGELOG.md](CHANGELOG.md)**.

You need a Power Platform administrator, an Azure subscription owner and a Teams team owner
(one person can have all three roles).

Built and maintained by [werchota.ai](https://www.werchota.ai). We are happy to install it with you, adapt the alerts
to your needs, or connect it to your Copilot Studio governance.

---

## For administrators and developers

### Files

| Path | Purpose |
|---|---|
| `config.example.json` | template; copy to `config.json` per customer |
| `install.ps1` | install / update (`-CodeOnly`) / remove (`-Uninstall`); pwsh 7, az, pac |
| `src/collect.py` | read-only data collection (APIs below) |
| `src/analysis.py` | daily use, forecast, run-out date, spike detection, alerts |
| `src/reports.py`, `src/i18n.py` | Teams Adaptive Cards (en, de) |
| `src/engine.py` | scheduled run and on-demand reports |
| `src/teams.py` | outgoing-webhook HMAC check and command parsing |
| `src/function_app.py` | Azure Functions: timer, HTTP (`/api/teams`), queue |
| `run_local.py` | test with your own az login, optional `--post` to Teams |
| `tests/` | offline tests with synthetic data: `python -I -m unittest discover -s tests` |
| `kql/agent-activity.kql` | KQL for Copilot Studio telemetry in Application Insights |

### Data sources

| Data | Source | Note |
|---|---|---|
| Pack total, AI Builder pool | `{tenant}.tenant.api.powerplatform.com/licensing/entitlements/MCSMessages`, `/tenantCapacity/CurrencyReports` (`api-version=1`) | internal PPAC endpoints, may change without notice; a failure shows as a red line |
| Per environment used/allocated | same host, `/environments/entitlementConsumptions/MCSMessages` | |
| Allocations, pay-as-you-go | `api.powerplatform.com/licensing` (public, preview) | billing-policy list is often refused to service principals → environments' own link used |
| Per agent and flow, by feature, channel, model | Official **Copilot Studio licensing report** `FeatureDetailsPerResource` ([Power Platform API 2024-10-01](https://learn.microsoft.com/rest/api/power-platform/copilotstudio/licensing-reports), public preview since Nov 2026): `POST …/copilotstudio/licensing/reports/{name}` → poll → gzip CSV | **needs the Entra role Power Platform Administrator for the service's managed identity** (otherwise HTTP 403, InsufficientPermissions); usually ready in under a minute, at most `reportWaitSeconds` is waited, so only the daily run asks it; on-demand reports reuse the last daily result. Fallbacks: `…/licensing/entitlements/MCSMessages/resources`, then `/resourceThresholds` |
| Environments | BAP admin API | |
| Flows without a live owner | Dataverse `workflows` (read-only role) + Flow admin API; Graph `/users` | Flow admin API hides solution-aware flows from service principals |
| Who changed what | Office 365 Management Activity API (`Audit.General`, Power Platform operations) | starts some hours after install; window ≤ 24 h |
| Agent activity (optional) | Log Analytics query on `AppDependencies` (Copilot Studio environment-level telemetry) | needs managed environment + data export |

Daily history (one JSON per day) is kept in the service's own storage; trends and forecasts are computed from it.

### Not covered (Microsoft offers no API yet)

- M365 admin center › Copilot › Cost management › **Credit requests** (check weekly by hand).
- Token counts per message (Microsoft reports show credits, not tokens; reasoning models: 1 credit ≈ 100 billed tokens).

## License

[Apache License 2.0](LICENSE). You may use, change and share Credit Watch, also commercially. When you pass on a copy
or a changed version, keep the [NOTICE](NOTICE) file with it. The names and brand of werchota.ai are not covered by the license.
