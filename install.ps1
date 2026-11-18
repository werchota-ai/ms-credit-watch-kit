# Credit Watch - installer. Run in PowerShell 7 (pwsh), signed in with az and pac to the CUSTOMER tenant.
#
#   .\install.ps1 -Config .\config.json -TeamsWebhook '<incoming webhook url>'     first install (safe to re-run)
#   .\install.ps1 -Config .\config.json -TeamsOutgoingSecret '<secret>'           after creating the Teams outgoing webhook
#   .\install.ps1 -Config .\config.json -CodeOnly                                 update the code only
#   .\install.ps1 -Config .\config.json -Uninstall                                remove everything this script created
#
# What it creates (all tagged): resource group, storage account (private), Log Analytics + Application Insights,
# Function App (Python, Flex Consumption) with a managed identity. The identity gets READ-ONLY rights:
# Graph User.Read.All, Office 365 audit feed (ActivityFeed.Read), Power Platform management-app registration,
# and a read-only Dataverse role "Credit Watch Reader" in the environments listed in the config.
param(
  [Parameter(Mandatory)] [string]$Config,
  [string]$TeamsWebhook, [string]$TeamsOutgoingSecret,
  [switch]$CodeOnly, [switch]$Uninstall
)
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'Please run this in PowerShell 7 (pwsh), not Windows PowerShell 5.1.' }
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$Kit = $PSScriptRoot
$cfg = Get-Content $Config -Raw | ConvertFrom-Json

# ---------------------------------------------------------------- names (derived, globally unique)
$Tenant = $cfg.tenantId; $Sub = $cfg.azure.subscriptionId; $Loc = $cfg.azure.location; $Rg = $cfg.azure.resourceGroup
$prefix = ($cfg.azure.namePrefix -replace '[^a-zA-Z0-9]', '').ToLower()
$hash = -join ([System.Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes("$Tenant$Sub$prefix"))[0..2] | ForEach-Object { $_.ToString('x2') })
$Func    = "func-$prefix-$hash"
$Storage = ("st" + $prefix).Substring(0, [Math]::Min(18, 2 + $prefix.Length)) + $hash
$Law     = "law-$prefix"; $Appi = "appi-$prefix"
$RoleName = 'Credit Watch Reader'
$Privs = 'prvReadWorkflow','prvReadflowrun','prvReadUser','prvReadOrganization','prvReadBusinessUnit','prvReadbot'
$Tags = [ordered]@{ project = 'credit-watch'; purpose = 'Daily Copilot credit and Power Platform checks, posts to Teams'
  owner = $cfg.azure.owner; customer = $cfg.customer; 'managed-by' = 'credit-watch-kit install.ps1'; access = 'read-only' }

