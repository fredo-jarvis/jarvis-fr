# Installe le cerveau local de Jarvis : Ollama + le modèle qwen3.5:9b + les oreilles locales (faster-whisper).
# Appelé par l'installateur .exe (case « Cerveau local ») ; tu peux aussi le lancer à la main plus tard.
param([string]$Dossier = (Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference = "Stop"
function Etape($t) { Write-Host ""; Write-Host "==> $t" -ForegroundColor Cyan }

Etape "Ollama (le moteur du cerveau local)"
$ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
if (-not $ollama) { $ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe" }
if (-not (Test-Path $ollama)) {
    Write-Host "Installation d'Ollama avec winget..."
    winget install -e --id Ollama.Ollama --scope user --accept-package-agreements --accept-source-agreements
    $ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (-not (Test-Path $ollama)) { throw "Ollama n'a pas pu être installé. Installe-le depuis https://ollama.com puis relance." }
} else { Write-Host "Ollama est déjà là." }

Etape "Démarrage du moteur Ollama"
function OllamaRepond { try { Invoke-WebRequest "http://127.0.0.1:11434/" -UseBasicParsing -TimeoutSec 2 | Out-Null; return $true } catch { return $false } }
if (-not (OllamaRepond)) {
    Start-Process $ollama -ArgumentList "serve" -WindowStyle Hidden
    for ($i = 0; $i -lt 30 -and -not (OllamaRepond); $i++) { Start-Sleep 1 }
    if (-not (OllamaRepond)) { throw "Ollama ne démarre pas. Ouvre l'application Ollama puis relance." }
}

Etape "Le modèle qwen3.5:9b (plusieurs Go, c'est long la première fois)"
& $ollama pull qwen3.5:9b
if ($LASTEXITCODE -ne 0) { throw "Le téléchargement du modèle a échoué." }

Etape "Les oreilles locales (faster-whisper)"
$py = Join-Path $Dossier ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Jarvis n'est pas encore installé dans $Dossier." }
& $py -m pip install faster-whisper --quiet
if ($LASTEXITCODE -ne 0) { throw "faster-whisper n'a pas pu être installé." }

Write-Host ""
Write-Host "Cerveau local prêt. Dis à Jarvis : « passe sur ton cerveau local »." -ForegroundColor Green
