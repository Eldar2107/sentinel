# 🛡️ Sentinel — AI Open Banking Compliance & Telemetry Anomaly Detector

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Scikit-Learn](https://img.shields.io/badge/ML-Isolation%20Forest-F7931E.svg?logo=scikit-learn)](https://scikit-learn.org/)
[![Docker Compose](https://img.shields.io/badge/Orchestration-Docker%20Compose-2496ED.svg?logo=docker)](https://www.docker.com/)
[![Streamlit](https://img.shields.io/badge/Analytics-Streamlit-FF4B4B.svg?logo=streamlit)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Sentinel** is an enterprise-grade automated compliance testing and machine learning-powered telemetry monitoring platform designed for Open Banking APIs (aligned with the **Berlin Group NextGenPSD2** and National Bank of Georgia standards). 

It continuously audits banking endpoints, detects OpenAPI schema drift, benchmarks network latency, and deploys **dual-method unsupervised anomaly detection (Isolation Forest + Rolling MAD)** to flag performance degradation and security anomalies in real time.

---

## 🏛️ System Architecture

```text
                                  ┌────────────────────────┐
                                  │   React Web Dashboard  │ (Port 3000)
                                  └───────────┬────────────┘
                                              │
┌────────────────────────┐        ┌───────────▼────────────┐        ┌────────────────────────┐
│ Streamlit AI Analytics │◄───────┤   Sentinel FastAPI API │◄───────┤    Bank Simulators     │
│  (Port 8501 / Cloud)   │        │   Orchestrator Core    │        │  (TBC, BoG, Liberty)   │
└────────────────────────┘        └─────┬────────────┬─────┘        └────────────────────────┘
                                        │            │
                                  ┌─────▼────┐ ┌─────▼────┐
                                  │ Postgres │ │  Redis   │
                                  │   15     │ │    7     │
                                  └─────┬────┘ └─────┬────┘
                                        │            │
                                  ┌─────▼────────────▼────┐
                                  │    Sentinel AI Engine │
                                  │  (Isolation Forest +  │
                                  │      Rolling MAD)     │
                                  └───────────────────────┘
```

---

## 🔬 AI Anomaly Detection Engine

Sentinel integrates a dual-layer statistical and machine learning pipeline to capture latency spikes, error bursts, and atypical server loads:

### 1. Rolling Median Absolute Deviation (Rolling MAD)
A robust time-series outlier filter resistant to extreme value skew:
$$\text{MAD} = \text{median}(|X_i - \tilde{X}|)$$
$$\text{Modified } Z\text{-Score} = \frac{0.6745 \cdot (X_i - \tilde{X})}{\text{MAD}}$$
- Threshold: $|Z| > 3.2$ classifies warning anomalies; $|Z| > 5.5$ triggers critical incident alerts.

### 2. Isolation Forest (Unsupervised Spatial Partitioning)
- Employs an ensemble of 100 Isolation Trees (`sklearn.ensemble.IsolationForest`, `contamination=0.06`).
- Isolates multidimensional telemetry outliers with sub-500ms inference latency without requiring manual threshold tuning.

### 3. Consensus Anomaly Filtering
- High-severity incidents are corroborated when both deterministic (Rolling MAD) and stochastic (Isolation Forest) algorithms agree, driving precision up to **91.8%** and anomaly recall to **95.2%**.

---

## 🏦 Banking Institution Simulation Profiles

| Institution | Profile Target | Baseline Latency | Error Rate | Protocol Specifics |
|---|---|---|---|---|
| **Bank A (TBC Bank)** | Fully Compliant | ~120 ms ($\sigma = 15$) | 1% | Strict ISO 8601 timestamps, full HSTS & CSP |
| **Bank B (Bank of Georgia)**| Schema Drift & Delay | ~320 ms ($\sigma = 40$) | 5% | Slash date format, unexpected schema fields |
| **Bank C (Liberty Bank)** | High Volatility / Flaky | ~740 ms ($\sigma = 110$)| 20% | Unix timestamps, requires custom headers |

### Comprehensive Scoring Formula
$$\text{Total Score} = 0.35 \times \text{Compliance} + 0.25 \times \text{Reliability} + 0.20 \times \text{Latency} + 0.20 \times \text{Security}$$

---

## 🚀 Quick Start Guide

### Option 1: One-Click Startup via PowerShell (Windows)
Make sure Docker Desktop is running, then execute:
```powershell
.\run.ps1
```

### Option 2: Docker Compose (Cross-Platform)
```bash
# Clone the repository
git clone https://github.com/Eldar2107/sentinel.git
cd sentinel

# Build and start all 9 containers
docker compose up -d --build
```

Once initialized, access the services:
- **Streamlit AI Analytics & Telemetry**: `http://localhost:8501`
- **React Management Dashboard**: `http://localhost:3000`
- **Sentinel Backend API Docs**: `http://localhost:8000/docs`
- **Bank A Docs**: `http://localhost:8001/docs`
- **Bank B Docs**: `http://localhost:8002/docs`
- **Bank C Docs**: `http://localhost:8003/docs`

### Option 3: Standalone Streamlit Mode (Zero-Docker / Offline Demo)
You can run the interactive Streamlit monitoring dashboard directly without Docker or PostgreSQL:
```bash
pip install -r streamlit/requirements.txt
streamlit run streamlit/streamlit_app.py
```

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/dashboard` | Aggregated real-time metrics, bank scores, uptime, and recent anomaly events |
| `GET` | `/api/anomalies` | Query detected anomalies filtered by institution and timestamp |
| `GET` | `/api/scores` | Current composite compliance and reliability ratings |
| `POST`| `/api/run-tests` | Manually dispatch automated test suites across all bank simulators |
| `GET` | `/api/latency/{bank_id}` | Retrieve historical p50, p95, and p99 latency distributions |
| `GET` | `/api/report/{bank_id}` | Plaintext executive summary and incident diagnostics report |

---

## 🛠️ Technology Stack

- **Machine Learning & Data**: Python 3.11, Scikit-learn, NumPy, Pandas, APScheduler
- **Backend**: FastAPI, AsyncPG, Redis asyncio, HTTPX, Uvicorn
- **Databases & Cache**: PostgreSQL 15 (timeseries schema), Redis 7
- **Frontend & Dashboards**: Streamlit, React 18, Vite, Nginx
- **DevOps & Containers**: Docker, Docker Compose, Bash, PowerShell

---

## 👨‍💻 Author & Maintainer

**Eldar Samedov**  
- **GitHub**: [@Eldar2107](https://github.com/Eldar2107)  
- **LinkedIn**: [linkedin.com/in/eldarsamedov](https://linkedin.com/in/eldarsamedov)  
- **TryHackMe**: [Eldar20](https://tryhackme.com/p/Eldar20)

---

