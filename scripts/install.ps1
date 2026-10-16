# Instalator projektu RAG DataRoom (Windows).
# Instaluje i konfiguruje wszystko, czego potrzebuje aplikacja:
# Python 3.11, PostgreSQL 17 + pgvector 0.8.0, Ollama 0.31.2 z modelami,
# baza rag_project_db oraz środowisko .venv z zależnościami.
# Każdy krok najpierw sprawdza, czy coś jest już zainstalowane - skrypt można uruchamiać wielokrotnie.

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

# --- Uprawnienia administratora (potrzebne do instalacji PostgreSQL, Build Tools i pgvector) ---
$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host 'Instalator potrzebuje uprawnień administratora - za chwilę pojawi się okno UAC.'
    Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    exit
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# --- Wersje (zgodne z README) ---
$PgVersion       = '17'
$PgvectorVersion = 'v0.8.0'
$OllamaVersion   = '0.31.2'
$Models          = @('nomic-embed-text', 'SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M')

$PgRoot = Join-Path $env:ProgramFiles "PostgreSQL\$PgVersion"
$TotalSteps = 7

function Write-Step($n, $text) { Write-Host ''; Write-Host "[$n/$TotalSteps] $text" -ForegroundColor Cyan }
function Write-Ok($text)       { Write-Host "  OK: $text" -ForegroundColor Green }
function Write-Info($text)     { Write-Host "  $text" }

function Update-SessionPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Install-WingetPackage($id, [string[]]$extraArgs) {
    Write-Info "Instalowanie $id (winget)..."
    & winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements @extraArgs
    Write-Info "winget zakończył z kodem $LASTEXITCODE"
    Update-SessionPath
}

function Find-Python311 {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $exe = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { return "$exe".Trim() }
    }
    foreach ($candidate in "$env:ProgramFiles\Python311\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe") {
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

function Find-Vcvars {
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) { return $null }
    $path = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1
    if (-not $path) { return $null }
    $vcvars = Join-Path "$path".Trim() 'VC\Auxiliary\Build\vcvars64.bat'
    if (Test-Path $vcvars) { return $vcvars }
    return $null
}

function Find-Ollama {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $path = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    if (Test-Path $path) { return $path }
    return $null
}

function Test-OllamaServer {
    # 127.0.0.1 zamiast localhost: Ollama nasłuchuje tylko na IPv4, a localhost bywa najpierw
    # rozwiązywany do ::1 (IPv6), co dodaje ~2 s opóźnienia do każdego zapytania
    try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 5 | Out-Null; return $true } catch { return $false }
}

function Wait-OllamaServer([int]$timeoutSec = 120) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-OllamaServer) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

Start-Transcript -Path (Join-Path $ProjectRoot 'install.log') -Force | Out-Null

