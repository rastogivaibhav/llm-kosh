!include nsDialogs.nsh
!include LogicLib.nsh

Var SourceFolder
Var DestinationFolder
Var SourceInput
Var DestinationInput

Function SelectSourceFolder
  nsDialogs::SelectFolderDialog "Select the folder containing your work" "$DOCUMENTS"
  Pop $SourceFolder
  ${If} $SourceFolder != ""
    ${NSD_SetText} $SourceInput $SourceFolder
  ${EndIf}
FunctionEnd

Function SelectDestinationFolder
  nsDialogs::SelectFolderDialog "Select where LLM-Kosh stores its local data" "$DOCUMENTS"
  Pop $DestinationFolder
  ${If} $DestinationFolder != ""
    ${NSD_SetText} $DestinationInput $DestinationFolder
  ${EndIf}
FunctionEnd

Function ConfigPageCreate
  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0 0 100% 18u "Choose the folder containing your work and the folder where LLM-Kosh stores its local index."
  Pop $0
  ${NSD_CreateLabel} 0 30u 100% 14u "Work folder (files stay here)"
  Pop $0
  ${NSD_CreateText} 0 46u 78% 14u ""
  Pop $SourceInput
  ${NSD_CreateButton} 80% 46u 20% 14u "Browse..."
  Pop $0
  ${NSD_OnClick} $0 SelectSourceFolder

  ${NSD_CreateLabel} 0 76u 100% 14u "LLM-Kosh data folder (index and citations)"
  Pop $0
  ${NSD_CreateText} 0 92u 78% 14u ""
  Pop $DestinationInput
  ${NSD_CreateButton} 80% 92u 20% 14u "Browse..."
  Pop $0
  ${NSD_OnClick} $0 SelectDestinationFolder
  nsDialogs::Show
FunctionEnd

Function ConfigPageLeave
  ${NSD_GetText} $SourceInput $SourceFolder
  ${NSD_GetText} $DestinationInput $DestinationFolder
  ${If} $SourceFolder == ""
    MessageBox MB_ICONEXCLAMATION "Choose a work folder to continue."
    Abort
  ${EndIf}
  ${If} $DestinationFolder == ""
    MessageBox MB_ICONEXCLAMATION "Choose an LLM-Kosh data folder to continue."
    Abort
  ${EndIf}
  ${If} $SourceFolder == $DestinationFolder
    MessageBox MB_ICONEXCLAMATION "The work folder and LLM-Kosh data folder must be different."
    Abort
  ${EndIf}
FunctionEnd

Page custom ConfigPageCreate ConfigPageLeave

!macro customInstall
  CreateDirectory "$INSTDIR\resources"
  FileOpen $0 "$INSTDIR\resources\llm-kosh-install.conf" w
  FileWrite $0 "source=$SourceFolder$\r$\n"
  FileWrite $0 "destination=$DestinationFolder$\r$\n"
  FileClose $0
  DetailPrint "LLM-Kosh source and destination folders configured."
!macroend

!macro customUninstall
  IfFileExists "$INSTDIR\resources\bin\llm-kosh.exe" 0 +3
    ExecWait '"$INSTDIR\resources\bin\llm-kosh.exe" service stop'
    ExecWait '"$INSTDIR\resources\bin\llm-kosh.exe" uninstall --yes'
!macroend
