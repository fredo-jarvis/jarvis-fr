; Installateur Windows de Jarvis FR (Inno Setup 6). Construit Jarvis-FR-Setup-1.1.0.exe
; Il copie Jarvis, puis lance installer.ps1 (Python 3.12, bibliothèques, cerveau, raccourci, clé Gemini).
#define Version "1.1.0"
#define Racine ".."
[Setup]
AppId={{6B2E5C7A-3D41-4F0E-9A57-0A1B2C3D4E5F}
AppName=Jarvis FR
AppVersion={#Version}
AppPublisher=Jarvis FR (édition non officielle de Mark LV, FatihMakes, CC BY-NC 4.0)
DefaultDirName={%USERPROFILE}\Jarvis-Mark-LV
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=sortie
OutputBaseFilename=Jarvis-FR-Setup-{#Version}
SetupIconFile={#Racine}\config\jarvis.ico
LicenseFile={#Racine}\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\config\jarvis.ico
[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
[Tasks]
Name: "cervealocal"; Description: "Installer aussi le cerveau local (Ollama + modèle, plusieurs Go, sans Internet ensuite)"; Flags: unchecked
[Files]
Source: "{#Racine}\*"; DestDir: "{app}"; Excludes: ".git,.git\*,__pycache__,*.pyc,installateur\sortie,installateur\sortie\*,jarvis.log,config\api_keys.json,memory\long_term.json,memory\carnet-cerveau.md,.venv,.venv\*"; Flags: recursesubdirs createallsubdirs ignoreversion
[Run]
; Installation normale : la fenêtre reste ouverte à la fin (« Appuyez sur une touche ») pour lire le résultat et coller la clé.
Filename: "{app}\Installer-Jarvis.bat"; WorkingDir: "{app}"; StatusMsg: "Installation de Jarvis (Python, bibliothèques, cerveau, raccourci)..."; Flags: waituntilterminated; Check: not WizardSilent
Filename: "{app}\outils\Installer-Cerveau-Local.bat"; WorkingDir: "{app}"; StatusMsg: "Installation du cerveau local..."; Tasks: cervealocal; Flags: waituntilterminated; Check: not WizardSilent
; Installation silencieuse (/VERYSILENT) : sans pause.
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Get-Content -Raw -Encoding UTF8 installer.ps1 | Invoke-Expression"""; WorkingDir: "{app}"; Flags: waituntilterminated runhidden; Check: WizardSilent
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\outils\installer-cerveau-local.ps1"""; WorkingDir: "{app}"; Tasks: cervealocal; Flags: waituntilterminated runhidden; Check: WizardSilent
[UninstallDelete]
; Le code et l'environnement sont retirés ; config (clé), memory (souvenirs) et le cerveau dans Documents restent à la personne.
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\actions"
Type: filesandordirs; Name: "{app}\core"
Type: filesandordirs; Name: "{app}\dashboard"
Type: filesandordirs; Name: "{app}\galaxie"
Type: filesandordirs; Name: "{app}\plugins"
Type: filesandordirs; Name: "{app}\holo"
Type: filesandordirs; Name: "{app}\tests"
Type: filesandordirs; Name: "{app}\docs"
Type: filesandordirs; Name: "{app}\cerveau-modele"
Type: filesandordirs; Name: "{app}\assets"
Type: filesandordirs; Name: "{app}\outils"
Type: filesandordirs; Name: "{app}\installateur"
Type: filesandordirs; Name: "{app}\uploads"

[UninstallRun]
; (le raccourci du bureau est retiré ci-dessous ; la clé, la mémoire et le cerveau de la personne ne sont jamais supprimés)
[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    DeleteFile(ExpandConstant('{userdesktop}\Jarvis.lnk'));
end;
