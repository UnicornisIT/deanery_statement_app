#define MyAppName "Deanery Statement App"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "ЧПОУ МК АВИЦЕННА"
#define MyAppExeName "DeaneryStatementApp.exe"

[Setup]
AppId={{9D26AC55-5441-4CB7-9B2B-19733C76D001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\DeaneryStatementApp
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=DeaneryStatementAppSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные значки:"; Flags: unchecked

[Files]
Source: "..\dist\DeaneryStatementApp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\config.ini"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "..\sql\*.sql"; DestDir: "{app}\sql"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent
