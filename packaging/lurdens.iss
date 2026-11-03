; Instalador do Lurdens para Windows (Inno Setup 6).
;
; Gera Lurdens-Setup-<versão>-windows-x64.exe a partir da pasta dist\Lurdens
; criada pelo PyInstaller (packaging/lurdens.spec). Usado pela CI
; (.github/workflows/release.yml); para gerar à mão no Windows:
;
;   python -m PyInstaller packaging\lurdens.spec --noconfirm
;   "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DAppVersion=1.3.1 ^
;       /DSourceDir=%CD%\dist\Lurdens /DOutputDir=%CD%\dist ^
;       /DIconFile=%CD%\dist\lurdens.ico packaging\lurdens.iss
;
; Instala só para o usuário atual (sem pedir administrador) em
; %LOCALAPPDATA%\Programs\Lurdens, cria o atalho no Menu Iniciar, aparece em
; Configurações › Aplicativos e atualiza por cima de uma versão anterior.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\Lurdens"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
#ifndef IconFile
  #define IconFile "..\dist\lurdens.ico"
#endif

#define AppName "Lurdens"
#define AppExe "Lurdens.exe"
#define AppUrl "https://github.com/lucasks2001/Lurdens"

[Setup]
; O AppId identifica o programa entre versões: NÃO mude, senão as atualizações
; passam a instalar uma segunda cópia em vez de substituir a anterior.
AppId={{6B2E8C41-3F7A-4D59-9A0E-5C1D7B3F2A86}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=lucasks2001
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription=Instalador do {#AppName}

DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
DisableReadyPage=yes
UsePreviousAppDir=yes

PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

OutputDir={#OutputDir}
OutputBaseFilename=Lurdens-Setup-{#AppVersion}-windows-x64
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

; O Lurdens pode estar aberto na bandeja: fecha antes de substituir os arquivos.
CloseApplications=force
CloseApplicationsFilter=*.exe,*.dll,*.pyd
RestartApplications=no
ShowLanguageDialog=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Atualização: apaga as bibliotecas da versão anterior antes de copiar as novas,
; para não sobrar DLL antiga misturada com a nova.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "Player complementar para o Spotify"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Não cria nada na instalação; só remove, ao desinstalar, a entrada de
; "Iniciar com o Windows" que o próprio Lurdens grava quando a opção é ligada.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Lurdens"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Encerra o Lurdens (inclusive se estiver só na bandeja) antes de remover os arquivos.
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExe} /T"; Flags: runhidden; RunOnceId: "EncerrarLurdens"

[Code]
// Ao desinstalar pela tela (não no modo silencioso), pergunta se também
// deve apagar configurações, histórico salvo, tempo de uso e cache de capas.
// Respondendo "Não", tudo fica guardado para uma reinstalação futura.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
  begin
    if MsgBox('Remover também as configurações, o histórico e o cache do Lurdens?' + #13#10 + #13#10 +
              'Escolha "Não" para manter tudo caso reinstale depois.',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      DelTree(ExpandConstant('{userappdata}\Lurdens'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\Lurdens'), True, True, True);
    end;
  end;
end;
