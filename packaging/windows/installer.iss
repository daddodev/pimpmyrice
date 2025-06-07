[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={pf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=installer_output
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\{#CmdName}.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; For CLI, typically no Start Menu shortcut, but you can add one if you want:
; Name: "{group}\{#AppName}"; Filename: "{app}\{#AppName}.exe"

[Run]
; Optional: Open a ReadMe or show a message after install
; Filename: "{app}\README.txt"; Description: "View ReadMe"; Flags: postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\{#CmdName}.exe"


[Files]
Source: "dist\{#CmdName}.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; For CLI, typically no Start Menu shortcut, but you can add one if you want:
; Name: "{group}\{#AppName}"; Filename: "{app}\{#CmdName}.exe"

[Run]
Filename: "cmd"; \
    Parameters: "/C setx PATH ""%PATH%;C:\PROGRA~2\{#AppName}"""; \
    Flags: runhidden

[UninstallDelete]
Type: files; Name: "{app}\{#CmdName}.exe"
