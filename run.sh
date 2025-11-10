#!/usr/bin/env bash
# MP3paraMIDI Launcher Script for Linux/Mac
# Developed by zarigata
# Supports Docker and local virtual environment modes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="mp3paramidi"
VENV_DIR="${SCRIPT_DIR}/venv"
PYTHON_MIN_VERSION="3.10"
DEFAULT_MODE="auto"
PORT="8000"
DOCKER_COMPOSE_CMD=()

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() {
  printf "%b%s%b\n" "${GREEN}" "$1" "${NC}"
}

print_warn() {
  printf "%b%s%b\n" "${YELLOW}" "$1" "${NC}"
}

print_error() {
  printf "%b%s%b\n" "${RED}" "$1" "${NC}"
  exit 1
}

check_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    print_error "Required command '$1' not found. Please install it first."
  fi
}

resolve_docker_compose() {
  if [[ ${#DOCKER_COMPOSE_CMD[@]} -gt 0 ]]; then
    return
  fi
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD=(docker compose)
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD=(docker-compose)
    return
  fi
  print_error "Neither 'docker compose' nor 'docker-compose' was found. Install Docker Compose v2."
}

check_python_version() {
  if ! command -v python >/dev/null 2>&1; then
    print_error "Python is not installed or not in PATH."
  fi
  local version
  version="$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"
  if [[ "$(printf '%s\n%s\n' "$PYTHON_MIN_VERSION" "$version" | sort -V | head -n1)" != "$PYTHON_MIN_VERSION" ]]; then
    print_error "Python ${PYTHON_MIN_VERSION}+ is required. Found ${version}."
  fi
}

check_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    print_error "Docker is not installed or not in PATH."
  fi
  if ! docker info >/dev/null 2>&1; then
    print_error "Docker daemon is not running or current user lacks permissions."
  fi
}

check_env_file() {
  if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
    if [[ -f "${SCRIPT_DIR}/.env.example" ]]; then
      print_warn ".env not found. Creating from .env.example."
      cp "${SCRIPT_DIR}/.env.example" "${SCRIPT_DIR}/.env"
    else
      print_error ".env.example not found. Cannot create .env file."
    fi
  fi
}

check_port() {
  if command -v lsof >/dev/null 2>&1; then
    if lsof -i ":${PORT}" >/dev/null 2>&1; then
      print_error "Port ${PORT} is already in use. Please free the port or set APP_PORT to another value."
    fi
    return
  fi
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn | grep -E -q ":${PORT}([[:space:]]|$)"; then
      print_error "Port ${PORT} is already in use. Please free the port or set APP_PORT to another value."
    fi
    return
  fi
  if command -v netstat >/dev/null 2>&1; then
    if netstat -tuln | grep -E -q ":${PORT}([[:space:]]|$)"; then
      print_error "Port ${PORT} is already in use. Please free the port or set APP_PORT to another value."
    fi
  fi
}

print_banner() {
  cat <<'EOF'
╔═══════════════════════════════════════╗
║     MP3paraMIDI Launcher v1.0.0      ║
║   AI-Powered Audio to MIDI Converter  ║
╚═══════════════════════════════════════╝
EOF
}

usage() {
  cat <<'EOF'
Usage: ./run.sh [OPTIONS]

Options:
  --mode=MODE    Specify run mode: docker, gpu, venv, auto (default: auto)
  --help         Show this help message
  --version      Show script version

Modes:
  docker    Run using Docker (CPU-only)
  gpu       Run using Docker with GPU acceleration
  venv      Run using local Python virtual environment
  auto      Auto-detect (use Docker if available, fallback to venv)

Examples:
  ./run.sh                    # Auto-detect mode
  ./run.sh --mode=docker      # Force Docker mode
  ./run.sh --mode=gpu         # Use GPU acceleration
  ./run.sh --mode=venv        # Use local Python

Access:
  Flask Web UI: http://localhost:8000/
  Flask API: http://localhost:8000/api/
  Gradio Interface: http://localhost:8000/gradio
EOF
}

print_version() {
  echo "MP3paraMIDI Launcher v1.0.0"
  echo "Developed by zarigata"
}

cleanup() {
  if [[ "${MODE}" == "docker" ]]; then
    resolve_docker_compose
    "${DOCKER_COMPOSE_CMD[@]}" down >/dev/null 2>&1 || true
  elif [[ "${MODE}" == "gpu" ]]; then
    resolve_docker_compose
    "${DOCKER_COMPOSE_CMD[@]}" -f docker-compose.yml -f docker-compose.gpu.yml down >/dev/null 2>&1 || true
  fi
}

run_docker_mode() {
  check_docker
  resolve_docker_compose
  check_env_file
  print_info "Starting MP3paraMIDI in Docker mode (CPU)."
  print_info "Access the application at http://localhost:8000/"
  trap cleanup EXIT INT TERM
  "${DOCKER_COMPOSE_CMD[@]}" up --build
}

run_docker_gpu_mode() {
  check_docker
  resolve_docker_compose
  check_env_file
  print_info "Starting MP3paraMIDI in Docker GPU mode."
  print_info "Verifying NVIDIA runtime..."
  if ! docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
    print_error "NVIDIA Docker runtime not available. Install nvidia-docker2 and ensure GPU is accessible."
  fi
  print_info "Access the application at http://localhost:8000/"
  trap cleanup EXIT INT TERM
  "${DOCKER_COMPOSE_CMD[@]}" -f docker-compose.yml -f docker-compose.gpu.yml up --build
}

run_venv_mode() {
  check_python_version
  check_env_file
  check_port
  if [[ ! -d "${VENV_DIR}" ]]; then
    print_info "Creating virtual environment at ${VENV_DIR}."
    python -m venv "${VENV_DIR}"
    source "${VENV_DIR}/bin/activate"
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt
  else
    source "${VENV_DIR}/bin/activate"
  fi
  print_info "Starting MP3paraMIDI using local Python environment."
  print_info "Access the application at http://localhost:8000/"
  trap 'print_info "Stopping application..."; deactivate 2>/dev/null || true; exit 0' INT TERM
  python src/main.py
}

run_auto_mode() {
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    print_info "Docker detected. Running in Docker mode."
    MODE="docker"
    run_docker_mode
  else
    print_warn "Docker not available. Falling back to virtual environment mode."
    MODE="venv"
    run_venv_mode
  fi
}

MODE="${DEFAULT_MODE}"
while (($#)); do
  case "$1" in
    --mode)
      shift
      [[ $# -gt 0 ]] || print_error "--mode requires an argument."
      MODE="$1"
      ;;
    --mode=*)
      MODE="${1#*=}"
      ;;
    --help)
      usage
      exit 0
      ;;
    --version)
      print_version
      exit 0
      ;;
    *)
      print_error "Unknown option: $1"
      ;;
  esac
  shift || true
done

print_banner

cd "${SCRIPT_DIR}"

case "$MODE" in
  docker)
    run_docker_mode
    ;;
  gpu)
    run_docker_gpu_mode
    ;;
  venv)
    run_venv_mode
    ;;
  auto)
    run_auto_mode
    ;;
  *)
    print_error "Invalid mode: ${MODE}. Use docker, gpu, venv, or auto."
    ;;
esac
