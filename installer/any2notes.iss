; any2notes — Inno Setup Script
; Richiede: Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
;
; Prima di compilare:
;   1. Esegui build\build_env.bat per preparare python_env\ e compilare launcher.exe
;   2. Scarica pandoc.exe e mettilo in build\bin\pandoc.exe
;   3. Compila questo script con Inno Setup Compiler

#define AppName "any2notes"
#define AppVersion "0.1.0"
#define AppPublisher "any2notes"
#define AppURL "https://github.com/your-repo/any2notes"
#define AppExeName "launcher.exe"
#define BuildDir "..\build\output"

[Setup]
AppId={{A2N-2025-UNIQUE-GUID-PLACEHOLDER}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Richiede privilegi admin per installare in Program Files
PrivilegesRequired=admin
OutputDir=..\dist
OutputBaseFilename=any2notes-setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Icona (genera con assets/icon.ico)
; SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
MinVersion=10.0.17763   ; Windows 10 1809+
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Launcher compilato
Source: "{#BuildDir}\launcher.exe"; DestDir: "{app}"; Flags: ignoreversion

; Codice applicazione
Source: "..\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs

; Script Python
Source: "..\scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs

; Python embeddable (preparato da build_env.bat)
Source: "..\build\python_env\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs

; Pandoc bundlato
Source: "..\build\bin\pandoc.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

; Assets
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.psd"

; main.py e requirements
Source: "..\main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Cartelle runtime (verranno create vuote e popolate dall'app)
Name: "{app}\runs"
Name: "{app}\benchmark"
Name: "{app}\models"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Installa dipendenze pip nell'env embedded subito dopo l'installazione
Filename: "{app}\python\python.exe"; \
  Parameters: "-m pip install --no-index --find-links=""{app}\python\wheels"" PyQt6 faster-whisper"; \
  WorkingDir: "{app}"; \
  StatusMsg: "Installazione dipendenze Python…"; \
  Flags: runhidden waituntilterminated

; Avvia l'app alla fine dell'installer (opzionale)
Filename: "{app}\{#AppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Rimuove runs e benchmark solo se l'utente conferma (non cancella i dati utente)
; Per sicurezza lasciamo che l'utente cancelli manualmente la cartella "runs\"
Type: filesandordirs; Name: "{app}\benchmark"
Type: filesandordirs; Name: "{app}\models"

[Code]
{ ---- Controlla se Ollama è installato ---- }
function OllamaInstalled(): Boolean;
var
  OllamaPath: String;
begin
  Result := RegQueryStringValue(HKLM, 'SOFTWARE\Ollama', 'InstallPath', OllamaPath)
         or FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not OllamaInstalled() then
    begin
      MsgBox(
        'Ollama non è installato sul sistema.' + #13#10 +
        'any2notes richiede Ollama per le funzioni di riassunto.' + #13#10#13#10 +
        'Scaricalo da: https://ollama.com/download' + #13#10 +
        'Dopo averlo installato, avvia ''ollama serve'' prima di usare any2notes.',
        mbInformation, MB_OK
      );
    end;
  end;
end;
