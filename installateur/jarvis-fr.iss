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
// Le désinstallateur d'Inno ne sait pas effacer un fichier dont le chemin complet dépasse 260 caractères
// (journal : « Failed to delete the file; it may be in use (3) » puis « Failed to delete directory (145) »).
// Le .venv contient de tels fichiers (PyQt6, google-genai) dès que le dossier d'installation est un peu profond.
// On l'efface donc avant, avec rd et le préfixe \\?\ qui lève cette limite. Seul {app}\.venv est visé.
procedure SupprimerVenv;
var
  Venv: String;
  Code: Integer;
begin
  Venv := ExpandConstant('{app}\.venv');
  if (Length(ExpandConstant('{app}')) > 3) and DirExists(Venv) then
  begin
    Log('Suppression du .venv (chemins longs) : ' + Venv);
    if Exec(ExpandConstant('{cmd}'), '/c rd /s /q "\\?\' + Venv + '"', '', SW_HIDE, ewWaitUntilTerminated, Code) then
      Log('rd terminé, code ' + IntToStr(Code))
    else
      Log('rd n''a pas pu être lancé');
    if DirExists(Venv) then
      Log('Le .venv est encore là après rd');
  end;
end;

// Efface un raccourci du bureau seulement s'il lance le Jarvis de CE dossier ({app}\Lancer-Jarvis.bat).
// Un raccourci qui pointe vers un autre Jarvis (autre installation) n'est jamais touché.
procedure SupprimerRaccourci(Nom: String);
var
  Chemin, Cible, Attendu: String;
  Shell, Lien: Variant;
begin
  if Nom = '' then exit;
  Chemin := ExpandConstant('{userdesktop}\') + Nom + '.lnk';
  if not FileExists(Chemin) then exit;
  Attendu := ExpandConstant('{app}\Lancer-Jarvis.bat');
  Cible := '';
  try
    Shell := CreateOleObject('WScript.Shell');
    Lien := Shell.CreateShortcut(Chemin);
    Cible := Lien.TargetPath;
  except
    Log('Raccourci illisible, on n''y touche pas : ' + Chemin);
    exit;
  end;
  if CompareText(Cible, Attendu) = 0 then
  begin
    if DeleteFile(Chemin) then
      Log('Raccourci supprimé : ' + Chemin)
    else
      Log('Raccourci non supprimé (erreur) : ' + Chemin);
  end
  else
    Log('Raccourci gardé, il pointe ailleurs : ' + Chemin + ' -> ' + Cible);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    SupprimerVenv;
  if CurUninstallStep = usPostUninstall then
  begin
    SupprimerVenv;  // seconde chance si un fichier était encore ouvert au premier passage
    SupprimerRaccourci('Jarvis');
    if CompareText(GetEnv('JARVIS_RACCOURCI'), 'Jarvis') <> 0 then
      SupprimerRaccourci(GetEnv('JARVIS_RACCOURCI'));
  end;
end;
