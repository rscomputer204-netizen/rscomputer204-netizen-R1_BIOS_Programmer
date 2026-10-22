@echo off
:: BatchGotAdmin
:-------------------------------------
REM  --> Check for permissions
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"

REM --> If error flag set, we do not have admin.
if '%errorlevel%' NEQ '0' (
    echo Requesting administrative privileges...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    set params = %*:"=""
    echo UAC.ShellExecute "cmd.exe", "/c ""%~s0"" %params%", "", "runas", 1 >> "%temp%\getadmin.vbs"

    "%temp%\getadmin.vbs"
    del "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    pushd "%CD%"
    CD /D "%~dp0"
:--------------------------------------

echo ===================================================
echo   RESTORING OFFICIAL FTDI D2XX DRIVER FOR FT232H
echo ===================================================
echo.

echo 1. Removing WinUSB driver packages...
pnputil /delete-driver oem19.inf /uninstall /force >nul 2>&1
for /f "tokens=1" %%d in ('pnputil /enum-drivers ^| findstr /i "r1_winusb"') do (
    pnputil /delete-driver %%d /uninstall /force
)

echo 2. Installing official FTDI D2XX driver...
if exist "%~dp0python_version\drivers\ftdi\ftdibus.inf" (
    pnputil /add-driver "%~dp0python_version\drivers\ftdi\ftdibus.inf" /install
)
if exist "%~dp0drivers\ftdi\ftdibus.inf" (
    pnputil /add-driver "%~dp0drivers\ftdi\ftdibus.inf" /install
)

echo 3. Rescanning Plug and Play devices...
pnputil /scan-devices

echo.
echo ===================================================
echo   SUCCESS! FTDI Driver Restored.
echo   FT232H is now ready for BIOS Programmer!
echo ===================================================
echo.
pause
