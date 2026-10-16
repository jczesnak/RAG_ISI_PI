# Uruchamia aplikację RAG DataRoom: sprawdza PostgreSQL i Ollamę, potem startuje Streamlit.

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$venvPy = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Write-Host 'Brak środowiska .venv - najpierw uruchom install.bat.' -ForegroundColor Red
    exit 1
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

# --- PostgreSQL ---
$configText = Get-Content (Join-Path $ProjectRoot 'config.py') -Raw
if ($configText -match 'DATABASE_URL\s*=\s*["'']postgresql\+psycopg2://[^@]*@([^:/]+):(\d+)/') {
    $dbHost = $Matches[1]; $dbPort = [int]$Matches[2]
    $tcp = New-Object Net.Sockets.TcpClient
    try { $tcp.Connect($dbHost, $dbPort); Write-Host "PostgreSQL: OK (${dbHost}:${dbPort})" -ForegroundColor Green }
    catch {
        Write-Host "PostgreSQL nie odpowiada na ${dbHost}:${dbPort}." -ForegroundColor Red
        Write-Host 'Uruchom usługę PostgreSQL (services.msc) albo ponownie install.bat.'
        exit 1
    }
    finally { $tcp.Close() }
}

# --- Ollama ---
if (-not (Test-OllamaServer)) {
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    $ollamaExe = if ($ollama) { $ollama.Source } else { "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" }
    if (-not (Test-Path $ollamaExe)) {
        Write-Host 'Nie znaleziono Ollamy - uruchom install.bat.' -ForegroundColor Red
        exit 1
    }
    Write-Host 'Uruchamianie Ollamy...'
    $trayApp = Join-Path (Split-Path $ollamaExe) 'ollama app.exe'
    if (Test-Path $trayApp) { Start-Process $trayApp } else { Start-Process $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden }
    if (-not (Wait-OllamaServer)) {
        Write-Host 'Ollama nie odpowiada na http://127.0.0.1:11434 (czekano 2 minuty).' -ForegroundColor Red
        exit 1
    }
}
Write-Host 'Ollama: OK' -ForegroundColor Green

# --- Aplikacja ---
Write-Host ''
Write-Host 'Start aplikacji - otworzy się w przeglądarce (http://localhost:8501). Zamknij to okno, aby ją zatrzymać.'
& $venvPy -m streamlit run app.py
