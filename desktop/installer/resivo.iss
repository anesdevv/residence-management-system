; RÉSIVO Desktop Console — Zero-Prerequisite Windows 10/11 64-bit Installer
#define MyAppName "RÉSIVO"
#define MyAppVersion "0.1.1"
#define MyAppPublisher "Direction des Œuvres Universitaires · Cité Universitaire · Tlemcen"
#define MyAppURL "https://github.com/anesdevv/residence-management-system"
#define MyAppExeName "RESIVO.exe"

[Setup]
AppId={{D37E84B1-6A22-4F15-B61E-7D49B892F1A0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\RESIVO
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=Setup-RESIVO-{#MyAppVersion}
SetupIconFile=..\assets\brand\resivo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[CustomMessages]
english.AutostartTask=Start RÉSIVO when Windows starts
french.AutostartTask=Démarrer RÉSIVO au lancement de Windows
english.RemoveUserDataPrompt=Do you also want to delete saved RÉSIVO preferences, logs, and cached session data for your Windows account?%n%nChoose No to keep your settings if you plan to reinstall later.
french.RemoveUserDataPrompt=Voulez-vous également supprimer vos préférences, journaux et données de session RÉSIVO enregistrés pour votre compte Windows ?%n%nChoisissez Non pour conserver vos paramètres en cas de réinstallation.
english.Require64BitWindows=RÉSIVO requires a 64-bit edition of Windows 10 (21H2 or later) or Windows 11.
french.Require64BitWindows=RÉSIVO nécessite une édition 64 bits de Windows 10 (21H2 ou ultérieure) ou Windows 11.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "{cm:AutostartTask}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\RESIVO\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Optional autostart enabled during install
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "RESIVO"; ValueData: """{app}\{#MyAppExeName}"" --autostart"; Flags: uninsdeletevalue; Tasks: autostart
; Always clean up any Run / StartupApproved entry created later inside Settings -> General
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "RESIVO"; Flags: dontcreatekey uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"; ValueName: "RESIVO"; Flags: dontcreatekey uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  if not IsWin64 then
  begin
    MsgBox(CustomMessage('Require64BitWindows'), mbCriticalError, MB_OK);
    Result := False;
    Exit;
  end;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  RoamingDir: string;
  LocalDir: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if not UninstallSilent then
    begin
      if MsgBox(CustomMessage('RemoveUserDataPrompt'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        RoamingDir := ExpandConstant('{userappdata}\RESIVO');
        LocalDir := ExpandConstant('{localappdata}\RESIVO');
        if DirExists(RoamingDir) then
          DelTree(RoamingDir, True, True, True);
        if DirExists(LocalDir) then
          DelTree(LocalDir, True, True, True);
        RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\RESIVO');
      end;
    end;
  end;
end;
