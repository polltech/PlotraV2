# Plotra — EUDR Agricultural Compliance Platform

Plotra is an end-to-end agricultural traceability and EU Deforestation Regulation (EUDR) compliance platform for East African smallholder coffee cooperatives. It connects farmers, cooperative officers, admins, and EUDR reviewers through a common supply-chain verification workflow backed by geospatial analysis, satellite imagery, and a four-tier audit trail.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Directory Structure](#directory-structure)
- [Prerequisites](#prerequisites)
- [Quick Start (Docker)](#quick-start-docker)
- [Environment Variables](#environment-variables)
- [Running Services Individually](#running-services-individually)
- [API Documentation](#api-documentation)
- [User Roles & Permissions](#user-roles--permissions)
- [EUDR Compliance Workflow](#eudr-compliance-workflow)
- [Satellite Analysis](#satellite-analysis)
- [Mobile App](#mobile-app)
- [Frontend Dashboard](#frontend-dashboard)
- [Database Migrations](#database-migrations)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Plotra enables full farm-to-port coffee traceability required under EU Regulation 2023/1115 (EUDR). Farmers register geo-referenced farm polygons, cooperative officers record deliveries and batches, Plotra admins verify compliance using satellite-derived deforestation data, and EUDR reviewers issue Due Diligence Statements (DDS) for submission to EU TRACES.

The platform is built for offline-first mobile use in rural Kenya, with delta-sync conflict resolution when connectivity is restored.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client Layer                         │
│  Flutter Mobile App   │  HTML5 Dashboard (Nginx)        │
└──────────┬────────────┴──────────────┬──────────────────┘
           │ HTTPS/REST + WebSockets   │
┌──────────▼────────────────────────────▼──────────────────┐
│               FastAPI Backend (Uvicorn)                   │
│  Auth  │  Farmer  │  Coop  │  Admin  │  EUDR  │  Sync    │
└──────────┬──────────────────────────┬─────────────────────┘
           │                          │
┌──────────▼──────────┐   ┌───────────▼──────────────────┐
│  PostgreSQL+PostGIS │   │  Redis  +  Celery Workers    │
│  (spatial data)     │   │  (cache, task queue)         │
└─────────────────────┘   └──────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────┐
│  External Services                                       │
│  Sentinel Hub (satellite)  │  EU TRACES  │  M-Pesa      │
└─────────────────────────────────────────────────────────┘
```

**Four-Tier User Hierarchy**

| Tier | Role | Responsibilities |
|------|------|-----------------|
| 1 | Farmer | Farm registration, GPS polygon capture, document upload |
| 2 | Cooperative Officer | Member verification, delivery & batch recording |
| 3 | Plotra Admin | Satellite analysis, compliance oversight, system config |
| 4 | EUDR Reviewer | Final certification, DDS generation, EU TRACES submission |

---

## Features

### Core Platform
- **Farm & Parcel Registry** — GPS polygon capture with PostGIS validation, parent-child parcel relationships, boundary-overlap detection
- **Supply-Chain Traceability** — Delivery → Batch → Processing Log → Consignment with full audit trails
- **EUDR Compliance Workflow** — 6-stage verification (Draft → Submitted → Coop Approved → Admin Approved → EUDR Submitted → Certified)
- **Due Diligence Statement (DDS)** — Auto-generated DDS with <10 s SLA, EU TRACES integration
- **Offline-First Mobile** — Delta sync with server-side conflict resolution (last-write-wins with field-level merging)
- **Real-Time Notifications** — WebSocket push to dashboard and mobile

### Geospatial & Satellite
- **Sentinel Hub Integration** — NDVI, BSI, NBR indices, true-colour composites
- **Deforestation Detection** — Hansen Global Forest Change baselines, per-parcel forest-cover change
- **Crop Analysis** — XGBoost 32-feature classifier (soil, spectral, climate inputs)
- **Polygon Validation** — Self-intersection checks, minimum area thresholds, SRID 4326 enforcement

### Security & Compliance
- **JWT Authentication** with refresh tokens and configurable expiry
- **OTP Login** via SMS/email for field officers
- **Role-Based Access Control** — granular endpoint-level permissions
- **EUDR Risk Scoring** — weighted deforestation, legal-land-use, and crop-type scores
- **M-Pesa Payment Integration** — incentive disbursement to farmers

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python 3.11, FastAPI, SQLAlchemy (async), Alembic |
| Database | PostgreSQL 15 + PostGIS 3.3 |
| Cache / Queue | Redis 7, Celery |
| Geospatial | GeoAlchemy2, GeoPandas, Shapely, Rasterio, PyProj |
| ML / Satellite | SentinelHub, NumPy, Pandas, XGBoost |
| Frontend | HTML5, JavaScript ES6, Bootstrap 5, Leaflet, ApexCharts |
| Mobile | Flutter 3.3+, Dio, Hive, flutter_map |
| Container | Docker, Docker Compose, Nginx |
| Deployment | Digital Ocean Droplet, optional S3-compatible storage |

---

## Directory Structure

```
plotra/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, lifespan, CORS
│   │   ├── core/
│   │   │   ├── auth.py             # JWT, password hashing, RBAC
│   │   │   ├── config.py           # YAML + env-var config loader
│   │   │   ├── database.py         # Async SQLAlchemy sessions
│   │   │   ├── email.py            # SMTP integration
│   │   │   ├── eudr_risk.py        # EUDR risk scoring engine
│   │   │   └── schema_enforcement.py
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   │   ├── user.py             # User, Cooperative, Member
│   │   │   ├── farm.py             # Farm, LandParcel, ParcelCrop
│   │   │   ├── traceability.py     # Batch, Delivery, Consignment
│   │   │   ├── verification.py     # VerificationRecord workflow
│   │   │   ├── compliance.py       # EUDRCompliance status
│   │   │   ├── satellite.py        # SatelliteObservation
│   │   │   ├── payments.py         # M-Pesa transactions
│   │   │   └── notification.py     # Push & in-app notifications
│   │   ├── api/v2/                 # Route handlers (14 routers, 229+ endpoints)
│   │   │   ├── auth.py
│   │   │   ├── farmer.py
│   │   │   ├── coop.py
│   │   │   ├── admin.py
│   │   │   ├── eudr.py
│   │   │   ├── satellite.py
│   │   │   ├── gis.py
│   │   │   └── sync.py
│   │   └── services/               # Business logic
│   │       ├── eudr_integration.py # DDS generation, EU TRACES
│   │       ├── satellite_analysis.py
│   │       ├── ml_classifier.py
│   │       ├── geometry_validator.py
│   │       └── delta_sync.py
│   ├── Dockerfile
│   └── alembic/                    # Database migrations
├── frontend/
│   └── dashboard/
│       ├── index.html              # Farmer dashboard
│       ├── coop-dashboard.html     # Cooperative officer dashboard
│       ├── admin-dashboard.html    # Admin dashboard
│       ├── admin-batches.html      # Batch management
│       ├── eudr-dashboard.html     # EUDR overview
│       ├── eudr-portal.html        # DDS submission portal
│       ├── js/
│       │   ├── api.js              # Fetch-based API client
│       │   └── gps.js              # GPS/geolocation helpers
│       ├── css/
│       └── Dockerfile
├── app/
│   └── plotra_mobile/              # Flutter application
│       ├── pubspec.yaml
│       └── lib/
│           ├── main.dart
│           ├── screens/
│           ├── services/
│           ├── models/
│           ├── widgets/
│           └── utils/
├── nginx/                          # Nginx reverse-proxy configs
├── docker/                         # Docker build helpers
├── config.yaml                     # Primary application config
├── .env.example                    # Environment variable template
├── docker-compose.yml              # Development stack
├── docker-compose.prod.yml         # Production overrides
├── docker-compose.ssl.yml          # SSL/TLS variant
└── requirements.txt                # Python dependencies (106 packages)
```

---

## Prerequisites

- **Docker** ≥ 24 and **Docker Compose** ≥ 2.20
- **Python** 3.11+ (for local backend development without Docker)
- **Flutter** 3.3+ (for mobile development)
- PostgreSQL client tools (`psql`) for manual DB access

---

## Quick Start (Docker)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/plotra.git
cd plotra

# 2. Copy and edit environment variables
cp .env.example .env
# Edit .env — at minimum set DB password, SECRET_KEY, and SENTINEL_HUB_CLIENT_ID

# 3. Start the full stack (PostgreSQL + PostGIS, Redis, FastAPI, Nginx dashboard)
docker compose up --build

# 4. Run initial database migrations
docker compose exec backend alembic upgrade head

# 5. Create a Plotra Admin user (interactive prompt)
docker compose exec backend python -m app.scripts.create_admin
```

| Service | URL |
|---------|-----|
| API (dev docs) | http://localhost:8000/api/docs |
| Dashboard | http://localhost:80 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

## Environment Variables

Copy `.env.example` to `.env` and set the values below. All variables are namespaced with `PLOTRA_`.

### Required

| Variable | Description |
|----------|-------------|
| `PLOTRA_APP__SECRET_KEY` | 32-byte random secret for JWT signing |
| `PLOTRA_DATABASE__HOST` | PostgreSQL host (default: `db`) |
| `PLOTRA_DATABASE__PORT` | PostgreSQL port (default: `5432`) |
| `PLOTRA_DATABASE__NAME` | Database name |
| `PLOTRA_DATABASE__USER` | Database user |
| `PLOTRA_DATABASE__PASSWORD` | Database password |
| `PLOTRA_REDIS__URL` | Redis URL (default: `redis://redis:6379/0`) |

### Optional — Satellite Analysis

| Variable | Description |
|----------|-------------|
| `PLOTRA_SATELLITE__SENTINEL_HUB_CLIENT_ID` | Sentinel Hub OAuth client ID |
| `PLOTRA_SATELLITE__SENTINEL_HUB_CLIENT_SECRET` | Sentinel Hub OAuth secret |
| `PLOTRA_SATELLITE__SIMULATION_MODE` | `true` to use synthetic data (default: `false`) |

### Optional — Email

| Variable | Description |
|----------|-------------|
| `PLOTRA_EMAIL__SMTP_HOST` | SMTP server hostname |
| `PLOTRA_EMAIL__SMTP_PORT` | SMTP port (default: `587`) |
| `PLOTRA_EMAIL__SMTP_USER` | SMTP username |
| `PLOTRA_EMAIL__SMTP_PASSWORD` | SMTP password |
| `PLOTRA_EMAIL__FROM_ADDRESS` | Sender address |

### Optional — Payments

| Variable | Description |
|----------|-------------|
| `PLOTRA_PAYMENTS__MPESA_CONSUMER_KEY` | Safaricom M-Pesa consumer key |
| `PLOTRA_PAYMENTS__MPESA_CONSUMER_SECRET` | M-Pesa consumer secret |
| `PLOTRA_PAYMENTS__MPESA_SHORTCODE` | M-Pesa business shortcode |

### Optional — Storage

| Variable | Description |
|----------|-------------|
| `PLOTRA_STORAGE__LOCAL_PATH` | Local file-upload directory |
| `PLOTRA_STORAGE__S3_BUCKET` | S3-compatible bucket name |
| `PLOTRA_STORAGE__S3_ENDPOINT` | S3 endpoint URL (for non-AWS providers) |

---

## Running Services Individually

### Backend (FastAPI)

```bash
cd backend
pip install -r ../requirements.txt

# Start development server with auto-reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run tests
pytest app/tests/ -v --cov=app
```

### Celery Worker

```bash
cd backend
celery -A app.celery_app worker --loglevel=info
```

### Frontend Dashboard

The dashboard is plain HTML/JS — serve it with any static file server:

```bash
cd frontend/dashboard
python -m http.server 3000
# Open http://localhost:3000
```

### Mobile App (Flutter)

```bash
cd app/plotra_mobile
flutter pub get
flutter run               # connect an Android device or start an emulator
flutter build apk --release
```

---

## API Documentation

Interactive API documentation is available in development mode:

- **Swagger UI** — `GET /api/docs`
- **ReDoc** — `GET /api/redoc`
- **OpenAPI JSON** — `GET /api/openapi.json`

> In production, `PLOTRA_APP__DEBUG=false` disables the docs endpoints.

### Key Endpoint Groups

| Group | Base Path | Description |
|-------|-----------|-------------|
| Authentication | `/api/v2/auth` | OTP login, JWT token exchange, password management |
| Farmer Portal | `/api/v2/farmer` | Profile, farms, parcels, documents, notifications |
| Cooperative | `/api/v2/coop` | Members, deliveries, batches, processing logs |
| Admin | `/api/v2/admin` | Oversight, satellite triggers, compliance verification |
| EUDR | `/api/v2/eudr` | Parcel verification, DDS generation, TRACES submission |
| Satellite | `/api/v2/satellite` | NDVI maps, deforestation detection, crop analysis |
| GIS | `/api/v2/gis` | Polygon validation, area calculation, boundary checks |
| Sync | `/api/v2/sync` | Mobile delta sync, conflict resolution |

### Authentication

```bash
# Request OTP
POST /api/v2/auth/send-otp
{ "phone_number": "+254712345678" }

# Verify OTP and receive JWT
POST /api/v2/auth/verify-otp
{ "phone_number": "+254712345678", "otp": "123456" }

# All subsequent requests
Authorization: Bearer <access_token>
```

---

## User Roles & Permissions

| Role | Access Level | Key Capabilities |
|------|-------------|-----------------|
| `Farmer` | Own data only | Register farms, upload photos, view compliance status |
| `CooperativeOfficer` | Cooperative scope | Verify members, record deliveries, approve batches |
| `PlotraAdmin` | Platform-wide | Manage all users, trigger satellite analysis, override verification |
| `EUDRReviewer` | Compliance scope | Final certification, DDS issuance, EU TRACES submission |
| `DeliveryAgent` | Delivery scope | Record deliveries, update delivery status |

---

## EUDR Compliance Workflow

```
Farmer registers parcel (GPS polygon)
        │
        ▼
[DRAFT] Farmer submits verification request
        │
        ▼
[SUBMITTED] Cooperative Officer reviews farm data
        │
        ▼
[COOP_APPROVED] Plotra Admin runs satellite analysis
        │  ├─ NDVI computation
        │  ├─ Deforestation risk score (Hansen GFC)
        │  └─ Crop-type classification
        ▼
[ADMIN_APPROVED] EUDR Reviewer certifies
        │
        ▼
[EUDR_SUBMITTED] DDS generated & submitted to EU TRACES
        │
        ▼
[CERTIFIED] Certificate issued to cooperative
```

The risk score combines deforestation probability, legal land-use status, and crop-type confidence into a 0–100 composite. Parcels scoring above the configured threshold are flagged for manual review before certification.

---

## Satellite Analysis

Satellite analysis is triggered per-parcel by Plotra Admin or via the Celery task queue.

**Indices computed:**
- **NDVI** — vegetation health and crop density
- **BSI** — bare soil index for land-use classification
- **NBR** — burn severity and post-fire recovery

**Deforestation detection pipeline:**
1. Fetch Sentinel-2 Level-2A imagery from Sentinel Hub for the parcel bounding box
2. Compute Hansen GFC forest-cover baseline (2000–2020)
3. Calculate annual forest-cover change against the EUDR reference year (2020)
4. Feed spectral + topographic features to the XGBoost 32-feature crop classifier
5. Return per-parcel risk scores, GeoTIFF outputs, and a confidence rating

**Simulation mode** (`PLOTRA_SATELLITE__SIMULATION_MODE=true`) generates synthetic NDVI and risk scores without Sentinel Hub credentials — useful for local development and CI.

---

## Mobile App

The Flutter mobile app targets Android API 21+ and is designed for low-bandwidth, intermittent-connectivity field use.

**Key screens:**
| Screen | Description |
|--------|-------------|
| Splash / Onboarding | App intro, language selection |
| Login | OTP-based phone-number login |
| Dashboard | Farm summary, recent activity, notifications |
| Farm Map | Leaflet-style map with polygon overlays |
| Profile | Farmer details, document uploads |

**Offline sync:**
- Local data stored in Hive (NoSQL) and SQLite
- Delta sync endpoint (`POST /api/v2/sync`) transmits only changed records
- Server-side conflict resolution uses last-write-wins with field-level merge

**Build:**
```bash
flutter build apk --release --target-platform android-arm64
# APK: build/app/outputs/flutter-apk/app-release.apk
```

---

## Frontend Dashboard

The dashboard is a server-rendered HTML5 SPA served by Nginx. It does not require a build step.

**Pages:**
| File | Audience |
|------|----------|
| `index.html` | Farmer — overview, farm list |
| `coop-dashboard.html` | Cooperative Officer |
| `admin-dashboard.html` | Plotra Admin |
| `admin-batches.html` | Batch review queue |
| `eudr-dashboard.html` | Compliance overview |
| `eudr-portal.html` | DDS form and submission |
| `farmer-profile.html` | Farmer profile editor |
| `farming-guide.html` | Best-practice educational content |

The `js/api.js` module handles all backend communication with automatic JWT injection and 401 redirect to login.

---

## Database Migrations

Plotra uses Alembic for schema versioning.

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "describe your change"

# Downgrade one step
alembic downgrade -1

# View migration history
alembic history --verbose
```

The PostGIS extension must be installed in the target database before the first migration:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
```

---

## Deployment

### Digital Ocean (recommended)

See `DIGITAL_OCEAN_DEPLOY.md` for a step-by-step guide covering:
- Droplet sizing recommendations
- Docker Compose production deployment
- SSL certificate provisioning with Let's Encrypt
- Nginx reverse-proxy configuration
- Automated database backups

### Production Docker Compose

```bash
# Production stack with TLS
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.ssl.yml up -d

# Verify services are healthy
docker compose ps
```

### Environment hardening checklist

- [ ] `PLOTRA_APP__DEBUG=false`
- [ ] `PLOTRA_APP__SECRET_KEY` set to a cryptographically random 32-byte value
- [ ] Database not exposed on public network (use Docker internal network)
- [ ] Redis password set and not exposed publicly
- [ ] SMTP credentials use an app-specific password
- [ ] Sentinel Hub credentials scoped to production workspace only
- [ ] S3 bucket policy restricts public read access

---

## Contributing

1. Fork the repository and create a feature branch from `master`
2. Follow PEP 8 for Python and Dart style guidelines for Flutter
3. Write or update tests for any changed behaviour
4. Run the test suite before opening a PR:
   ```bash
   # Backend
   pytest backend/app/tests/ -v --cov=app --cov-fail-under=80

   # Mobile
   flutter test
   ```
5. Open a pull request with a clear description of what changed and why

---

## License

Proprietary. All rights reserved — Plotra Ltd.

For licensing enquiries contact: paulmunywoki086@gmail.com