function Step($t) { Write-Host "`n== $t" -ForegroundColor Cyan }
function AzTry { param([Parameter(ValueFromRemainingArguments)]$a)
  $PSNativeCommandUseErrorActionPreference = $false
  $out = & az @a -o json 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
  return ($out | Out-String | ConvertFrom-Json)
}
function AzRest { param($Method, $Url, $Body)      # JSON body through a file: az.cmd would mangle & and quotes
  $f = Join-Path $env:TEMP ("cw-" + [guid]::NewGuid().ToString('N') + '.json')
  if ($null -ne $Body) { $Body | ConvertTo-Json -Depth 12 | Set-Content $f -Encoding utf8 }
  try {
    if ($null -ne $Body) { az rest --method $Method --url $Url --body "@$f" --headers 'Content-Type=application/json' -o none }
    else { az rest --method $Method --url $Url -o none }
  } finally { Remove-Item $f -ErrorAction SilentlyContinue }
}
function Set-Tags($Id) { AzRest PUT "https://management.azure.com$Id/providers/Microsoft.Resources/tags/default?api-version=2021-04-01" @{ properties = @{ tags = $Tags } } }
function Grant-AppRole($MiObjectId, $ApiAppId, $RoleValue) {
  $api  = az ad sp show --id $ApiAppId -o json | ConvertFrom-Json
  $role = $api.appRoles | Where-Object { $_.value -eq $RoleValue -and $_.allowedMemberTypes -contains 'Application' }
  $have = (az rest --method GET --url "https://graph.microsoft.com/v1.0/servicePrincipals/$MiObjectId/appRoleAssignments" -o json | ConvertFrom-Json).value
  if ($have | Where-Object { $_.appRoleId -eq $role.id -and $_.resourceId -eq $api.id }) { Write-Host "  ${RoleValue}: already granted"; return }
  AzRest POST "https://graph.microsoft.com/v1.0/servicePrincipals/$MiObjectId/appRoleAssignments" @{ principalId = $MiObjectId; resourceId = $api.id; appRoleId = $role.id }
  Write-Host "  ${RoleValue}: granted"
}
# Dataverse environments to give the read-only role (from config.powerPlatform.flowCheckEnvironments)
function Get-TargetEnvironments {
  $tok = az account get-access-token --resource https://service.powerapps.com/ --query accessToken -o tsv
  $all = (Invoke-RestMethod -Headers @{ Authorization = "Bearer $tok" } `
          -Uri 'https://api.bap.microsoft.com/providers/Microsoft.BusinessAppPlatform/scopes/admin/environments?api-version=2020-10-01').value
  $want = @($cfg.powerPlatform.flowCheckEnvironments)
  foreach ($e in $all) {
    $url = $e.properties.linkedEnvironmentMetadata.instanceUrl
    if (-not $url) { continue }
    $ok = ($want -contains 'all') -or ($want -contains 'default' -and $e.name -like 'Default-*') -or ($want -contains $e.properties.displayName) -or ($want -contains $e.name) -or ($want -contains $url.TrimEnd('/'))
    if ($ok) { [pscustomobject]@{ Name = $e.properties.displayName; Url = $url.TrimEnd('/') } }
  }
}
function Dv($Org, $Method, $Path, $Body) {
  $tok = az account get-access-token --resource $Org --query accessToken -o tsv
  $p = @{ Method = $Method; Uri = "$Org/api/data/v9.2/$Path"; Headers = @{ Authorization = "Bearer $tok"; Accept = 'application/json'; 'Content-Type' = 'application/json' } }
  if ($Body) { $p.Body = ($Body | ConvertTo-Json -Depth 6) }
  Invoke-RestMethod @p
}

# ---------------------------------------------------------------- preflight
Step 'Checks'
$acct = az account show -o json | ConvertFrom-Json
if ($acct.tenantId -ne $Tenant) { throw "az is signed in to tenant $($acct.tenantId), config says $Tenant. Run: az login --tenant $Tenant" }
az account set --subscription $Sub
Write-Host "  az: $($acct.user.name), subscription $Sub"
if (-not $CodeOnly) {
  $pacOut = pac auth who 2>&1 | Out-String
  if ($pacOut -notmatch $Tenant) { throw "pac is not signed in to tenant $Tenant. Run: pac auth create --tenant $Tenant" }
  Write-Host '  pac: signed in to the right tenant'
}
Write-Host "  names: $Rg / $Func / $Storage"

# ---------------------------------------------------------------- uninstall
if ($Uninstall) {
  Step 'Uninstall'
  $mi = AzTry functionapp identity show -g $Rg -n $Func
  if ($mi) {
    $miApp = az ad sp show --id $mi.principalId --query appId -o tsv
    foreach ($e in Get-TargetEnvironments) {
      try {
        $u = (Dv $e.Url GET "systemusers?`$select=systemuserid&`$filter=applicationid eq $miApp").value | Select-Object -First 1
        $r = (Dv $e.Url GET "roles?`$select=roleid&`$filter=name eq '$RoleName'").value
        foreach ($x in $r) { if ($u) { try { Dv $e.Url DELETE "systemusers($($u.systemuserid))/systemuserroles_association($($x.roleid))/`$ref" } catch {} } }
        if ($u) { Dv $e.Url PATCH "systemusers($($u.systemuserid))" @{ isdisabled = $true } }
        foreach ($x in $r) { try { Dv $e.Url DELETE "roles($($x.roleid))" } catch {} }
        Write-Host "  $($e.Name): role removed"
      } catch { Write-Warning "  $($e.Name): $($_.Exception.Message)" }
    }
    $PSNativeCommandUseErrorActionPreference = $false
    pac admin application unregister --application-id $miApp | Out-Null
    $PSNativeCommandUseErrorActionPreference = $true
    Write-Host '  Power Platform registration removed'
  }
  az group delete -n $Rg --yes
  Write-Host "Done. Resource group $Rg deleted (the managed identity and its permissions are gone with it)." -ForegroundColor Yellow
  Write-Host 'Remove the two Teams webhooks by hand (see INSTALL.md, step 9).' -ForegroundColor Yellow
  exit 0
}

