[Setup]
AppId={{0BCB2484-9DF9-47F5-8EDA-F355B63E75F5}
AppName=Frankesso
AppVersion=2.0.0
AppPublisher=Frankesso
DefaultDirName={localappdata}\Programs\Frankesso
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.10240
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\assets\frankesso.ico
SetupIconFile=..\assets\frankesso.ico
AppMutex=Local\FrankessoDesktop
OutputDir=..\dist
OutputBaseFilename=Frankesso-2.0.0-Windows-x64-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "build\payload\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Frankesso"; Filename: "{app}\python\pythonw.exe"; Parameters: "-E -s -B ""{app}\agent\desktop.py"" --installed"; WorkingDir: "{app}"; IconFilename: "{app}\assets\frankesso.ico"; AppUserModelID: "Frankesso.Desktop"

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-E -s -B ""{app}\agent\desktop.py"" --installed"; WorkingDir: "{app}"; Description: "Open Frankesso"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{localappdata}\FrankessoDesktop\models\Qwen3-4B-Q4_K_M.gguf"
Type: files; Name: "{localappdata}\FrankessoDesktop\models\qwen-download-*.part"
Type: dirifempty; Name: "{localappdata}\FrankessoDesktop\models"
Type: dirifempty; Name: "{localappdata}\FrankessoDesktop"
