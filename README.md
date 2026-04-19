# Kipawa Platform - EUDR Compliance & Traceability

A comprehensive platform for EUDR compliance, satellite-verified farm mapping, and traceability from farm to export.

## Architecture

```
kipawa/
├── backend/                          # FastAPI + SQLAlchemy + PostGIS
│   ├── app/
│   │   ├── core/                    # Config, Database, Auth
│   │   ├── models/                  # All SQLAlchemy models
│   │   ├── services/                 # Business logic
│   │   ├── api/                     # FastAPI endpoints
│   │   └── main.py                  # Application entry
│   ├── requirements.txt
│   ├── config.yaml
│   └── Dockerfile
├── frontend/dashboard/               # Bootstrap Dashboard
│   ├── index.html                   # Main HTML
│   ├── css/styles.css               # Custom styles
│   ├── js/
│   │   ├── api.js                   # API client
│   │   └── app.js                   # Main application
│   └── Dockerfile
├── mobile/android_app/              # Android App (starter)
├── docker-compose.yml               # Full orchestration
└── README.md
```

## Features

### Backend
- **FastAPI** with async SQLAlchemy
- **PostgreSQL + PostGIS** for geospatial data
- **Redis** for Celery task queue
- **JWT Authentication** with RBAC
- **UUID Primary Keys** for all models
- **Immutable Audit Logs** with tamper-evident hash chain

### Models
- User (Farmer, Coop Officer, Admin, EUDR Reviewer)
- Farm with parent-child LandParcel relationships
- Delivery, Batch, PracticeLog
- SatelliteObservation with NDVI/biomass
- VerificationRecord with four-tier state machine
- EUDRSubmission, Certificate, DigitalProductPassport
- PaymentEscrow for future M-Pesa integration

### Dashboard (Bootstrap 5)
- Login system
- Role-based dashboards
- Farm/Parcel management
- Delivery tracking
- Verification workflows
- Satellite analysis trigger
- EUDR compliance management
- Chart.js visualizations
- Leaflet maps

## Quick Start

```bash
# Start all services
docker-compose up -d --build

# Access:
# API: http://localhost:8000/docs
# Dashboard: http://localhost:8080
# pgAdmin: http://localhost:5050
# MinIO: http://localhost:9001
```

## API Examples

```bash
# Login
curl -X POST http://localhost:8000/api/v2/auth/token-form \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=farmer1@kipawa.africa&password=password123"

# Get dashboard stats
curl http://localhost:8000/api/v2/admin/dashboard/stats \
  -H "Authorization: Bearer <token>"

# Run satellite analysis
curl -X POST http://localhost:8000/api/v2/admin/satellite/analyze \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"parcel_ids": ["<id>"]}'
```

## User Roles
- **Farmer**: Field data entry, GPS mapping
- **Cooperative Officer**: Member verification
- **Kipawa Admin**: System oversight
- **EUDR Reviewer**: Compliance certification
- **Super Admin**: Full access

## Verification Workflow
Draft → Submitted → CooperativeApproved → AdminApproved → EUDRSubmitted → Certified

## License
MIT
