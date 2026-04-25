# Kipawa Platform - Digital Ocean Deployment Guide

## Prerequisites

1. Digital Ocean account with:
   - Docker droplets/app platform
   - PostgreSQL managed database (optional)
   - Domain configured with DNS A record pointing to droplet IP

2. Git repository cloned to local machine

## Quick Deploy

### 1. Clone and Setup
```bash
# Clone repository
git clone https://github.com/your-repo/plotra.git
cd plotra

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment
Edit `.env` with your values:

```bash
# REQUIRED: Generate secret key
PLOTRA_APP__SECRET_KEY=$(openssl rand -hex 32)
echo "PLOTRA_APP__SECRET_KEY=$PLOTRA_APP__SECRET_KEY" >> .env

# Set your domain
PLOTRA_APP__FRONTEND_BASE_URL=https://your-domain.com

# CORS - your domain(s)
PLOTRA_CORS__ALLOWED_ORIGINS=https://your-domain.com

# Database password
POSTGRES_PASSWORD=$(openssl rand -base64 24)
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" >> .env
```

### 3. Deploy with Docker Compose
```bash
# Development
docker compose up -d --build

# Production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### 4. Verify Deployment
```bash
# Check services
docker compose ps

# View logs
docker compose logs -f backend

# Test API
curl https://your-domain.com/api/v2/docs

# Test frontend
curl https://your-domain.com/health
```

## Docker Services

| Service | Port | Purpose |
|---------|------|---------|
| `postgres` | 5432 | PostgreSQL + PostGIS database |
| `backend` | 8000 | FastAPI Python application |
| `dashboard` | 8080 | Frontend (nginx) |

## Access Points

| URL | Description |
|-----|-------------|
| `https://your-domain.com` | Frontend Dashboard |
| `https://your-domain.com/api/v2` | API Base |
| `https://your-domain.com/api/v2/docs` | Swagger API Docs |
| `https://your-domain.com/health` | Health Check |

## Environment Variables (Required)

### For .env file:

```bash
# Generate secrets
PLOTRA_APP__SECRET_KEY=<32+ char random string>
POSTGRES_PASSWORD=<secure password>

# Set domain
PLOTRA_APP__FRONTEND_BASE_URL=https://your-domain.com
PLOTRA_CORS__ALLOWED_ORIGINS=https://your-domain.com
```

## API Endpoints Available

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/auth/*` | Various | Authentication |
| `/api/v2/farmer/*` | Various | Farmer APIs |
| `/api/v2/coop/*` | Various | Cooperative APIs |
| `/api/v2/admin/*` | Various | Admin APIs |
| `/api/v2/sync/*` | Various | Delta Sync |
| `/api/v2/gis/*` | POST | Polygon Validation |
| `/api/v2/satellite/*` | Various | Satellite Analysis |
| `/api/v2/eudr/*` | Various | EUDR/DDS |

## Troubleshooting

### Container won't start
```bash
# View logs
docker compose logs backend

# Check env file syntax
cat .env | grep -v "^#" | grep "="

# Recreate containers
docker compose down -v
docker compose up -d --build
```

### Database connection failed
```bash
# Check postgres health
docker compose exec postgres pg_isready -U postgres

# Check connection from backend
docker compose exec backend python -c "from app.core.database import engine; print(engine.url)"
```

### CORS errors
Ensure `PLOTRA_CORS__ALLOWED_ORIGINS` includes your frontend URL exactly:
```bash
PLOTRA_CORS__ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

## Monitoring

### View all logs
```bash
docker compose logs -f
```

### Restart services
```bash
docker compose restart backend
```

### Scale workers
```bash
# In .env or docker-compose.prod.yml
UVICORN_WORKERS=4

# Recreate
docker compose up -d --build backend
```

## SSL/TLS

For production SSL, use:
1. Digital Ocean Load Balancer with free Let's Encrypt
2. Or configure nginx/Caddy for SSL termination

The nginx in dashboard container handles `/api/` proxying automatically.