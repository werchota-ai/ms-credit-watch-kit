# Credit Watch: installation guide

This guide installs Credit Watch in your Microsoft 365 tenant, step by step. Allow about **45 minutes**.
You do not need to write code. You copy values into one file and run one script.

After the installation:

- **Every morning** a short card appears in a Teams channel, but only when something needs attention.
- **Every Monday** a weekly report arrives, and on the **1st of the month** a monthly report.
- **At any time** you can ask in the channel: `@Credit Watch status`, `weekly`, `monthly` or `daily`.

---

## Step 1. Check that you have the right permissions

One person can do the whole installation if they have these roles. They can also be split between two people (see the last column).

| What | Role needed | Can be done by |
|---|---|---|
| Entra ID: give the service read permissions | **Global Administrator**, or **Privileged Role Administrator** | Entra admin |
| Power Platform: register the service, read credits | **Power Platform Administrator** | Power Platform admin |
| Dataverse: read-only role in the checked environment(s) | **System Administrator** in that environment | Power Platform admin |
| Azure: create the resource group and service | **Owner** of the Azure subscription | Azure admin |
| Teams: add the channel connections | **Owner** of the team | Team owner |

Teams must allow **outgoing webhooks** (Teams admin center › Teams apps › Permission policies: custom apps allowed). If unsure, ask your Teams admin.

---

## Step 2. Install the three tools (once per PC)

Open **Windows Terminal** or **PowerShell** and run these three lines, one after the other:

```
winget install --id Microsoft.PowerShell -e
winget install --id Microsoft.AzureCLI -e
winget install --id Microsoft.PowerAppsCLI -e
```

Close the window and open **PowerShell 7** (Start menu › *PowerShell 7*, the black icon, **not** "Windows PowerShell").
Check the versions:

```
$PSVersionTable.PSVersion    # must start with 7
az version
pac help
```

Python is **not** needed on your PC.

---

## Step 3. Download the kit

