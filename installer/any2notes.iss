; any2notes — Inno Setup Script
; Richiede: Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
;
; Prima di compilare:
;   1. Esegui build\build_env.bat per preparare python_env\ e compilare launcher.exe
;   2. Scarica pandoc.exe e mettilo in build\bin\pandoc.exe
;   3. Compila questo script con Inno Setup Compiler

#define AppName "any2notes"
#define AppVersion "0.3.0"
#define AppPublisher "TamasNight"
#define AppURL "https://github.com/TamasNight/any2notes"
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
MinVersion=10.0.17763
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

; Assets
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.psd"

; main.py e requirements
Source: "..\main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Cartelle runtime (verranno create vuote e popolate dall'app)
Name: "{app}\models"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Installa dipendenze base
Filename: "{app}\python\python.exe"; \
  Parameters: "-m pip install -r {app}\requirements.txt"; \
  WorkingDir: "{app}"; \
  StatusMsg: "Installazione dipendenze Python…"; \
  Flags: runhidden waituntilterminated

; Installa torch CUDA 12.8 (solo se selezionato CUDA)
Filename: "{app}\python\python.exe"; \
  Parameters: "-m pip install torch --index-url https://download.pytorch.org/whl/cu128" --upgrade; \
  WorkingDir: "{app}"; \
  StatusMsg: "Installazione torch (CUDA 12.8)…"; \
  Flags: runhidden waituntilterminated; \
  Check: IsCudaSelected

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

function PandocInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('cmd.exe', '/C where pandoc', '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
            and (ResultCode = 0);
end;

procedure InstallWithWinget(PackageId: String; DisplayName: String);
var
  ResultCode: Integer;
  PSCommand: String;
begin
  PSCommand := 'winget install --id ' + PackageId + ' --silent --accept-package-agreements --accept-source-agreements';
  if MsgBox(
    DisplayName + ' non è installato sul sistema.' + #13#10 +
    'Vuoi installarlo automaticamente tramite winget?' + #13#10#13#10 +
    'Verrà eseguito:' + #13#10 +
    '  winget install --id ' + PackageId,
    mbConfirmation, MB_YESNO
  ) = IDYES then
  begin
    WizardForm.StatusLabel.Caption := 'Installazione ' + DisplayName + ' in corso…';
    if not Exec('powershell.exe',
      '-NoProfile -ExecutionPolicy Bypass -Command "' + PSCommand + '"',
      '', SW_SHOW, ewWaitUntilTerminated, ResultCode)
      or (ResultCode <> 0) then
    begin
      MsgBox(
        'Installazione automatica di ' + DisplayName + ' fallita (codice ' + IntToStr(ResultCode) + ').' + #13#10 +
        'Installalo manualmente:' + #13#10 +
        '  winget install --id ' + PackageId,
        mbError, MB_OK
      );
    end else begin
      MsgBox(DisplayName + ' installato correttamente.', mbInformation, MB_OK);
    end;
  end else begin
    MsgBox(
      'Puoi installarlo manualmente in qualsiasi momento con:' + #13#10 +
      '  winget install --id ' + PackageId,
      mbInformation, MB_OK
    );
  end;
end;

var
  CudaCheckbox: TNewCheckBox;
  CudaPage: TWizardPage;

function IsCudaSelected(): Boolean;
begin
  Result := CudaCheckbox.Checked;
end;

procedure InitializeWizard();
begin
  CudaPage := CreateCustomPage(
    wpSelectTasks,
    'Opzioni GPU',
    'Seleziona il supporto hardware per la trascrizione audio'
  );

  CudaCheckbox := TNewCheckBox.Create(CudaPage);
  CudaCheckbox.Parent := CudaPage.Surface;
  CudaCheckbox.Left := 0;
  CudaCheckbox.Top := 16;
  CudaCheckbox.Width := CudaPage.SurfaceWidth;
  CudaCheckbox.Height := 32;
  CudaCheckbox.Caption := 'Abilita supporto CUDA 12.8 (richiede GPU NVIDIA con driver aggiornati)';
  CudaCheckbox.Checked := False;

  { Nota informativa sotto il checkbox }
  with TNewStaticText.Create(CudaPage) do
  begin
    Parent := CudaPage.Surface;
    Left := 0;
    Top := 52;
    Width := CudaPage.SurfaceWidth;
    Caption :=
      'Con CUDA: installa torch+CUDA 12.8 e openai-whisper (~4 GB, richiede GPU NVIDIA).' + #13#10 +
      'Senza CUDA: installa torch CPU e faster-whisper (consigliato, ~500 MB).';
    AutoSize := True;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not PandocInstalled() then
      InstallWithWinget('JohnMacFarlane.Pandoc', 'Pandoc');

    if not OllamaInstalled() then
      InstallWithWinget('Ollama.Ollama', 'Ollama');
  end;
end;
