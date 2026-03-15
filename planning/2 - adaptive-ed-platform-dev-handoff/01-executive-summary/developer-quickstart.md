# Developer Quickstart Guide

Get the Adaptive K-12 Learning Platform running locally in under 30 minutes.

---

## Prerequisites

- **Docker** 24.0+ with Docker Compose
- **Node.js** 20.x (for frontend development)
- **Python** 3.11+ (for backend development)
- **Git** 2.40+

Optional but recommended:
- **kubectl** (for Kubernetes deployment)
- **Helm** 3.x (for chart management)
- **NVIDIA Docker** runtime (for ML development)

---

## Quick Setup (5 minutes)

### 1. Start Infrastructure

```bash
cd 07-devops/
docker-compose up -d

# Verify all services are healthy
./scripts/health-check.sh
```

Services started:
- API Gateway (http://localhost:8080)
- PostgreSQL (localhost:5432)
- Neo4j (http://localhost:7474)
- Redis (localhost:6379)
- Kafka (localhost:9092)
- Grafana (http://localhost:3001)

### 2. Initialize Database

```bash
# Run schema migrations
psql -h localhost -U postgres \
  -f ../03-platform-specs/database-schema.sql

# Load seed data
./scripts/seed-data.sh
```

### 3. Start Development Servers

**Backend:**
```bash
cd backend/api-gateway
npm install
npm run dev  # Runs on http://localhost:8080
```

**Frontend:**
```bash
cd frontend/web
npm install
npm run dev  # Runs on http://localhost:3000
```

**ML Inference (optional):**
```bash
# Requires NVIDIA GPU
docker-compose --profile ml up -d triton
```

---

## Development Workflows

### Backend Development

```bash
# API Gateway
cd backend/api-gateway
npm run dev          # Hot reload dev server
npm run test:unit    # Run unit tests
npm run test:e2e     # Run integration tests

# Personalization Engine
cd backend/personalization-engine
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m pytest
```

### Frontend Development

```bash
cd frontend/web

# Development server
npm run dev

# Type checking
npm run type-check

# Linting
npm run lint

# Testing
npm run test:unit
npm run test:e2e

# Production build
npm run build
```

### ML Model Development

```bash
cd ml/training

# Install dependencies
pip install -r requirements.txt

# Train DKT model
python train_dkt.py \
  --data-path data/student_interactions.csv \
  --config configs/dkt_default.yaml \
  --output models/dkt_v2.pt

# Export to ONNX for inference
python export_onnx.py \
  --model models/dkt_v2.pt \
  --output models/dkt_v2.onnx
```

---

## Common Tasks

### Reset Local Environment

```bash
cd 07-devops/
docker-compose down -v  # Remove volumes
docker-compose up -d     # Fresh start
```

### Run Full Test Suite

```bash
# Unit tests
./scripts/test-unit.sh

# Integration tests
./scripts/test-integration.sh

# E2E tests
./scripts/test-e2e.sh

# Performance tests
./scripts/test-performance.sh
```

### Generate API Client

```bash
# TypeScript client
openapi-generator-cli generate \
  -i 03-platform-specs/api-contract/openapi.yaml \
  -g typescript-fetch \
  -o frontend/web/src/api/generated

# Python client
openapi-generator-cli generate \
  -i 03-platform-specs/api-contract/openapi.yaml \
  -g python \
  -o backend/clients/python
```

---

## Debugging

### View Service Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api-gateway

# Last 100 lines
docker-compose logs --tail=100 api-gateway
```

### Database Access

```bash
# PostgreSQL
docker-compose exec postgres psql -U postgres -d adaptive_platform

# Neo4j Browser
open http://localhost:7474  # Login: neo4j/password

# Redis
redis-cli -h localhost
```

### API Testing

```bash
# Health check
curl http://localhost:8080/health

# Authenticate
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password"}'

# Get recommendations (authenticated)
curl http://localhost:8080/v1/recommendations \
  -H "Authorization: Bearer $TOKEN"
```

---

## Troubleshooting

### Port Conflicts

If ports are already in use, modify `docker-compose.yml`:

```yaml
services:
  postgres:
    ports:
      - "5433:5432"  # Use 5433 instead of 5432
```

### Out of Memory

Increase Docker memory limit to 8GB minimum.

### Database Connection Issues

```bash
# Reset database
docker-compose down -v
docker volume rm adaptive-platform_postgres_data
docker-compose up -d postgres
```

### ML Model Not Loading

```bash
# Check model directory exists
ls -la ml-models/

# Verify Triton status
curl http://localhost:8000/v2/health/ready
```

---

## VS Code Setup

Recommended extensions:
- ESLint
- Prettier
- Python
- Pylance
- Docker
- REST Client
- Thunder Client

Workspace settings (`.vscode/settings.json`):
```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true
}
```

---

## Git Workflow

```bash
# Create feature branch
git checkout -b feature/dkt-model-update

# Make changes, commit
git add .
git commit -m "feat: improve DKT prediction accuracy"

# Push and create PR
git push origin feature/dkt-model-update
# Create PR via GitHub/GitLab

# After merge, update local
git checkout main
git pull origin main
```

---

## Resources

| Resource | URL | Description |
|----------|-----|-------------|
| API Docs | http://localhost:8080/docs | OpenAPI/Swagger UI |
| Grafana | http://localhost:3001 | Monitoring dashboards |
| Jaeger | http://localhost:16686 | Distributed tracing |
| Neo4j Browser | http://localhost:7474 | Graph visualization |
| MailHog | http://localhost:8025 | Email testing |

---

## Next Steps

1. **Read the Architecture:** `../02-architecture-overview/conceptual-architecture.md`
2. **Study the API:** `../03-platform-specs/api-contract/openapi.yaml`
3. **Understand Security:** `../05-security/threat-model.md`
4. **Review Roadmap:** `../06-implementation/roadmap.md`

---

## Support

- **Slack:** #dev-support
- **Issues:** GitHub Issues
- **Office Hours:** Tuesdays 2-3pm PT
- **Email:** dev-team@platform.edu

---

## Quick Reference Commands

```bash
# Full stack restart
docker-compose down -v && docker-compose up -d

# Rebuild with no cache
docker-compose build --no-cache

# Scale services
docker-compose up -d --scale api-gateway=3

# Resource usage
docker stats

# Clean up everything
docker system prune -a -volumes
```

**You're now ready to develop! 🚀**
