@echo off
echo.
echo =========================================
echo    Quick101 v2.1 EXE Builder
echo =========================================
echo.

REM Install requirements
echo Installing requirements...
python -m pip install pyinstaller PyQt6 PyYAML Pillow >nul 2>&1

REM Create default files
echo Creating config files...
if not exist accounts.yml (
    echo Default: > accounts.yml
    echo   Sample: >> accounts.yml
    echo     username: "your_username" >> accounts.yml
    echo     password: "your_password" >> accounts.yml
)

if not exist launcher_config.json (
    echo {"theme_index": 0, "wiz_path": "C:/ProgramData/KingsIsle Entertainment/Wizard101/Bin/"} > launcher_config.json
)

if not exist backgrounds mkdir backgrounds

REM Build using spec file
echo.
echo Building Quick101.exe using spec file...
echo ============================================

pyinstaller --clean Quick101.spec

if exist dist\Quick101.exe (
    copy /Y Quick101.ico dist\ >nul 2>&1
    copy /Y Quick101.png dist\ >nul 2>&1
    echo.
    echo ============================================
    echo   SUCCESS! Quick101.exe created!
    echo   Location: dist\Quick101.exe
    echo ============================================
) else (
    echo.
    echo ============================================
    echo   Build failed - trying basic method...
    echo ============================================
    pyinstaller --onefile --windowed --icon=Quick101.ico --name=Quick101 --exclude-module=PyQt5 --add-data "Quick101.png;." --add-data "Quick101.ico;." Quick101.py
    
    if exist dist\Quick101.exe (
        echo   Basic build succeeded!
        echo   Location: dist\Quick101.exe
    ) else (
        echo   Both methods failed!
    )
)

echo.
pause
