# Changelog

## v1.2 (18 Nov 2026)

- Cards no longer list a flow twice: a flow already shown as an alert is left out of the flows list below it.
- No "(+0)" next to environments without use.
- The daily run logs where the per-agent figures came from, the time per check, and any fallback used
  (Application Insights › traces).

## v1.1 (18 Nov 2026)

- **Credits per agent from Microsoft's official licensing report.** The daily run now reads the Copilot Studio
  licensing report `FeatureDetailsPerResource` through the Power Platform API (public preview, announced in
  Message Center MC1558020 on 17 Nov 2026). It gives billed and non-billed credits per agent and per flow, with
  name, environment, feature (for example *Process Agent*, *Agent action*, *Classic answer*), channel and model.
  Before, per-agent figures depended on APIs that some tenants refuse to service identities.
- The weekly, monthly and status cards show the top features next to each agent, plus where the figures come from.
- Requests from Teams stay fast: they reuse the report of the last daily run of the month instead of waiting for a new one.
- The daily run waits at most 10 minutes for the report (`reportWaitSeconds` in `config.json`). If Microsoft is
  slower, the job is remembered and collected by the next daily run; until then the last figures are shown.
- Each snapshot records how long every check took (`timings`), to find slow parts quickly.
- If the report cannot be read, the older per-agent sources are used as before and the reason is kept in the
  snapshot (`notes`), without a red line in the card.
- New switch in `config.json`: `checks.reportsApi` (default `true`).

## v1.0 (14 Nov 2026)

First release: daily, weekly and monthly reports and on-demand commands in a Teams channel; pack, environment,
allocation, pay-as-you-go, orphan-flow and admin-change checks; English and German.
