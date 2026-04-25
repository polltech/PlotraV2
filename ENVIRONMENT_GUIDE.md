# Kipawa Platform - Environment Variables Guide

## Complete Environment Variables List

### Application
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_APP__NAME` | Kipawa Platform | Application name | Yes |
| `PLOTRA_APP__VERSION` | 1.0.0 | Version | Yes |
| `PLOTRA_APP__DEBUG` | false | Debug mode | Yes |
| `PLOTRA_APP__ENV` | development | Environment | Yes |
| `PLOTRA_APP__SECRET_KEY` | - | JWT secret key (min 32 chars) | **YES** |
| `PLOTRA_APP__ALGORITHM` | HS256 | JWT algorithm | Yes |
| `PLOTRA_APP__ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | Token expiry | Yes |
| `PLOTRA_APP__FRONTEND_BASE_URL` | http://localhost:8080 | Frontend URL | Yes |

### Database
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_DATABASE__HOST` | localhost | PostgreSQL host | **YES** |
| `PLOTRA_DATABASE__PORT` | 5432 | PostgreSQL port | Yes |
| `PLOTRA_DATABASE__USERNAME` | postgres | Database user | **YES** |
| `PLOTRA_DATABASE__PASSWORD` | - | Database password | **YES** |
| `PLOTRA_DATABASE__NAME` | plotra_db | Database name | **YES** |
| `PLOTRA_DATABASE__POOL_SIZE` | 10 | Connection pool size | No |
| `PLOTRA_DATABASE__MAX_OVERFLOW` | 20 | Max overflow connections | No |
| `PLOTRA_DATABASE__ASYNC_MODE` | true | Use async driver | Yes |

### Redis
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_REDIS__HOST` | localhost | Redis host | No |
| `PLOTRA_REDIS__PORT` | 6379 | Redis port | No |
| `PLOTRA_REDIS__DB` | 0 | Redis database | No |

### PostGIS / Geospatial
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_POSTGIS__ENABLED` | true | Enable PostGIS | Yes |
| `PLOTRA_POSTGIS__SRID` | 4326 | Spatial reference ID | Yes |
| `PLOTRA_GEOSPATIAL__GPS_ACCURACY_THRESHOLD_METERS` | 10 | Max GPS accuracy | Yes |
| `PLOTRA_GEOSPATIAL__MIN_POLYGON_AREA_HECTARES` | 0.1 | Min parcel area | Yes |
| `PLOTRA_GEOSPATIAL__MAX_FARM_POLYGONS_PER_FARMER` | 10 | Max parcels per farmer | Yes |
| `PLOTRA_GEOSPATIAL__PARENT_CHILD_VALIDATION` | true | Enable parent-child validation | Yes |
| `PLOTRA_GEOSPATIAL__BOUNDARY_OVERLAP_TOLERANCE` | 0.01 | Overlap tolerance | Yes |

### Satellite / GEE
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_SATELLITE__PROVIDER` | sentinel_hub | Satellite provider | Yes |
| `PLOTRA_SATELLITE__API_KEY` | - | API key | **YES** |
| `PLOTRA_SATELLITE__BASE_URL` | https://services.sentinel-hub.com | API base URL | Yes |
| `PLOTRA_SATELLITE__SIMULATION_MODE` | true | Use simulation mode | Yes |
| `PLOTRA_SATELLITE__NDVI_THRESHOLD` | 0.65 | NDVI threshold | Yes |
| `PLOTRA_SATELLITE__DEFORESTATION_BASELINE_YEAR` | 2014 | Baseline year | Yes |
| `PLOTRA_SATELLITE__BIOMASS_THRESHOLD` | 100.0 | Biomass threshold | Yes |

### EUDR Compliance
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_EUDR__COMPLIANCE_STATUS` | Under Review | Default status | Yes |
| `PLOTRA_EUDR__CERTIFICATE_VALIDITY_DAYS` | 365 | Certificate validity | Yes |
| `PLOTRA_EUDR__DDS_VERSION` | 1.0 | DDS version | Yes |
| `PLOTRA_EUDR__PORTAL_URL` | - | EUDR portal URL | **YES** |

### Email
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_EMAIL__SMTP_SERVER` | - | SMTP server | **YES** |
| `PLOTRA_EMAIL__SMTP_PORT` | 587 | SMTP port | Yes |
| `PLOTRA_EMAIL__SMTP_USERNAME` | - | SMTP username | **YES** |
| `PLOTRA_EMAIL__SMTP_PASSWORD` | - | SMTP password | **YES** |
| `PLOTRA_EMAIL__FROM_EMAIL` | - | From email address | **YES** |
| `PLOTRA_EMAIL__FROM_NAME` | Plotra Platform | From name | Yes |
| `PLOTRA_EMAIL__USE_TLS` | true | Use TLS | Yes |

