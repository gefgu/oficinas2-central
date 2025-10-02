@echo off
REM Oficinas2 Central - Quick Start Setup Script for Windows
REM This script sets up the development environment

echo ================================
echo Oficinas2 Central - Quick Start
echo ================================
echo.

REM Check Python version
echo [*] Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python is not installed or not in PATH.
    echo     Please install Python 3.8 or higher from https://python.org
    pause
    exit /b 1
)

python --version
echo [OK] Python found
echo.

REM Create virtual environment
echo [*] Creating virtual environment...
if exist "fastapi_env\" (
    echo [!] Virtual environment 'fastapi_env' already exists.
    set /p RECREATE="Do you want to recreate it? (y/N): "
    if /i "%RECREATE%"=="y" (
        echo Removing existing virtual environment...
        rmdir /s /q fastapi_env
        python -m venv fastapi_env
        echo [OK] Virtual environment recreated
    ) else (
        echo [!] Using existing virtual environment
    )
) else (
    python -m venv fastapi_env
    echo [OK] Virtual environment created
)
echo.

REM Activate virtual environment
echo [*] Activating virtual environment...
call fastapi_env\Scripts\activate.bat
echo [OK] Virtual environment activated
echo.

REM Upgrade pip
echo [*] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo [OK] pip upgraded
echo.

REM Install dependencies
echo [*] Installing dependencies from requirements.txt...
echo This may take a few minutes...
pip install -r requirements.txt
if errorlevel 1 (
    echo [X] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] All dependencies installed successfully
echo.

REM Check for data files
echo [*] Checking for required data files...
set MISSING_FILES=0

if not exist "dados\Curitiba_resolution_10.geojson" (
    echo [!] Missing: dados\Curitiba_resolution_10.geojson
    set MISSING_FILES=1
)

if not exist "dados\bairros_curitiba.zip" (
    echo [!] Missing: dados\bairros_curitiba.zip
    set MISSING_FILES=1
)

if %MISSING_FILES%==0 (
    echo [OK] All required data files found
) else (
    echo [!] Some data files are missing. Please ensure you have:
    echo     - dados\Curitiba_resolution_10.geojson
    echo     - dados\bairros_curitiba.zip
)
echo.

REM Check for model files
echo [*] Checking for trained model files...
set MISSING_MODELS=0

if not exist "modelos\lgb_purpose_model.pkl" (
    echo [!] Missing: modelos\lgb_purpose_model.pkl
    set MISSING_MODELS=1
)

if not exist "modelos\lgb_purpose_encoders.pkl" (
    echo [!] Missing: modelos\lgb_purpose_encoders.pkl
    set MISSING_MODELS=1
)

if not exist "server\random_forest_model.pkl" (
    echo [!] Missing: server\random_forest_model.pkl
    set MISSING_MODELS=1
)

if %MISSING_MODELS%==0 (
    echo [OK] All required model files found
) else (
    echo [!] Some model files are missing. Train models using:
    echo     - notebooks\modelo_proposito_foursquare.ipynb
    echo     - notebooks\modelo_de_transporte.ipynb
)
echo.

REM Initialize database
echo [*] Initializing database...
cd server
python db_commands.py
if errorlevel 1 (
    echo [X] Failed to initialize database
    cd ..
    pause
    exit /b 1
)
echo [OK] Database tables created
cd ..
echo.

REM Create .env file if it doesn't exist
echo [*] Configuring environment...
if not exist "server\.env" (
    (
        echo # Database Configuration
        echo # Set to 'true' for production database (dados.db^)
        echo # Set to 'false' for test database (dados_test.db^)
        echo PRODUCTION_MODE=false
    ) > server\.env
    echo [OK] Created server\.env file
) else (
    echo [!] server\.env already exists
)
echo.

REM Create startup script
echo [*] Creating startup script...
(
    echo @echo off
    echo REM Start the Oficinas2 Central server
    echo.
    echo REM Activate virtual environment
    echo call fastapi_env\Scripts\activate.bat
    echo.
    echo REM Set to development mode (use test database^)
    echo set PRODUCTION_MODE=false
    echo.
    echo REM Start server
    echo cd server
    echo echo Starting Oficinas2 Central server...
    echo echo Server will be available at: http://localhost:8000
    echo echo API documentation at: http://localhost:8000/docs
    echo echo.
    echo echo Press Ctrl+C to stop the server
    echo echo.
    echo REM Use uvicorn with --reload for development (auto-restarts on code changes^)
    echo python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
) > start_server.bat
echo [OK] Created start_server.bat
echo.

REM Summary
echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo.
echo 1. Start the server:
echo    start_server.bat
echo.
echo 2. Or manually (recommended - includes auto-reload):
echo    fastapi_env\Scripts\activate.bat
echo    cd server
echo    python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
echo.
echo 3. Run tests:
echo    fastapi_env\Scripts\activate.bat
echo    pytest server\test_main.py -v
echo.
echo 4. Access API documentation:
echo    http://localhost:8000/docs
echo.

if %MISSING_FILES%==1 (
    echo [!] Warning: Some data files are missing.
    echo     Please check the messages above for details.
    echo.
)

if %MISSING_MODELS%==1 (
    echo [!] Warning: Some model files are missing.
    echo     Please check the messages above for details.
    echo.
)

echo Happy coding!
pause
