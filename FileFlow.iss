; FileFlow installer script for Inno Setup 6 (https://jrsoftware.org/isinfo.php)
;
; Build order:
;   1. pyinstaller --noconsole --onefile --name FileFlow --icon icon.ico --add-data "icon.ico;." --collect-all customtkinter FileFlow.py
;   2. Open this file in Inno Setup and choose Build > Compile (or run: ISCC.exe FileFlow.iss)
;   3. The installer is written to the "installer" folder.

#define MyAppName "FileFlow"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Khalipha Samela"
#define MyAppURL "https://github.com/Khalipha-Samela/FileFlow"
#define MyAppExeName "FileFlow.exe"

[Setup]
; AppId identifies this app across versions so upgrades replace the old install.
; Keep this GUID the same for every future release.
AppId={{22B68231-55D5-4819-9D66-8DC378D54E79}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installs for the current user by default, so there is no admin prompt.
; The user can still choose "all users" on the first wizard page.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

OutputDir=installer
OutputBaseFilename=FileFlow-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

; If FileFlow is running during an upgrade or uninstall, offer to close it.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
{ On uninstall, ask whether to remove settings, undo history and the activity log.
  They live in %APPDATA%\FileFlow, outside the install folder. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\FileFlow');
    if DirExists(DataDir) and (not UninstallSilent) then
    begin
      if MsgBox('Also delete your FileFlow settings, undo history and activity log?' + #13#10 + #13#10 +
                'Choose No to keep them in case you reinstall later.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
