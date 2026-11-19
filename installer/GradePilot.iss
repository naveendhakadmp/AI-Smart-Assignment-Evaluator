#define AppName "GradePilot"
#define AppVersion "1.0.0"

[Setup]
AppId={{1D617AB8-5B0A-4B34-91E8-D2AE6DF4AC07}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=GradePilot
DefaultDirName={localappdata}\Programs\GradePilot
DefaultGroupName=GradePilot
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=GradePilot-Setup
SetupIconFile=..\static\gradepilot.ico
UninstallDisplayIcon={app}\GradePilot.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Dirs]
Name: "{localappdata}\GradePilot"; Flags: uninsneveruninstall

[Files]
Source: "..\dist\GradePilot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README_HINDI.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\GradePilot"; Filename: "{app}\GradePilot.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\GradePilot"; Filename: "{app}\GradePilot.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\GradePilot.exe"; Description: "Launch GradePilot"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent
