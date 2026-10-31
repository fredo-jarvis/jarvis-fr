# Demande la clé Gemini (gratuite) et la range dans config\api_keys.json.
# Appelé à la fin de installer.ps1, et par Changer-Cle-Gemini.bat pour la changer plus tard.
param([string]$Dossier = (Split-Path $PSScriptRoot -Parent))
$fichier = Join-Path $Dossier "config\api_keys.json"
$cfg = @{}
if (Test-Path $fichier) {
    try { (Get-Content $fichier -Raw -Encoding UTF8 | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $cfg[$_.Name] = $_.Value } } catch {}
}

Write-Host ""
Write-Host "==> Ta clé Gemini (gratuite)" -ForegroundColor Cyan
Write-Host "Jarvis a besoin d'une clé Google Gemini pour parler. Elle est gratuite."
Write-Host "La page Google AI Studio s'ouvre dans ton navigateur..."
Start-Process "https://aistudio.google.com/apikey"
Write-Host ""
Write-Host "  1. Connecte-toi avec ton compte Google."
Write-Host "  2. Clique sur « Create API key » (Créer une clé API), ou copie une clé déjà créée."
Write-Host "  3. Reviens dans cette fenêtre, fais un clic droit pour coller la clé, puis Entrée."
Write-Host ""

while ($true) {
    $cle = "$(Read-Host "Colle ta clé Gemini ici (ou Entrée pour le faire plus tard)")".Trim()
    if (-not $cle) {
        Write-Host "D'accord : Jarvis te la demandera à son premier lancement."
        return
    }
    # Google donne deux formats de clé : l'ancien « AIza… » et le nouveau « AQ.… » (2026).
    if ($cle -match '^(AIza|AQ\.)[0-9A-Za-z_.\-]{30,}$') { break }
    Write-Host "Ça ne ressemble pas à une clé Gemini (elle commence par AIza ou par AQ., sans espace). Réessaie." -ForegroundColor Yellow
}

$cfg["gemini_api_key"] = $cle
if (-not $cfg["os_system"]) { $cfg["os_system"] = "windows" }
New-Item -ItemType Directory -Force (Split-Path $fichier) | Out-Null
$json = $cfg | ConvertTo-Json -Depth 5
[IO.File]::WriteAllText($fichier, $json, (New-Object Text.UTF8Encoding $false))
Write-Host "Clé enregistrée sur ton PC (config\api_keys.json, jamais partagée)." -ForegroundColor Green
