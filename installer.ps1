# ─────────────────────────────────────────────────────────────────────────────
#  Installation de Jarvis (Mark LV, version française) — Windows 10 / 11
#
#  VERSION BÊTA (1.1) — réservée aux testeurs. Ligne à coller dans PowerShell :
#     irm https://raw.githubusercontent.com/fredo-jarvis/jarvis-fr/beta/installer.ps1 | iex
#  Elle s'installe À CÔTÉ de la version normale (dossier Jarvis-Mark-LV-beta, raccourci
#  « Jarvis BETA ») et partage le même cerveau.
#
#  Ce que fait ce script, dans l'ordre :
#    1. installe Python 3.12 s'il manque (avec winget, l'outil officiel de Windows) ;
#    2. télécharge Jarvis dans  %USERPROFILE%\Jarvis-Mark-LV ;
#    3. crée son environnement Python et installe ses bibliothèques ;
#    4. crée un cerveau vierge dans  Documents\Cerveau  (s'il n'existe pas déjà) ;
#    5. pose un raccourci « Jarvis » sur le bureau.
#  Relancer le script met Jarvis à jour sans toucher à la clé, à la mémoire ni au cerveau.
# ─────────────────────────────────────────────────────────────────────────────
# Nom du raccourci : "Jarvis BETA", sauf si la variable JARVIS_RACCOURCI en donne un autre (tests).
$Raccourci = if ($env:JARVIS_RACCOURCI) { $env:JARVIS_RACCOURCI } else { "Jarvis BETA" }
$ErrorActionPreference = "Stop"
$Depot   = "fredo-jarvis/jarvis-fr"                       # « compte/projet » sur GitHub
$Branche = "beta"                                         # version bêta : branche « beta »
$Dossier = Join-Path $env:USERPROFILE "Jarvis-Mark-LV-beta"

function Etape($texte) { Write-Host ""; Write-Host "==> $texte" -ForegroundColor Cyan }

# 1. Python 3.12 ---------------------------------------------------------------
Etape "Vérification de Python 3.12"
$py = $null
try { & py -3.12 --version *> $null; if ($LASTEXITCODE -eq 0) { $py = @("py", "-3.12") } } catch {}
if (-not $py) {
    Write-Host "Python 3.12 n'est pas installé : installation avec winget..."
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
    $py = @("py", "-3.12")
    & py -3.12 --version
    if ($LASTEXITCODE -ne 0) { throw "Python 3.12 n'a pas pu être installé. Installe-le depuis python.org puis relance." }
}

# 2. Les fichiers de Jarvis ----------------------------------------------------
$ici = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
if ($ici -and (Test-Path (Join-Path $ici "main.py"))) {
    $Dossier = $ici                                     # lancé depuis un dossier déjà téléchargé
    Etape "Jarvis est déjà là : $Dossier"
} else {
    Etape "Téléchargement de Jarvis"
    $zip = Join-Path $env:TEMP "jarvis-mark-lv.zip"
    $tmp = Join-Path $env:TEMP "jarvis-mark-lv"
    Invoke-WebRequest "https://github.com/$Depot/archive/refs/heads/$Branche.zip" -OutFile $zip
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive $zip -DestinationPath $tmp
    $source = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
    New-Item -ItemType Directory -Force $Dossier | Out-Null
    # on garde la clé, la mémoire et les réglages de la personne lors d'une mise à jour
    robocopy $source $Dossier /E /NFL /NDL /NJH /NJS /XF api_keys.json interface.json long_term.json carnet-cerveau.md | Out-Null
    if (-not (Test-Path (Join-Path $Dossier "memory\interface.json"))) {
        Copy-Item (Join-Path $source "memory\interface.json") (Join-Path $Dossier "memory\interface.json")
    }
    Remove-Item $zip, $tmp -Recurse -Force
}

# 3. Environnement Python et bibliothèques -------------------------------------
Etape "Installation des bibliothèques"
Write-Host "Cela prend 5 à 10 minutes. La fenêtre reste calme pendant ce temps : c'est normal, ne la ferme pas."
Set-Location $Dossier
if (-not (Test-Path ".venv\Scripts\python.exe")) { & $py[0] $py[1] -m venv .venv }
& .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { throw "L'installation des bibliothèques a échoué (voir le message ci-dessus)." }
& .venv\Scripts\python.exe -m playwright install chromium

# 4. Le cerveau ----------------------------------------------------------------
$cerveau = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Cerveau"
if (-not (Test-Path $cerveau)) {
    Etape "Création du cerveau vierge : $cerveau"
    Copy-Item (Join-Path $Dossier "cerveau-modele") $cerveau -Recurse
} else {
    Etape "Cerveau déjà présent : $cerveau (on n'y touche pas)"
}

# 5. Raccourci sur le bureau ---------------------------------------------------
Etape "Raccourci « $Raccourci » sur le bureau"
$sh = New-Object -ComObject WScript.Shell
$lnk = $sh.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "$Raccourci.lnk"))
$lnk.TargetPath = Join-Path $Dossier "Lancer-Jarvis.bat"
$lnk.WorkingDirectory = $Dossier
$lnk.IconLocation = Join-Path $Dossier "config\jarvis.ico"
$lnk.Save()

# 6. La clé Gemini -------------------------------------------------------------
$cles = Join-Path $Dossier "config\api_keys.json"
$dejaCle = $false
if (Test-Path $cles) { try { $dejaCle = [bool](Get-Content $cles -Raw -Encoding UTF8 | ConvertFrom-Json).gemini_api_key } catch {} }
if (-not $dejaCle) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Dossier "outils\cle_gemini.ps1") -Dossier $Dossier
} else {
    Etape "Clé Gemini déjà enregistrée (pour la changer : Changer-Cle-Gemini.bat)"
}

Write-Host ""
Write-Host "Jarvis est installé !" -ForegroundColor Green
Write-Host "Double-clique sur « $Raccourci » sur ton bureau : il va se présenter et faire connaissance avec toi."
Write-Host ""
Write-Host "Où sont les fichiers :" -ForegroundColor Cyan
Write-Host "  Jarvis     : $Dossier"
Write-Host "  Le cerveau : $cerveau   (à ouvrir dans Obsidian : « Ouvrir un dossier comme coffre »)"
Write-Host "  Le carnet  : $(Join-Path $Dossier 'memory\carnet-cerveau.md')"
