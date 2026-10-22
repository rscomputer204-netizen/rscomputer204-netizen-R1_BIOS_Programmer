@echo off
echo Building Programmer Core DLL...

if not exist "libs" mkdir libs

:: Using g++ (MinGW) to compile the DLL
:: If you have Visual Studio, you can use cl.exe instead
g++ -shared -o libs/programmer_core.dll src/programmer_core.cpp -Wl,--out-implib,libs/programmer_core.a

if %ERRORLEVEL% EQU 0 (
    echo Build Successful! DLL location: hardware_lib/libs/programmer_core.dll
) else (
    echo Build Failed. Please ensure MinGW g++ is in your PATH.
)
pause
