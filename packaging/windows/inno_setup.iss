[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={pf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\..\dist
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes

[Files]
Source: "..\..\dist\{#CmdName}.exe"; DestDir: "{app}"; Flags: ignoreversion

[UninstallDelete]
Type: files; Name: "{app}\{#CmdName}.exe"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#CmdName}.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "cmd"; \
    Parameters: "/C setx PATH ""%PATH%;C:\PROGRA~2\{#AppName}"""; \
    Flags: runhidden