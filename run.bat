@echo off
REM MP3paraMIDI Launcher Script for Windows
REM Developed by zarigata
REM Supports Docker and local virtual environment modes

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_NAME=mp3paramidi"
set "VENV_DIR=%SCRIPT_DIR%venv"
set "PYTHON_MIN_VERSION=3.10"
set "DEFAULT_MODE=auto"
set "PORT=8000"
set "DOCKER_COMPOSE_CMD="

set "MODE=%DEFAULT_MODE%"

:parse_args
if "%~1"=="" goto :after_args
if /I "%~1"=="--help" goto :show_help
if /I "%~1"=="--version" goto :show_version
if /I "%~1"=="--mode" (
    shift
    if "%~1"=="" (
        call :print_error "--mode requires a value (docker|gpu|venv|auto)."
    )
    set "MODE=%~1"
    shift
    goto :parse_args
)
if /I "%~1:~0,7%"=="--mode=" (
    set "MODE=%~1"
    set "MODE=!MODE:~7!"
    for %%M in ("!MODE!") do set "MODE=%%~M"
    shift
    goto :parse_args
)
call :print_error "Unknown option: %~1"

:after_args

echo ╔═══════════════════════════════════════╗
echo ║     MP3paraMIDI Launcher v1.0.0      ║
echo ║   AI-Powered Audio to MIDI Converter  ║
echo ╚═══════════════════════════════════════╝
echo.

cd /d "%SCRIPT_DIR%"

if /I "%MODE%"=="docker" goto :run_docker_mode
if /I "%MODE%"=="gpu" goto :run_docker_gpu_mode
if /I "%MODE%"=="venv" goto :run_venv_mode
if /I "%MODE%"=="auto" goto :run_auto_mode

echo [ERROR] Invalid mode: %MODE%. Use docker, gpu, venv, or auto.
goto :end

:print_info
set "MESSAGE=%~1"
echo [INFO] %MESSAGE%
goto :eof

:print_warn
set "MESSAGE=%~1"
echo [WARN] %MESSAGE%
goto :eof

:print_error
set "MESSAGE=%~1"
echo [ERROR] %MESSAGE%
exit /b 1

:check_command
where %~1 >nul 2>&1 || call :print_error "Required command '%~1' not found."
goto :eof

:resolve_docker_compose
if defined DOCKER_COMPOSE_CMD goto :eof
docker compose version >nul 2>&1
if %errorlevel%==0 (
    set "DOCKER_COMPOSE_CMD=docker compose"
    goto :eof
)
where docker-compose >nul 2>&1
if %errorlevel%==0 (
    set "DOCKER_COMPOSE_CMD=docker-compose"
    goto :eof
)
call :print_error "Neither 'docker compose' nor 'docker-compose' was found. Install Docker Compose v2."
goto :eof

:check_python_version
where python >nul 2>&1 || call :print_error "Python is not installed or not in PATH."
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 || call :print_error "Python %PYTHON_MIN_VERSION% or higher is required."
goto :eof

:check_docker
call :check_command docker
docker info >nul 2>&1 || call :print_error "Docker daemon is not running or access is denied."
goto :eof

:check_env_file
if exist "%SCRIPT_DIR%.env" goto :eof
if exist "%SCRIPT_DIR%.env.example" (
    call :print_warn ".env not found. Creating from .env.example."
    copy /Y "%SCRIPT_DIR%.env.example" "%SCRIPT_DIR%.env" >nul
    goto :eof
)
call :print_error ".env.example not found. Cannot create .env file."

goto :eof

:check_port
netstat -ano | findstr /R /C":%PORT%" >nul 2>&1 && call :print_error "Port %PORT% is in use. Free the port or set APP_PORT to another value."
goto :eof

:run_docker_mode
call :check_docker
call :resolve_docker_compose
call :check_env_file
call :print_info "Starting MP3paraMIDI in Docker mode (CPU)."
call :print_info "Access the application at http://localhost:8000/"
!DOCKER_COMPOSE_CMD! up --build
call :print_info "Stopping containers..."
!DOCKER_COMPOSE_CMD! down
goto :end

:run_docker_gpu_mode
call :check_docker
call :resolve_docker_compose
call :check_env_file
call :print_info "Starting MP3paraMIDI in Docker GPU mode."
call :print_info "Verifying NVIDIA runtime..."
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi >nul 2>&1 || call :print_error "NVIDIA Docker runtime not available. Install nvidia-docker2 and ensure GPU access."
call :print_info "Access the application at http://localhost:8000/"
!DOCKER_COMPOSE_CMD! -f docker-compose.yml -f docker-compose.gpu.yml up --build
call :print_info "Stopping containers..."
!DOCKER_COMPOSE_CMD! -f docker-compose.yml -f docker-compose.gpu.yml down
goto :end

:run_venv_mode
call :check_python_version
call :check_env_file
call :check_port
if not exist "%VENV_DIR%" (
    call :print_info "Creating virtual environment at %VENV_DIR%."
    python -m venv "%VENV_DIR%" || call :print_error "Failed to create virtual environment."
    call "%VENV_DIR%\Scripts\activate.bat"
    python -m pip install --upgrade pip setuptools wheel
    python -m pip install -r requirements.txt
) else (
    call "%VENV_DIR%\Scripts\activate.bat"
)
call :print_info "Starting MP3paraMIDI using local Python environment."
call :print_info "Access the application at http://localhost:8000/"
python src\main.py
call "%VENV_DIR%\Scripts\deactivate.bat" >nul 2>&1
goto :end

:run_auto_mode
where docker >nul 2>&1
if %errorlevel%==0 (
    docker info >nul 2>&1
    if %errorlevel%==0 (
        call :print_info "Docker detected. Running in Docker mode."
        set "MODE=docker"
        goto :run_docker_mode
    )
)
call :print_warn "Docker not available. Falling back to virtual environment mode."
set "MODE=venv"
goto :run_venv_mode

:show_help
echo Usage: run.bat [OPTIONS]
echo.
echo Options:
echo   --mode=MODE    Specify run mode: docker, gpu, venv, auto ^(default: auto^)
echo   --help         Show this help message
echo   --version      Show script version
echo.
echo Modes:
echo   docker    Run using Docker ^(CPU-only^)
echo   gpu       Run using Docker with GPU acceleration
echo   venv      Run using local Python virtual environment
echo   auto      Auto-detect ^(use Docker if available, fallback to venv^)
echo.
echo Examples:
echo   run.bat                    REM Auto-detect mode
echo   run.bat --mode=docker      REM Force Docker mode
echo   run.bat --mode=gpu         REM Use GPU acceleration
echo   run.bat --mode=venv        REM Use local Python
echo.
echo Access:
echo   Flask Web UI: http://localhost:8000/
echo   Flask API: http://localhost:8000/api/
echo   Gradio Interface: http://localhost:8000/gradio
echo.
echo Press any key to exit...
pause >nul
goto :end

:show_version
echo MP3paraMIDI Launcher v1.0.0
echo Developed by zarigata
goto :end

:end
endlocal
exit /b 0
