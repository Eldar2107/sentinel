# Sentinel — Georgia Open Banking Compliance Platform

## Quick Start / Sürətli Başlanğıc

**English**
```powershell
# Open a terminal in the project folder and run:
.\run.ps1
```

**Azerbaijani**
```powershell
# Desktop‑da terminal aç və aşağıdakı əmri icra et:
.\run.ps1
```

After the script finishes you can access:
- 🌐 Dashboard → `http://localhost:3000`
- 🔌 Backend API → `http://localhost:8000/api`
- 📖 API Docs → `http://localhost:8000/docs`
- 🏦 Bank A docs → `http://localhost:8001/docs`
- 🏦 Bank B docs → `http://localhost:8002/docs`
- 🏦 Bank C docs → `http://localhost:8003/docs`

---

## Architecture / Arxitektura

```text
sentinel/
├─ backend/                # FastAPI + simulators
│   ├─ simulators/         # 3 bank simulators (A, B, C)
│   ├─ core/               # compliance, drift, security, normalization, scoring, DB init
│   └─ api/main.py         # API entry point, scheduled jobs
├─ ai/                     # AI engine for synthetic data & anomaly detection
├─ frontend/               # React dashboard (Vite + Nginx)
└─ docker-compose.yml      # Orchestrates 7 containers
```

## Bank Profiles / Bank Profilləri

| Bank | Compliance | Latency | Error Rate | Special Feature |
|------|------------|---------|------------|-----------------|
| **Bank A (TBC)** | ✅ Full | ~120 ms | 1 % | Standard format, HSTS |
| **Bank B (BoG)** | ⚠️ Partial | ~320 ms | 5 % | Slash dates, extra fields |
| **Bank C (Liberty)** | ❌ Weak | ~750 ms | 20 % | Unix timestamps, custom header, flaky |

## Scoring Formula / Skorinq Formulu
```
Total Score = Compliance×0.35 + Reliability×0.25 + Latency×0.20 + Security×0.20
```

## Commands / Əmrlər

```powershell
.\run.ps1                 # Start all services
.\run.ps1 -Rebuild        # Re‑build images (use after code changes)
.\run.ps1 -Logs           # Follow logs of all containers
.\run.ps1 -Status         # Show container status
.\run.ps1 -Down           # Stop and remove all containers
```

You can also use the helper script `deploy.sh` (Linux/WSL) which does the same:
```bash
./deploy.sh
```

---

## GitHub Repository
The repository is ready at `https://github.com/Eldar2107/sentinel`. After cloning or initializing locally run the commands above, then push your changes:
```bash
git init
git add .
git commit -m "Initial Sentinel stack"
git remote add origin https://github.com/Eldar2107/sentinel.git
git branch -M main
git push -u origin main
```
The CI workflow will automatically build and publish Docker images to GitHub Container Registry.
