# AIIANER Marktplatz installieren, natives Windows.
#
# Fuer Linux, macOS und WSL gibt es install.sh. Dieses Skript ist fuer
# PowerShell auf nativem Windows, wo Hermes seine Daten unter
# %LOCALAPPDATA%\hermes haelt statt unter ~/.hermes.
#
# Aufruf:
#   irm https://raw.githubusercontent.com/oliverhees/aiianer-hermes-extensions/main/extensions/aiianer-hub/install.ps1 | iex
#
# Idempotent. Mehrfaches Ausfuehren aktualisiert nur.

$ErrorActionPreference = 'Stop'

# Wo Hermes seine Daten haelt. Reihenfolge wie in Hermes' eigenem install.ps1.
$HermesHome = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { "$env:LOCALAPPDATA\hermes" }

if (-not (Test-Path $HermesHome)) {
  Write-Error @"
$HermesHome existiert nicht.

Auf nativem Windows liegt Hermes unter %LOCALAPPDATA%\hermes.
Ist Hermes installiert? Falls es woanders liegt, setze HERMES_HOME.
"@
  exit 1
}

Write-Host "Hermes-Verzeichnis: $HermesHome"

$PluginDir = Join-Path $HermesHome 'plugins\aiianer-hub'
$DesktopDir = Join-Path $HermesHome 'desktop-plugins\aiianer-hub'
$HookDir   = Join-Path $HermesHome 'hooks\aiianer-guard'
$StateDir  = Join-Path $HermesHome 'aiianer'

# Quelle bestimmen: lokaler Clone oder Download
$Here = if ($PSScriptRoot) { $PSScriptRoot } else { $null }
$Temp = $null

if (-not $Here -or -not (Test-Path (Join-Path $Here 'guard_check.py'))) {
  Write-Host "Kein lokaler Clone gefunden, lade von GitHub ..."
  $Temp = Join-Path ([System.IO.Path]::GetTempPath()) ("aiianer-" + [guid]::NewGuid())
  New-Item -ItemType Directory -Path $Temp -Force | Out-Null
  $Zip = Join-Path $Temp 'repo.zip'
  Invoke-WebRequest -Uri 'https://github.com/oliverhees/aiianer-hermes-extensions/archive/refs/heads/main.zip' -OutFile $Zip
  Expand-Archive -Path $Zip -DestinationPath $Temp -Force
  $Root = Get-ChildItem -Path $Temp -Directory | Select-Object -First 1
  $Here = Join-Path $Root.FullName 'extensions\aiianer-hub'
}

Write-Host "Installiere AIIANER Marktplatz ..."

# 1) Plugin
New-Item -ItemType Directory -Path (Join-Path $PluginDir 'dashboard\dist') -Force | Out-Null
Copy-Item (Join-Path $Here 'plugin.yaml')                 (Join-Path $PluginDir 'plugin.yaml') -Force
Copy-Item (Join-Path $Here 'catalog.json')                (Join-Path $PluginDir 'catalog.json') -Force
Copy-Item (Join-Path $Here 'dashboard\manifest.json')     (Join-Path $PluginDir 'dashboard\manifest.json') -Force
Copy-Item (Join-Path $Here 'dashboard\plugin_api.py')     (Join-Path $PluginDir 'dashboard\plugin_api.py') -Force
Copy-Item (Join-Path $Here 'dashboard\dist\index.js')     (Join-Path $PluginDir 'dashboard\dist\index.js') -Force
$Pyc = Join-Path $PluginDir 'dashboard\__pycache__'
if (Test-Path $Pyc) { Remove-Item $Pyc -Recurse -Force }
Write-Host "  Plugin      -> $PluginDir"

# 2) Desktop-Fassung. Hermes hat zwei getrennte Plugin-Systeme.
New-Item -ItemType Directory -Path $DesktopDir -Force | Out-Null
Copy-Item (Join-Path $Here 'desktop\plugin.js') (Join-Path $DesktopDir 'plugin.js') -Force
Write-Host "  Desktop     -> $DesktopDir"

# 3) Gemeinsame Pruefung
New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
Copy-Item (Join-Path $Here 'guard_check.py') (Join-Path $StateDir 'guard_check.py') -Force
Write-Host "  Pruefung    -> $StateDir\guard_check.py"

# 4) Waechter
New-Item -ItemType Directory -Path $HookDir -Force | Out-Null
Copy-Item (Join-Path $Here 'guard\HOOK.yaml')  (Join-Path $HookDir 'HOOK.yaml') -Force
Copy-Item (Join-Path $Here 'guard\handler.py') (Join-Path $HookDir 'handler.py') -Force
$Pyc2 = Join-Path $HookDir '__pycache__'
if (Test-Path $Pyc2) { Remove-Item $Pyc2 -Recurse -Force }
Write-Host "  Waechter    -> $HookDir"

if ($Temp -and (Test-Path $Temp)) { Remove-Item $Temp -Recurse -Force }

Write-Host ""
Write-Host "Fertig. Naechste Schritte:"
Write-Host "  1. Hermes komplett neu starten"
Write-Host "  2. Der Eintrag 'AIIANER' erscheint in beiden Oberflaechen:"
Write-Host "     Desktop-App    -> in der Seitenleiste"
Write-Host "     Web-Dashboard  -> als Reiter, erreichbar mit: hermes web"
Write-Host "  3. Dort auswaehlen, was du installieren willst"
Write-Host ""
Write-Host "Der Waechter prueft ab jetzt bei jedem Gateway-Start, ob ein"
Write-Host "Hermes-Update etwas entfernt hat, und spielt es erneut ein."
