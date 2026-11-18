# Credit Watch kit

Watches Copilot Studio / Copilot Credits and Power Platform admin changes in one tenant and reports to a Teams channel:
daily (only when something happens), weekly, monthly, and on request (`@Credit Watch status|daily|weekly|monthly`).
Tenant-independent: everything comes from `config.json`. Installation: see **[INSTALL.md](INSTALL.md)**.

## Files

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

## Data sources

| Data | Source | Note |
|---|---|---|
| Pack total, AI Builder pool | `{tenant}.tenant.api.powerplatform.com/licensing/entitlements/MCSMessages`, `/tenantCapacity/CurrencyReports` (`api-version=1`) | internal PPAC endpoints, may change without notice; a failure shows as a red line |
| Per environment used/allocated | same host, `/environments/entitlementConsumptions/MCSMessages` | |
| Allocations, pay-as-you-go | `api.powerplatform.com/licensing` (public, preview) | billing-policy list is often refused to service principals → environments' own link used |
| Per agent | `api.powerplatform.com/licensing/entitlements/MCSMessages/resources` (2024-10-01); fallback `/resourceThresholds` | per-resource API may return 403 in some tenants |
| Environments | BAP admin API | |
| Flows without a live owner | Dataverse `workflows` (read-only role) + Flow admin API; Graph `/users` | Flow admin API hides solution-aware flows from service principals |
| Who changed what | Office 365 Management Activity API (`Audit.General`, Power Platform operations) | starts some hours after install; window ≤ 24 h |
| Agent activity (optional) | Log Analytics query on `AppDependencies` (Copilot Studio environment-level telemetry) | needs managed environment + data export |

Daily history (one JSON per day) is kept in the service's own storage; trends and forecasts are computed from it.

## Not covered (Microsoft offers no API yet)

- M365 admin center › Copilot › Cost management › **Credit requests** (check weekly by hand).
- Token counts per message (Microsoft reports show credits, not tokens; reasoning models: 1 credit ≈ 100 billed tokens).
