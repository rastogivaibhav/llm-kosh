; Custom NSIS sections injected by electron-builder via nsis.include
; Runs after all files are installed — wires up the daemon, MCP, and cartridge.

!macro customInstall
  ; Run llm-kosh install using the bundled sidecar binary
  ; The sidecar is placed at $INSTDIR\resources\bin\llm-kosh.exe by electron-builder
  DetailPrint "Configuring llm-kosh service and MCP registration..."

  ; Try bundled sidecar first
  IfFileExists "$INSTDIR\resources\bin\llm-kosh.exe" useSidecar useSystemPath

  useSidecar:
    ExecWait '"$INSTDIR\resources\bin\llm-kosh.exe" install --yes' $0
    Goto installDone

  useSystemPath:
    ; Fall back to system PATH (pip-installed version)
    ExecWait '"llm-kosh" install --yes' $0

  installDone:
  DetailPrint "llm-kosh install exited with code $0"

  ; Start the daemon immediately (don't wait for next login)
  IfFileExists "$INSTDIR\resources\bin\llm-kosh.exe" startSidecarDaemon startSystemDaemon

  startSidecarDaemon:
    Exec '"$INSTDIR\resources\bin\llm-kosh.exe" service start'
    Goto daemonDone

  startSystemDaemon:
    Exec '"llm-kosh" service start'

  daemonDone:
!macroend

!macro customUninstall
  ; Stop daemon on uninstall
  IfFileExists "$INSTDIR\resources\bin\llm-kosh.exe" stopSidecarDaemon stopSystemDaemon

  stopSidecarDaemon:
    ExecWait '"$INSTDIR\resources\bin\llm-kosh.exe" service stop'
    Goto daemonStopped

  stopSystemDaemon:
    ExecWait '"llm-kosh" service stop'

  daemonStopped:

  ; Remove the startup folder bat file
  Delete "$APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\llm-kosh-daemon.bat"

  DetailPrint "llm-kosh daemon stopped and startup entry removed."
!macroend
