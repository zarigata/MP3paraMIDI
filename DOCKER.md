# Docker Deployment Guide for MP3paraMIDI

This guide covers Docker-based deployment options for MP3paraMIDI, including CPU-only and GPU-accelerated configurations.

**Developed by [zarigata](https://github.com/zarigata)**

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Docker Images](#docker-images)
4. [Docker Compose](#docker-compose)
5. [GPU Support](#gpu-support)
6. [Production Deployment](#production-deployment)
7. [Configuration](#configuration)
8. [Troubleshooting](#troubleshooting)
9. [Performance Tuning](#performance-tuning)
10. [Appendix](#appendix)

## Prerequisites

- Docker 20.10 or later
- Docker Compose 2.0 or later (bundled with Docker Desktop)
- Minimum hardware requirements: 4 GB RAM, 10 GB free disk space
- Recommended hardware: 8 GB RAM, 50 GB free disk space
- For GPU acceleration:
  - NVIDIA GPU with CUDA Compute Capability 3.5+
  - NVIDIA driver version 450.80.02 or later
  - NVIDIA Container Toolkit (nvidia-docker2)

## Quick Start

### Using Launcher Scripts (Recommended)

```bash
# Linux / macOS
chmod +x run.sh
./run.sh --mode=docker

# Windows
run.bat --mode=docker
```

### Manual Docker Compose

```bash
# Start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down

# Stop and remove volumes (deletes persistent data)
docker-compose down -v
```

### Service Endpoints

- Flask Web UI: http://localhost:8000/
- Flask API: http://localhost:8000/api/
- Gradio Interface: http://localhost:8000/gradio

## Docker Images

### CPU-Only Image (Default)

- Dockerfile: `Dockerfile`
- Base: `python:3.11-slim-bookworm`
- Size: ~2 GB
- Usage: General deployment without GPU requirements

Build locally:

```bash
docker build -t mp3paramidi:latest .
```

### GPU-Accelerated Image

- Dockerfile: `Dockerfile.gpu`
- Base: `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04`
- Size: ~4 GB
- Usage: Accelerated separation and transcription (5-10x faster)
- Requirements: NVIDIA GPU with CUDA support

Build locally:

```bash
docker build -f Dockerfile.gpu -t mp3paramidi:gpu .
```

### Pre-built Images

If pre-built images are published:

```bash
docker pull zarigata/mp3paramidi:latest
docker pull zarigata/mp3paramidi:gpu
```

## Docker Compose

### Development Setup

- File: `docker-compose.yml`
- Features: Hot reload ready, debug-friendly environment
- Launch:

```bash
docker-compose up
```

### Production Setup

- Files: `docker-compose.yml` + `docker-compose.prod.yml`
- Features: Multiple workers, resource limits, log rotation
- Launch:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `APP_HOST` | `0.0.0.0` | Host interface for unified server |
| `APP_PORT` | `8000` | Port for unified server |
| `APP_STORAGE_ROOT` | `/app/storage` | Persistent storage path |
| `FLASK_DEBUG` | `False` | Enables Flask debug mode |
| `MAX_UPLOAD_SIZE_MB` | `100` | Max upload size in MB |
| `CORS_ORIGINS` | `*` | Allowed origins (comma-separated) |
| `GRADIO_AUTH` | `` | Optional `username:password` for Gradio authentication |

Environment variables can be defined in `.env` (mounted read-only) or overridden in the compose files.

## GPU Support

### Prerequisites

- NVIDIA GPU with CUDA support
- NVIDIA Container Toolkit (nvidia-docker2)
- NVIDIA driver installed on host

Install NVIDIA Docker runtime (Ubuntu/Debian):

```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

Verify GPU access:

```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

Launch with GPU:

```bash
# Launcher script
./run.sh --mode=gpu

# Docker Compose override
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

Performance comparison (approximate):

| Audio Length | CPU Mode | GPU Mode |
| --- | --- | --- |
| 3 minutes | ~60 seconds | ~8 seconds |
| 10 minutes | ~200 seconds | ~25 seconds |

## Production Deployment

### Reverse Proxy (Nginx Example)

```nginx
server {
    listen 80;
    server_name mp3paramidi.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support for Gradio
    location /gradio {
        proxy_pass http://localhost:8000/gradio;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable HTTPS with Let's Encrypt:

```bash
sudo certbot --nginx -d mp3paramidi.example.com
```

### Resource Planning

- CPU: 4+ cores recommended
- RAM: 8 GB minimum (16 GB for large workloads)
- Storage: 50 GB+ persistent volume (`storage_data`)
- Network: 100 Mbps+ for large uploads

### Monitoring & Logging

- Health check endpoint: `/health`
- Docker health status: `docker ps`
- Logs: `docker-compose logs -f --tail=100`
- Consider log aggregation (ELK, Loki) and metrics (Prometheus, Grafana)

### Backup Strategy

```bash
# Backup storage volume
docker run --rm -v mp3paramidi_storage_data:/data -v $(pwd):/backup ubuntu tar czf /backup/storage-$(date +%Y%m%d).tar.gz /data

# Restore storage volumedocker run --rm -v mp3paramidi_storage_data:/data -v $(pwd):/backup ubuntu tar xzf /backup/storage-YYYYMMDD.tar.gz -C /
```

## Configuration

### Environment Files

1. Copy `.env.example` to `.env`
2. Adjust values for your deployment
3. Never commit `.env` to version control

### Volume Mounts

- `storage_data` (named volume) stores uploads, stems, and MIDI files
- Optional: Mount `.env` as read-only (`./.env:/app/.env:ro`)

### Port Mapping

- Default host port: `8000`
- Override via `APP_PORT` in `.env` or `docker-compose` file

## Troubleshooting

| Issue | Possible Cause | Resolution |
| --- | --- | --- |
| Container failing to start | Port conflict, missing `.env`, insufficient resources | Check logs, verify port availability (`netstat` / `lsof`), ensure `.env` exists |
| GPU not detected | Missing NVIDIA runtime or driver | Verify with `nvidia-smi`, reinstall NVIDIA Container Toolkit |
| Slow processing | CPU-only mode | Use GPU mode or increase worker count (CPU mode only) |
| Out of memory | Insufficient host RAM | Reduce workers, increase host memory, use GPU mode |
| Permission errors | Volume ownership | `docker-compose exec mp3paramidi chown -R appuser:appuser /app/storage` |

## Performance Tuning

### Worker Configuration

- CPU mode: 2–4 workers (≈ 2 × CPU cores)
- GPU mode: 1 worker (avoid CUDA context conflicts)

### Memory Management

- Each worker uses ~2 GB baseline
- Audio peak usage can reach 4 GB per worker
- Adjust Docker memory limits and compose resource settings accordingly

### Storage Optimization

- Use SSD-backed volumes for faster I/O
- Implement cleanup policies for old files
- Monitor usage: `docker system df`

### Network Optimization

- Use reverse proxy with caching (Nginx, Traefik, Varnish)
- Enable gzip compression for API responses
- Consider CDN for static assets

## Appendix

### Docker Commands Reference

| Command | Description |
| --- | --- |
| `docker-compose up -d` | Start services in detached mode |
| `docker-compose down` | Stop and remove services |
| `docker-compose logs -f` | Follow logs |
| `docker-compose ps` | List running services |
| `docker-compose exec mp3paramidi bash` | Obtain shell inside container |
| `docker-compose restart` | Restart services |
| `docker system prune -a` | Remove unused images and containers |

### Security Best Practices

- Run containers as non-root (configured via `appuser`)
- Use Docker secrets or environment management for credentials
- Enable HTTPS in production via reverse proxy
- Restrict `CORS_ORIGINS` to trusted domains
- Configure `GRADIO_AUTH` for authenticated access
- Keep base images and dependencies updated
- Scan images for vulnerabilities: `docker scan mp3paramidi:latest`

---

**Developed by [zarigata](https://github.com/zarigata)**

For more information, see the main [README.md](README.md).

Report issues on [GitHub Issues](https://github.com/zarigata/MP3paraMIDI/issues).
