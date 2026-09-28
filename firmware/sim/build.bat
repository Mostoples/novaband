@echo off
rem Builds the Nova-Band UI simulator with MSVC (VS 2022 Community).
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cd /d %~dp0
cl /nologo /O2 /std:c++17 /EHsc /W3 /wd4244 /D_CRT_SECURE_NO_WARNINGS /I "%USERPROFILE%\Documents\Arduino\libraries\ArduinoJson\src" ^
  sim_main.cpp ..\novaband_display\src\gfx.cpp ..\novaband_display\src\ui.cpp ^
  ..\novaband_display\src\model.cpp ..\novaband_display\src\protocol.cpp /Fe:sim.exe /Fo:obj\ 
