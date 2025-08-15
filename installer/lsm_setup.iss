; Inno Setup Script for Laser Scan Micrometer (Windows Installer)
; Save as installer/lsm_setup.iss and build with ISCC.exe

#define AppName "Laser Scan Micrometer"
#define AppVersion "1.0.0"
#define AppPublisher "Your Company"
#define AppExeGui "LSM-GUI.exe"
#define AppExeReader "LSM-Reader.exe"
#define ProgramDataDir "{commonappdata}\\Laser_Scan_Micrometer"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={pf}\{#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=LSM-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
; Optional icon (place app.ico next to this .iss and uncomment):
; SetupIconFile=app.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Dirs]
Name: "{#ProgramDataDir}\logs"; Flags: uninsneveruninstall

[Files]
; Binaries produced by PyInstaller (created in CI in dist/)
Source: "..\dist\{#AppExeGui}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\{#AppExeReader}"; DestDir: "{app}"; Flags: ignoreversion

; Config shipped to ProgramData (only create if not exists, so user edits are preserved)
Source: "..\config.yaml"; DestDir: "{#ProgramDataDir}"; Flags: onlyifdoesntexist

; Optional docs (uncomment if present)
; Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\LSM-6200 量測 GUI"; Filename: "{app}\{#AppExeGui}"
Name: "{group}\LSM-6200 連線讀取"; Filename: "{app}\{#AppExeReader}"
Name: "{group}\查看報表資料夾"; Filename: "{cmd}"; Parameters: "/c start \"\" \"{#ProgramDataDir}\\logs\""; WorkingDir: "{#ProgramDataDir}"
Name: "{group}\編輯設定檔 (config.yaml)"; Filename: "{sys}\notepad.exe"; Parameters: "{#ProgramDataDir}\\config.yaml"; WorkingDir: "{#ProgramDataDir}"
Name: "{commondesktop}\LSM-6200 量測 GUI"; Filename: "{app}\{#AppExeGui}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "在桌面建立快捷方式"; GroupDescription: "其他選項:"; Flags: unchecked

[Run]
; Optionally run GUI after install
; Filename: "{app}\{#AppExeGui}"; Description: "啟動 {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Keep logs by default (no deletion entries for logs)