### Authentication
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_AUTH__MAX_LOGIN_ATTEMPTS` | 5 | Max login attempts | Yes |
| `PLOTRA_AUTH__LOCKOUT_DURATION_MINUTES` | 15 | Lockout duration | Yes |
| `PLOTRA_AUTH__PASSWORD_RESET_TOKEN_EXPIRY_HOURS` | 24 | Reset token expiry | Yes |

### CORS
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_CORS__ALLOWED_ORIGINS` | - | Allowed origins (comma-separated) | **YES** |

### Storage / S3
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_STORAGE__DOCUMENTS_PATH` | ./uploads/documents | Documents path | Yes |
| `PLOTRA_STORAGE__CERTIFICATES_PATH` | ./uploads/certificates | Certificates path | Yes |
| `PLOTRA_STORAGE__PHOTOS_PATH` | ./uploads/photos | Photos path | Yes |
| `PLOTRA_STORAGE__S3_BUCKET` | - | S3 bucket name | No |
| `PLOTRA_STORAGE__S3_ENDPOINT` | - | S3 endpoint | No |
| `PLOTRA_STORAGE__S3_ACCESS_KEY` | - | AWS access key | No |
| `PLOTRA_STORAGE__S3_SECRET_KEY` | - | AWS secret key | No |
| `PLOTRA_STORAGE__S3_REGION` | af-south-1 | AWS region | No |

### Celery / Workers
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_CELERY__BROKER_URL` | redis://localhost:6379/1 | Celery broker | No |
| `PLOTRA_CELERY__RESULT_BACKEND` | redis://localhost:6379/2 | Result backend | No |

### Payments
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_PAYMENTS__ENABLED` | false | Enable payments | Yes |
| `PLOTRA_PAYMENTS__MPESA_CONSUMER_KEY` | - | M-Pesa consumer key | No |
| `PLOTRA_PAYMENTS__MPESA_CONSUMER_SECRET` | - | M-Pesa consumer secret | No |
| `PLOTRA_PAYMENTS__MPESA_SHORTCODE` | - | M-Pesa shortcode | No |
| `PLOTRA_PAYMENTS__ESCROW_ENABLED` | true | Enable escrow | Yes |

### Verification
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_VERIFICATION__REQUIRE_ALL_FIELDS` | false | Require all fields | Yes |
| `PLOTRA_VERIFICATION__AUTO_SUBMIT_EUDR` | false | Auto-submit to EUDR | Yes |
| `PLOTRA_VERIFICATION__ALERT_THRESHOLD_DAYS` | 30 | Alert threshold | Yes |

### Logging
| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `PLOTRA_LOGGING__LEVEL` | INFO | Log level | Yes |
| `PLOTRA_LOGGING__FORMAT` | - | Log format | Yes |
| `PLOTRA_LOGGING__FILE` | logs/plotra.log | Log file path | Yes |
| `PLOTRA_LOGGING__AUDIT_ENABLED` | true | Enable audit logging | Yes |

---

## Quick Setup

### 1. Development
```bash
cp .env.example .env
# Edit .env with development values
```

### 2. Production
```bash
cp .env.example .env.production
# Edit .env.production with production values
# Use: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. Docker
```bash
cp .env.example .env
docker-compose up -d
```

---

## Frontend Configuration (config.js)

| Setting | Default | Description |
|---------|---------|-------------|
| `api.baseUrl` | /api/v2 | API endpoint |
| `api.timeout` | 10000 | Request timeout (ms) |
| `gps.toleranceMeters` | 3.0 | GPS tolerance |
| `gps.minAreaHectares` | 0.1 | Min parcel area |
| `satellite.simulationMode` | true | Use simulation |
| `satellite.confidenceThreshold` | 0.90 | Min confidence |
| `eudr.conflictSlaHours` | 48 | Conflict SLA |
| `sync.successThreshold` | 99.5 | Sync success rate |

---

## Required vs Optional

### MUST be set before deployment:
- `PLOTRA_APP__SECRET_KEY` (generate with: `openssl rand -hex 32`)
- `PLOTRA_DATABASE__*` (database credentials)
- `PLOTRA_SATELLITE__API_KEY` (for live satellite)
- `PLOTRA_EMAIL__*` (for emails)
- `PLOTRA_CORS__ALLOWED_ORIGINS` (your domain)
- `PLOTRA_EUDR__PORTAL_URL` (EUDR portal)

### Can use defaults in development:
- Redis, Celery, Storage (can be added later)
- Payments (disabled by default)
- Logging (has sensible defaults)