if (-not $CodeOnly) {
  Step '1/8 Resource group, logs, Application Insights'
  az group create -n $Rg -l $Loc -o none
  Set-Tags (az group show -n $Rg --query id -o tsv)
  if (-not (AzTry monitor log-analytics workspace show -g $Rg -n $Law)) { az monitor log-analytics workspace create -g $Rg -n $Law -l $Loc --retention-time 30 -o none }
  $lawId = az monitor log-analytics workspace show -g $Rg -n $Law --query id -o tsv; Set-Tags $lawId
  if (-not (AzTry monitor app-insights component show -g $Rg --app $Appi)) { az monitor app-insights component create -g $Rg --app $Appi -l $Loc --workspace $lawId -o none }
  Set-Tags (az monitor app-insights component show -g $Rg --app $Appi --query id -o tsv)

  Step '2/8 Storage account (private) for state and history'
  if (-not (AzTry storage account show -g $Rg -n $Storage)) {
    az storage account create -g $Rg -n $Storage -l $Loc --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 --allow-blob-public-access false --https-only true -o none
  }
  $stId = az storage account show -g $Rg -n $Storage --query id -o tsv; Set-Tags $stId

  Step '3/8 Function App + managed identity'
  if (-not (AzTry functionapp show -g $Rg -n $Func)) {
    az functionapp create -g $Rg -n $Func --storage-account $Storage --flexconsumption-location $Loc --runtime python --runtime-version 3.12 --app-insights $Appi -o none
  }
  az functionapp identity assign -g $Rg -n $Func -o none
  $siteId = az functionapp show -g $Rg -n $Func --query id -o tsv
  AzRest PATCH "https://management.azure.com$siteId`?api-version=2023-12-01" @{ properties = @{ httpsOnly = $true } }
  Set-Tags $siteId
  Set-Tags (az rest --method GET --url "https://management.azure.com$siteId`?api-version=2023-12-01" --query properties.serverFarmId -o tsv)
  $mi = az functionapp identity show -g $Rg -n $Func --query principalId -o tsv
  $miApp = az ad sp show --id $mi --query appId -o tsv
  Write-Host "  managed identity: $miApp"

  Step '4/8 Storage rights for the identity (own account only)'
  foreach ($r in 'Storage Blob Data Contributor','Storage Queue Data Contributor') {
    az role assignment create --assignee-object-id $mi --assignee-principal-type ServicePrincipal --role $r --scope $stId -o none
  }
  az storage container create --account-name $Storage -n state --auth-mode login -o none

  Step '5/8 Read-only API permissions for the identity'
  Grant-AppRole $mi '00000003-0000-0000-c000-000000000000' 'User.Read.All'
  Grant-AppRole $mi 'c5393580-f805-4401-95e8-94b7a6ef2fc2' 'ActivityFeed.Read'
  if ($cfg.appInsights.workspaceResourceId) {
    az role assignment create --assignee-object-id $mi --assignee-principal-type ServicePrincipal --role 'Log Analytics Reader' --scope $cfg.appInsights.workspaceResourceId -o none
    Write-Host '  Log Analytics Reader on the agent telemetry workspace'
  }

  Step '6/8 Power Platform: register the identity as admin management app'
  $PSNativeCommandUseErrorActionPreference = $false
  $reg = pac admin application register --application-id $miApp 2>&1 | Out-String
  $PSNativeCommandUseErrorActionPreference = $true
  if ($LASTEXITCODE -ne 0 -and $reg -notmatch 'already') { throw "pac admin application register failed: $reg" }
  Write-Host '  registered'

  Step "7/8 Dataverse: read-only role '$RoleName' in the configured environments"
  foreach ($e in Get-TargetEnvironments) {
    try {
      $bu = (Dv $e.Url GET "businessunits?`$select=businessunitid&`$filter=_parentbusinessunitid_value eq null").value[0].businessunitid
      $role = (Dv $e.Url GET "roles?`$select=roleid&`$filter=name eq '$RoleName' and _businessunitid_value eq $bu").value | Select-Object -First 1
      if (-not $role) {
        Dv $e.Url POST 'roles' @{ name = $RoleName; 'businessunitid@odata.bind' = "/businessunits($bu)"; description = 'Read-only for Credit Watch (managed identity).' } | Out-Null
        $role = (Dv $e.Url GET "roles?`$select=roleid&`$filter=name eq '$RoleName' and _businessunitid_value eq $bu").value[0]
      }
      $ids = foreach ($p in $Privs) { (Dv $e.Url GET "privileges?`$select=privilegeid&`$filter=name eq '$p'").value[0].privilegeid }
      Dv $e.Url POST "roles($($role.roleid))/Microsoft.Dynamics.CRM.AddPrivilegesRole" @{ Privileges = @($ids | Where-Object { $_ } | ForEach-Object { @{ PrivilegeId = $_; Depth = 'Global'; BusinessUnitId = $bu } }) } | Out-Null
      pac admin assign-user --environment $e.Url --user $miApp --role $RoleName --application-user | Out-Null
      Write-Host "  $($e.Name): ok"
    } catch {
      Write-Warning "  $($e.Name): $($_.Exception.Message)  -> you need the System Administrator role in this environment (INSTALL.md, troubleshooting)."
    }
  }
}

