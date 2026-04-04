[Setup]
AppName=FileFlow
AppVersion=1.0
DefaultDirName={pf}\FileFlow
DefaultGroupName=FileFlow
OutputDir=dist
OutputBaseFilename=FileFlow_Setup
SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes

AppPublisher=Khalipha Samela
AppPublisherURL=https://github.com/Khalipha-Samela
AppSupportURL=https://github.com/Khalipha-Samela
AppUpdatesURL=https://github.com/Khalipha-Samela

UninstallDisplayIcon={app}\FileFlow.exe

VersionInfoVersion=1.0.0.0
VersionInfoCompany=Khalipha Samela
VersionInfoDescription=Smart File Organizer

[Files]
Source: "dist\FileFlow.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "history.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "last_folder.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\FileFlow"; Filename: "{app}\FileFlow.exe"
Name: "{commondesktop}\FileFlow"; Filename: "{app}\FileFlow.exe"