1. Open [github.com/werchota-ai/ms-credit-watch-kit](https://github.com/werchota-ai/ms-credit-watch-kit), select **Code › Download ZIP** (or a version under **Tags**), and unpack it to `C:\credit-watch-kit`.
2. In that folder, copy `config.example.json` and rename the copy to **`config.json`**.

---

## Step 4. Fill in `config.json`

Open `config.json` in Notepad. Change only the values in this table. Keep the quotes.

| Field | What to enter | Where to find it |
|---|---|---|
| `customer` | Your company name, shown on the cards | — |
| `tenantId` | Your tenant ID | [Entra admin center](https://entra.microsoft.com) › Overview › **Tenant ID** |
| `azure.subscriptionId` | The Azure subscription for the service | [Azure portal](https://portal.azure.com) › Subscriptions › **Subscription ID** |
| `azure.location` | Azure region, e.g. `westeurope` | Usually leave as is |
| `azure.resourceGroup` | Name of the new resource group | Leave `rg-credit-watch` |
| `azure.namePrefix` | Short name, letters only | Leave `creditwatch` |
| `azure.owner` | E-mail of the responsible IT person | — |
| `powerPlatform.flowCheckEnvironments` | Environments checked for flows without an owner | Leave `["default"]`. For more: add the environment names, e.g. `["default", "Sales PROD"]` |
| `schedule.dailyCron` | Time of the daily check, in UTC | `0 0 6 * * *` = 06:00 UTC (07:00 Vienna in winter) |
| `schedule.weeklyDay` | Day of the weekly report | `Monday` |
| `schedule.monthlyDay` | Day of the monthly report | `1` |
| `schedule.dailyPost` | `alerts-only` = a card only when something happened; `always` = every day | `alerts-only` |
| `report.language` | `en` or `de` | — |
| `pricing.packPricePerMonth` | Monthly price of your Copilot Credit pack (optional, shows a cost line) | Microsoft 365 admin center › Billing › Your products |

Leave everything else as it is. Save the file.

---

## Step 5. Create the Teams channel and the incoming connection

The service posts its cards through a Teams **Workflow**.

1. In Teams, open the team where IT works, e.g. **IT**.
2. Create a channel: **…** next to the team › **Add channel** › name **Credit Watch** › **Add**.
3. In the list on the left, point at the new channel **Credit Watch** › click **…** (More options) next to its name › choose the menu item **Workflows**.
   Do not type anything into the channel: *Workflows* is a menu item, not a message.
   (If the menu has no *Workflows*: left bar › **Apps** › **Workflows** › **Create**.)
4. In the template search type `webhook` › choose **Send webhook alerts to a channel** › name: `Credit Watch` › **Next**.
5. Check team and channel › **Add workflow**.
6. In the window that opens, click **Copy webhook link** (a long address starting with `https://`). Keep it for step 6.
   Closed it by mistake? Workflows app › **Home** › `Credit Watch` › **Copy webhook link**.

> This address works like a password for the channel. Do not post it anywhere.

---

## Step 6. Run the installation

In **PowerShell 7**:

```
cd C:\credit-watch-kit
az login --tenant <your tenant ID>
pac auth create --tenant <your tenant ID>
.\install.ps1 -Config .\config.json -TeamsWebhook '<URL from step 5>'
```

- A browser window opens twice for sign-in. Use your admin account.
- The script runs about **5–10 minutes**. It shows steps `1/8` to `8/8`.
- It is safe to run again: what already exists is skipped.

At the end it shows:

```
Done.
Callback URL for the Teams outgoing webhook (INSTALL.md, step 7):
  https://func-creditwatch-xxxxxx.azurewebsites.net/api/teams
```

Copy this **callback URL** for step 7.

---

## Step 7. Let the team ask Credit Watch for reports

1. In Teams, next to the team name: **…** › **Manage team** › tab **Apps**.
2. Bottom right: **Create an outgoing webhook**.
3. Fill in:

| Field | Value |
|---|---|
| Name | `Credit Watch` |
| Callback URL | the callback URL from step 6 |
| Description | `Copilot credit reports. Mention me with: status, daily, weekly, monthly` |

4. **Create**. A **security token** appears. **Copy it now**: it is shown only once.
5. In PowerShell 7:

```
.\install.ps1 -Config .\config.json -CodeOnly -TeamsOutgoingSecret '<security token>'
```

---

## Step 8. Test

In the **Credit Watch** channel, write a new post:

```
@Credit Watch status
```

(Type `@Credit` and pick **Credit Watch** from the list.)

- Within seconds Credit Watch answers: *"… asked for the status report. It arrives here in about a minute."*
- About a minute later the **status card** appears.

Also try `@Credit Watch help`. If something does not work, see **Troubleshooting** below.

The **first scheduled check** runs the next morning. Trends (credits per day, forecast) become meaningful after a few days, because the service builds up its own history.

---

## What the reports show

| Report | When | Content |
|---|---|---|
| **Daily** | every morning, only if something happened (or on request) | credit pack used, last day, forecast for month end, alerts, per environment |
| **Weekly** | Mondays (or on request) | credits per day for 7 days, week total, per environment, top agents, flows without an owner, all changes of the week |
| **Monthly** | the 1st, for the previous month (or on request, for the running month) | month total, busiest day, comparison with the previous month, per environment and agent, allocated but unused credits |
| **Status** | on request | everything current |

Alerts the service sends:

| Alert | Meaning |
|---|---|
| Credit pack at 70 / 85 / 95 % | share of the monthly pack used |
| Pack will run out before the month ends | forecast from the last 7 days |
| Unusual credit use | one day used much more than usual (default: 3× the average and at least 200 credits) |
| Environment over / near its allocation | an environment used ≥ 80 % or more than its allocated credits |
| Using credits without its own allocation | an environment draws from the shared pool |
| AI Builder credits over the pack | AI Builder use above the purchased amount |
| Credit allocation changed / new environment / pay-as-you-go link changed | admin changes, with who and when |
| Flow without a live owner | an active flow whose owner account is disabled or deleted |
| **Some checks could not run** (red) | a check failed; the reason is shown. The service never stays silent about a failed check. |

Every card has a **Copy as text** button (Teams cannot copy text directly from a card).

---

## Optional: agent activity from Application Insights (KQL)

Copilot Studio can send agent telemetry (turns, tools, models, errors) of a **managed environment** to Application Insights. Credit Watch then adds an *Agent activity* block to the weekly report. The file `kql\agent-activity.kql` contains ready queries for the Azure portal.

> **Managed environments** require premium licences for the users of that environment. Check your licensing before you turn this on.

1. Power Platform admin center › **Admin** (or **Manage**) › **Data export** › **App Insights** › **New data export**.
2. Export type **Copilot Studio**, choose the environment and an Application Insights resource › **Create**.
3. In the Azure portal, open that Application Insights › **Workspace** link › copy **Workspace ID** and the **Resource ID** (Properties).
4. In `config.json`, fill `appInsights.workspaceId` and `appInsights.workspaceResourceId`.
5. Run `.\install.ps1 -Config .\config.json` again.

Data can take up to 24 hours to arrive.

---

## Troubleshooting

| What you see | Cause | Fix |
|---|---|---|
| `Please run this in PowerShell 7` | started in Windows PowerShell 5.1 | open **PowerShell 7** (step 2) |
| `az is signed in to tenant …` | wrong tenant | `az login --tenant <tenant ID>` |
| `pac is not signed in to tenant …` | wrong or no pac profile | `pac auth create --tenant <tenant ID>` |
| Step 7/8: warning *System Administrator role* | your account has no rights in that environment | Power Platform admin center › Environments › the environment › **Settings** › Users › add yourself as System Administrator, then run again |
| Red line *orphanFlows: Dataverse HTTP 403* | read-only role missing in that environment | run `install.ps1` again (step 6) |
| Red line *audit* on the first day | the audit feed starts some hours after installation | wait one day |
| `@Credit Watch` does not answer | outgoing webhook missing or wrong token | redo step 7 (create a new webhook, use the new token) |
| Answer comes, but no card | incoming workflow switched off or deleted | Teams › Workflows › check `Credit Watch` is on; or redo step 5 and run step 6 again |
| No morning card | nothing to report (that is normal with `alerts-only`) | ask `@Credit Watch status` |

The service's own log: Azure portal › resource group `rg-credit-watch` › Application Insights › **Logs**, query 7 in `kql\agent-activity.kql`.

---

## Remove Credit Watch

```
.\install.ps1 -Config .\config.json -Uninstall
```

This deletes the resource group, the service and all its permissions, and the read-only Dataverse role.
Then remove the two Teams connections by hand: **Workflows** › `Credit Watch` › Delete, and **Manage team › Apps** › `Credit Watch` (outgoing webhook) › Remove.

---

## Security and cost

- **Read only.** The service can read credit figures, environments, users' enabled/disabled state, flows and the Power Platform audit log. It cannot change anything in Microsoft 365 or Power Platform. It writes only to its own private storage and to the one Teams channel.
- **No passwords or secrets in files.** It signs in with an Azure managed identity. The Teams addresses are kept in the service settings.
- **Teams commands are signed.** Requests without the correct Teams signature are rejected.
- **Cost:** usually **under €1 per month** (Azure Functions Flex Consumption, small storage, 30-day logs).
- **Data:** the daily snapshots (numbers, environment and flow names, no message content) stay in your storage account.