try {
    # ------------------------------------------------------------------
    Write-Step 1 'Sprawdzanie konfiguracji'
    # ------------------------------------------------------------------
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'Brak programu winget. Zainstaluj "Instalator aplikacji" (App Installer) ze Sklepu Microsoft i uruchom instalator ponownie.'
    }
    $configText = Get-Content (Join-Path $ProjectRoot 'config.py') -Raw
    if ($configText -notmatch 'DATABASE_URL\s*=\s*["'']postgresql\+psycopg2://([^:]+):([^@]*)@([^:/]+):(\d+)/([^"'']+)["'']') {
        throw 'Nie udało się odczytać DATABASE_URL z config.py.'
    }
    $DbUser = $Matches[1]; $DbPass = $Matches[2]; $DbHost = $Matches[3]; $DbPort = $Matches[4]; $DbName = $Matches[5]
    Write-Ok "baza $DbName na ${DbHost}:${DbPort}, użytkownik $DbUser (z config.py)"

    # ------------------------------------------------------------------
    Write-Step 2 'Python 3.11'
    # ------------------------------------------------------------------
    $python = Find-Python311
    if (-not $python) {
        Install-WingetPackage 'Python.Python.3.11'
        $python = Find-Python311
        if (-not $python) { throw 'Nie udało się zainstalować Pythona 3.11.' }
    }
    Write-Ok $python

    # ------------------------------------------------------------------
    Write-Step 3 "PostgreSQL $PgVersion"
    # ------------------------------------------------------------------
    if (-not (Test-Path "$PgRoot\bin\psql.exe")) {
        Write-Info "Instalacja z hasłem i portem z config.py (port $DbPort)."
        $override = "--mode unattended --unattendedmodeui none --superaccount $DbUser --superpassword `"$DbPass`" --serverport $DbPort --disable-components stackbuilder"
        Install-WingetPackage "PostgreSQL.PostgreSQL.$PgVersion" @('--override', $override)
        if (-not (Test-Path "$PgRoot\bin\psql.exe")) { throw "Nie udało się zainstalować PostgreSQL $PgVersion." }
    }
    $pgService = Get-Service -Name "postgresql*$PgVersion*" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pgService -and $pgService.Status -ne 'Running') {
        Write-Info "Uruchamianie usługi $($pgService.Name)..."
        Start-Service $pgService.Name
    }
    Write-Ok $PgRoot

    # ------------------------------------------------------------------
    Write-Step 4 "pgvector $PgvectorVersion"
    # ------------------------------------------------------------------
    if (Test-Path "$PgRoot\share\extension\vector.control") {
        Write-Ok 'rozszerzenie jest już zainstalowane'
    } else {
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            Install-WingetPackage 'Git.Git'
            if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Nie udało się zainstalować Gita.' }
        }
        $vcvars = Find-Vcvars
        if (-not $vcvars) {
            Write-Info 'Instalacja Build Tools for Visual Studio (kilka GB, może potrwać 10-30 minut)...'
            Install-WingetPackage 'Microsoft.VisualStudio.2022.BuildTools' @('--override', '--quiet --wait --norestart --nocache --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended')
            $vcvars = Find-Vcvars
            if (-not $vcvars) { throw 'Nie udało się zainstalować Build Tools for Visual Studio (kompilator C++).' }
        }

        $src = Join-Path $env:TEMP 'pgvector-build'
        if (Test-Path $src) { Remove-Item $src -Recurse -Force }
        Write-Info 'Pobieranie źródeł pgvector...'
        & git clone --quiet --depth 1 --branch $PgvectorVersion https://github.com/pgvector/pgvector.git $src
        if ($LASTEXITCODE -ne 0) { throw 'Nie udało się pobrać pgvector z GitHuba.' }

        Write-Info 'Kompilacja i instalacja pgvector...'
        $buildScript = Join-Path $env:TEMP 'build-pgvector.cmd'
        @"
@echo off
call "$vcvars" || exit /b 1
set "PGROOT=$PgRoot"
cd /d "$src" || exit /b 1
nmake /nologo /F Makefile.win || exit /b 1
nmake /nologo /F Makefile.win install || exit /b 1
"@ | Set-Content -Path $buildScript -Encoding ASCII
        & cmd.exe /c $buildScript
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path "$PgRoot\share\extension\vector.control")) {
            throw 'Kompilacja pgvector nie powiodła się - szczegóły powyżej oraz w install.log.'
        }
        Remove-Item $src, $buildScript -Recurse -Force -ErrorAction SilentlyContinue
        Write-Ok 'pgvector zainstalowany'
    }

    # ------------------------------------------------------------------
    Write-Step 5 "Ollama $OllamaVersion i modele"
    # ------------------------------------------------------------------
    $ollama = Find-Ollama
    if (-not $ollama) {
        Install-WingetPackage 'Ollama.Ollama' @('--version', $OllamaVersion)
        $ollama = Find-Ollama
        if (-not $ollama) { throw 'Nie udało się zainstalować Ollamy.' }
    }
    if (-not (Test-OllamaServer)) {
        Write-Info 'Uruchamianie Ollamy...'
        $trayApp = Join-Path (Split-Path $ollama) 'ollama app.exe'
        if (Test-Path $trayApp) { Start-Process $trayApp } else { Start-Process $ollama -ArgumentList 'serve' -WindowStyle Hidden }
        if (-not (Wait-OllamaServer)) { throw 'Ollama nie odpowiada na http://127.0.0.1:11434 (czekano 2 minuty).' }
    }
    $installedModels = & $ollama list | Out-String
    foreach ($model in $Models) {
        if ($installedModels -match [regex]::Escape($model)) {
            Write-Ok "$model jest już pobrany"
        } else {
            Write-Info "Pobieranie modelu $model (Bielik ma ok. 7 GB)..."
            & $ollama pull $model
            if ($LASTEXITCODE -ne 0) { throw "Nie udało się pobrać modelu $model." }
            Write-Ok $model
        }
    }

    # ------------------------------------------------------------------
    Write-Step 6 "Baza danych $DbName"
    # ------------------------------------------------------------------
    $psql = "$PgRoot\bin\psql.exe"
    $env:PGPASSWORD = $DbPass
    $exists = & $psql -w -h $DbHost -p $DbPort -U $DbUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DbName'"
    if ($LASTEXITCODE -ne 0) {
        throw "Nie można połączyć się z PostgreSQL (${DbHost}:${DbPort}, użytkownik $DbUser). Jeśli PostgreSQL był zainstalowany wcześniej, wpisz jego hasło i port w config.py (README, krok 2) i uruchom instalator ponownie."
    }
    if ("$exists".Trim() -ne '1') {
        & $psql -w -h $DbHost -p $DbPort -U $DbUser -d postgres -c "CREATE DATABASE $DbName;"
        if ($LASTEXITCODE -ne 0) { throw "Nie udało się utworzyć bazy $DbName." }
    }
    & $psql -w -h $DbHost -p $DbPort -U $DbUser -d $DbName -c 'CREATE EXTENSION IF NOT EXISTS vector;'
    if ($LASTEXITCODE -ne 0) { throw 'Nie udało się włączyć rozszerzenia vector.' }
    Remove-Item Env:PGPASSWORD
    Write-Ok "baza $DbName z rozszerzeniem vector jest gotowa"

    # ------------------------------------------------------------------
    Write-Step 7 'Środowisko Python (.venv) i zależności'
    # ------------------------------------------------------------------
    $venvDir = Join-Path $ProjectRoot '.venv'
    $venvPy = Join-Path $venvDir 'Scripts\python.exe'
    if (Test-Path $venvPy) {
        $venvVersion = & $venvPy -c "import sys; print('%d.%d' % sys.version_info[:2])"
        if ("$venvVersion".Trim() -ne '3.11') {
            Write-Info "Istniejące .venv używa Pythona $venvVersion - tworzenie od nowa na Pythonie 3.11..."
            Remove-Item $venvDir -Recurse -Force
        }
    }
    if (-not (Test-Path $venvPy)) {
        & $python -m venv $venvDir
        if ($LASTEXITCODE -ne 0) { throw 'Nie udało się utworzyć środowiska .venv.' }
    }
    & $venvPy -m pip install --upgrade pip
    Write-Info 'Instalowanie pakietów z requirements.txt (może potrwać kilka minut)...'
    & $venvPy -m pip install -r (Join-Path $ProjectRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Instalacja pakietów z requirements.txt nie powiodła się.' }
    Write-Ok 'zależności zainstalowane'

    Write-Host ''
    Write-Host 'Instalacja zakończona pomyślnie!' -ForegroundColor Green
    Write-Host 'Aplikację uruchamiasz plikiem start.bat. Logowanie: admin / admin123'
    Write-Host ''
    $answer = Read-Host 'Uruchomić aplikację teraz? [T/n]'
    if ($answer -notmatch '^[nN]') {
        # explorer.exe uruchamia start.bat bez uprawnień administratora
        Start-Process explorer.exe -ArgumentList "`"$(Join-Path $ProjectRoot 'start.bat')`""
    }
}
catch {
    Write-Host ''
    Write-Host "BŁĄD: $_" -ForegroundColor Red
    Write-Host 'Pełny przebieg instalacji jest zapisany w pliku install.log.'
    Read-Host 'Naciśnij Enter, aby zamknąć'
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    Stop-Transcript | Out-Null
}