Step '8/8 Settings and code'
$siteId = az functionapp show -g $Rg -n $Func --query id -o tsv
$cur = az rest --method POST --url "https://management.azure.com$siteId/config/appsettings/list?api-version=2023-12-01" -o json | ConvertFrom-Json
$s = [ordered]@{}; foreach ($p in $cur.properties.PSObject.Properties) { $s[$p.Name] = $p.Value }
$s['STATE_ACCOUNT'] = $Storage
$s['DAILY_CRON'] = $cfg.schedule.dailyCron
if ($TeamsWebhook)        { $s['TEAMS_WEBHOOK_URL'] = $TeamsWebhook }
if ($TeamsOutgoingSecret) { $s['TEAMS_OUTGOING_SECRET'] = $TeamsOutgoingSecret }
if (-not $s['TEAMS_WEBHOOK_URL']) { Write-Warning 'No Teams webhook yet: reports are built but not posted. Re-run with -TeamsWebhook.' }
AzRest PUT "https://management.azure.com$siteId/config/appsettings?api-version=2023-12-01" @{ properties = $s }

$stage = Join-Path $env:TEMP "cw-stage-$hash"; $zip = Join-Path $env:TEMP "cw-$hash.zip"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory $stage | Out-Null
Copy-Item (Join-Path $Kit 'src\*') $stage -Recurse
Copy-Item $Config (Join-Path $stage 'config.json')
Get-ChildItem $stage -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -Force
az functionapp deployment source config-zip -g $Rg -n $Func --src $zip --build-remote true -o none

$hostName = az rest --method GET --url "https://management.azure.com$siteId`?api-version=2023-12-01" --query properties.defaultHostName -o tsv
Write-Host "`nDone." -ForegroundColor Green
Write-Host "Callback URL for the Teams outgoing webhook (INSTALL.md, step 7):" -ForegroundColor Green
Write-Host "  https://$hostName/api/teams"
if (-not $s['TEAMS_OUTGOING_SECRET']) { Write-Host 'Commands from Teams work after: .\install.ps1 -Config <file> -TeamsOutgoingSecret <secret>' -ForegroundColor Yellow }
