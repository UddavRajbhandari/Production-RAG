# Phase 8: Production Deployment Strategy

**Project 02 - Production-Grade RAG Pipeline**
**Document Version: 1.0 | Date: May 2026**

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Infrastructure Setup](#2-infrastructure-setup)
3. [API Deployment and Management](#3-api-deployment-and-management)
4. [Frontend Deployment](#4-frontend-deployment)
5. [Backend Deployment](#5-backend-deployment)
6. [CI/CD Pipelines](#6-cicd-pipelines)
7. [Security and Compliance](#7-security-and-compliance)
8. [Monitoring and Support](#8-monitoring-and-support)
9. [Error Handling and Rollbacks](#9-error-handling-and-rollbacks)
10. [Additional Components](#10-additional-components)
11. [Implementation Timeline](#11-implementation-timeline)
12. [Risk Assessment](#12-risk-assessment)
13. [Cost Analysis](#13-cost-analysis)
14. [Appendix](#14-appendix)

---

## 1. Executive Summary

This document outlines the comprehensive deployment strategy for transitioning the Production RAG Pipeline (Phase 8) from a local development environment to a production-grade cloud infrastructure. The deployment leverages zero-cost, managed services to minimize operational overhead while maintaining enterprise-grade reliability and performance.

### Key Objectives

1. Deploy zero-cost infrastructure using managed services (Render, Neon, Qdrant Cloud, Cloudflare)
2. Implement production-ready API with FastAPI framework
3. Build user-facing frontend with Next.js and streaming UX
4. Establish automated CI/CD pipelines with GitHub Actions
5. Configure monitoring, alerting, and observability
6. Ensure security compliance with SSL, API keys, and firewall rules
7. Implement robust error handling and rollback procedures

### Target Outcome

Fully operational production RAG system with:
- API latency p95 ≤ 180s
- RAGAS metrics within defined thresholds
- Zero-cost monthly operational budget

---

## 2. Infrastructure Setup

### 2.1 Cloud Platform Selection

The deployment utilizes a combination of free-tier managed services to achieve zero-cost production operations:

| Component | Service | Tier | Monthly Cost |
|-----------|---------|------|--------------|
| Backend API Hosting | Render | Free | $0 |
| Vector Database | Qdrant Cloud | Free | $0 |
| Relational Database | Neon | Free | $0 |
| CDN / Frontend | Cloudflare Pages | Free | $0 |
| Object Storage | Cloudflare R2 | Free | $0 |

### 2.2 Environment Segmentation

Three-tier environment architecture ensures proper separation of concerns:

| Environment | Purpose | Resources |
|-------------|---------|-----------|
| Development | Local development and testing | localhost:6333, SQLite |
| Staging | Pre-production validation | staging.api.rag.io, Qdrant staging |
| Production | Live production environment | api.rag.io, Qdrant production |

### 2.3 Resource Provisioning

Production resource specifications:

- **Render**: 512MB RAM, 0.5 CPU, 750 hours/month free
- **Qdrant Cloud**: 1GB vector storage, managed scaling
- **Neon**: 0.5GB storage, serverless Postgres with pgvector
- **Cloudflare**: 500 builds/month, 1GB storage, global CDN

---

## 3. API Deployment and Management

### 3.1 API Framework

FastAPI is selected as the API framework for production deployment due to its native support for async operations, automatic OpenAPI documentation, and high performance. The API will be containerized using Docker and deployed to Render's container registry.

### 3.2 API Endpoints

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/api/v1/query` | POST | Submit RAG query | Yes |
| `/api/v1/query/stream` | GET | Streaming response | Yes |
| `/api/v1/ingest` | POST | Add documents | Yes |
| `/api/v1/health` | GET | Health check | No |
| `/api/v1/metrics` | GET | Prometheus metrics | Yes |

### 3.3 API Gateway Configuration

Security and performance features:

- **Rate Limiting**: 60 requests/minute per API key
- **Authentication**: X-API-Key header validation
- **Request Validation**: Pydantic models for all inputs
- **Documentation**: Auto-generated OpenAPI 3.0 at `/docs` and `/redoc`
- **Versioning**: URL-based (`/api/v1/`, `/api/v2/`) with 6-month deprecation overlap

### 3.4 Documentation Strategy

- OpenAPI 3.0 spec auto-generated
- Swagger UI at `/docs`
- ReDoc at `/redoc`
- Postman collection exportable

---

## 4. Frontend Deployment

### 4.1 Frontend Framework

Next.js with App Router will be used for the frontend application, providing a unified codebase for both API and frontend components. The streaming UX requirement from CLAUDE.md will be implemented using Server-Sent Events (SSE).

### 4.2 Hosting Configuration

Cloudflare Pages deployment settings:

- **Build Command**: `npm run build`
- **Output Directory**: `.next`
- **Node Version**: 18.x
- **CDN Caching**: 5-minute cache for static assets

### 4.3 Frontend Pages

| Page | Route | Features |
|------|-------|----------|
| Dashboard | `/` | Query history, metrics display |
| Query Interface | `/query` | Chat interface, streaming responses |
| Admin | `/admin` | Document management, system config |

### 4.4 CDN Configuration

- Static assets: Cloudflare CDN (global edge)
- API calls: Proxied through same domain
- Caching: 5-minute CDN cache for static assets

---

## 5. Backend Deployment

### 5.1 Containerization (Docker)

Docker configuration for the backend services:

- **Base Image**: python:3.10-slim
- **Port Exposure**: 8000 (FastAPI)
- **Dependencies**: requirements.txt installation
- **Command**: `uvicorn src.api.main:app --host 0.0.0.0 --port 8000`



**Dockerfile Location**: `Dockerfile` (root)

### 5.2 Docker Compose (Local Development)

Local development will use docker-compose with the following services:

- **api**: Main FastAPI application
- **qdrant**: Vector database (qdrant/qdrant:latest)
- **redis**: Optional caching layer (redis:7-alpine)

**Location**: `docker-compose.yml` (root)

### 5.3 Database Migrations

Migration strategy for production databases:

- **PostgreSQL**: Alembic for schema migrations
- **Qdrant**: SDK-based collection management
- **Development**: Auto-apply on startup
- **Production**: Blue-green deployment with rollback capability

### 5.4 Kubernetes (Future Scaling)

For future horizontal scaling requirements, Kubernetes manifests will be prepared in the `k8s/` directory:

| File | Purpose |
|------|---------|
| `k8s/deployment.yaml` | API deployment configuration |
| `k8s/service.yaml` | ClusterIP service routing |
| `k8s/ingress.yaml` | External routing configuration |
| `k8s/hpa.yaml` | Horizontal pod autoscaling |
| `k8s/configmap.yaml` | Environment configuration |
| `k8s/secrets.yaml` | API keys (external) |

---

## 6. CI/CD Pipelines

### 6.1 GitHub Actions Workflows

Existing CI workflow will be extended with deployment automation:

| Workflow | Trigger | Environment | Duration Target |
|----------|---------|-------------|----------------|
| ci.yml | push, PR | N/A | < 7 min |
| deploy.yml (staging) | push to main | staging | < 10 min |
| deploy.yml (production) | workflow_dispatch | production | < 15 min |

### 6.2 Pipeline Stages

Deployment pipeline stages and success criteria:

1. **Lint**: ruff check, ruff format, mypy (< 2 min)
2. **Test**: pytest unit + integration tests (< 5 min)
3. **Build**: Docker build and push (< 3 min)
4. **Deploy Staging**: Render deployment (< 2 min)
5. **Integration Test**: Health check and smoke test (< 2 min)
6. **Deploy Production**: Blue-green or rolling deployment (< 5 min)

### 6.3 Rollback Procedures

Automated rollback triggers and procedures:

- **CI Failure**: Auto-stop at any stage
- **Deploy Failure**: Render automatic rollback
- **Runtime Failure**: Git revert and redeploy
- **Database Migration Failure**: Alembic downgrade
- **RAGAS Regression**: Block production deployment

---

## 7. Security and Compliance

### 7.1 SSL/TLS Configuration

Security transport layer configuration:

- Cloudflare Full SSL with custom origin certificate
- HSTS enabled with 6-month max age
- TLS 1.2 minimum, 1.3 preferred

### 7.2 Firewall Configuration

| Service | Inbound Rules | Outbound Rules |
|---------|---------------|----------------|
| API Server | Cloudflare → API only | 80, 443 → external APIs |
| Database | API server only | Internal only |
| Vector Store | API server only | Internal only |

### 7.3 Authentication and Authorization

Security layers for API access:

- **API Key Authentication**: X-API-Key header validation
- **Rate Limiting**: Per-API-key limits (60 req/min)
- **IP Allowlist**: Cloudflare firewall rules for admin endpoints
- **Future**: OAuth2 with JWT refresh tokens

### 7.4 Security Headers

Cloudflare Transform Rules configuration:

```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=()
```

### 7.5 Compliance Considerations

Regulatory and policy compliance measures:

- **Data Privacy**: No PII in logs, GDPR-compliant data handling
- **API Key Rotation**: 90-day rotation policy
- **Audit Trail**: Full request/response logging
- **Data Retention**: 30-day log retention policy

---

## 8. Monitoring and Support

### 8.1 Logging Architecture

| Component | Tool | Retention |
|-----------|------|-----------|
| Application Logs | JSON to stdout | 7 days |
| Access Logs | Cloudflare | 30 days |
| Error Tracking | Sentry (free tier) | 90 days |

### 8.2 Metrics Collection

Key metrics and alerting thresholds:

| Metric | Collection Method | Alert Threshold |
|--------|------------------|------------------|
| API Latency (p95) | Prometheus histogram | > 180s |
| Error Rate | Prometheus counter | > 1% |
| Request Volume | Prometheus counter | > 1000/min |
| RAGAS Scores | Scheduled job | Below threshold |

### 8.3 Alerting Configuration

Alert severity and response time targets:

- **API Down**: Critical severity, < 5 min response
- **High Latency**: Warning severity, < 30 min response
- **RAGAS Regression**: Warning severity, < 1 hour response
- **Error Rate Spike**: Warning severity, < 15 min response

### 8.4 Monitoring Dashboards

Primary monitoring and observability platforms:

- **Grafana (free tier)**: API metrics, RAGAS scores visualization
- **Render Dashboard**: CPU, memory, request metrics
- **Qdrant Dashboard**: Collection stats, query latency
- **Cloudflare Analytics**: CDN performance, security events

### 8.5 Support Protocols

Escalation paths and response times:

- **User-reported bug**: Triage within 24 hours
- **System downtime**: Page on-call within 5 minutes
- **Security incident**: Immediate escalation to emergency response
- **RAGAS regression**: Alert team, investigate before retry

---

## 9. Error Handling and Rollbacks

### 9.1 Error Classification

| Level | Example | Action |
|-------|---------|--------|
| L0 - Recoverable | Timeout, transient error | Retry with exponential backoff |
| L1 - Application | Bad request, validation error | Return 4xx with error message |
| L2 - Service | Database unavailable | Fail gracefully, return cached |
| L3 - Critical | Data corruption | Full rollback to last known good |

### 9.2 Retry Strategy

Exponential backoff retry pattern:

```
Attempt 1 → Immediate
Attempt 2 → 1 second delay
Attempt 3 → 5 second delay
Attempt 4 → 30 second delay
Final → Return error with context
```

### 9.3 Rollback Decision Tree

Automated decision logic for rollback scenarios:

- **Deploy fails?** → Auto-rollback (Render)
- **Runtime error detected?** → Check Grafana → Review changes → Git revert if regression
- **Database migration fails?** → Stop deploy → Alembic downgrade → Rollback code
- **RAGAS regression detected?** → Block production → Alert team → Investigate before retry
- **LLM provider downtime?** → Automatic fallback to alternate provider

### 9.4 Rollback Commands

Emergency rollback commands for different scenarios:

**Code Rollback**:
```bash
git revert HEAD
git push origin main
```

**Database Rollback**:
```bash
alembic downgrade -1
```

**Full Environment Reset**:
```bash
render deploy --rollback
```

---

## 10. Additional Components

### 10.1 Message Queue (Future)

Not required for initial Phase 8 deployment. Consider Redis for future async processing requirements.

### 10.2 Caching Layer

| Cache Type | Implementation | TTL |
|------------|---------------|-----|
| Query Results | Redis (optional) | 1 hour |
| Static Assets | Cloudflare CDN | 1 day |
| API Responses | Varnish (future) | Configurable |

### 10.3 Third-Party Integrations

External service dependencies:

- **OpenRouter**: REST API for LLM inference
- **Qdrant Cloud**: Python SDK for vector search
- **Neon**: psycopg2 for relational storage with pgvector
- **Cloudflare**: DNS + CDN for frontend delivery

### 10.4 External Dependencies

| Dependency | Version | Management |
|------------|---------|------------|
| Python | 3.10 | Runtime |
| LangGraph | Latest | requirements.txt |
| Qdrant Client | Latest | requirements.txt |
| FastAPI | Latest | requirements.txt |

---

## 11. Implementation Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| 8.1 Foundation | Week 1-2 | FastAPI app, core endpoints, Docker config, docker-compose, API integration tests |
| 8.2 Infrastructure | Week 2-3 | Neon DB, Qdrant Cloud cluster, Cloudflare account, staging env, deploy workflow |
| 8.3 Frontend | Week 3-4 | Next.js project, query interface with streaming, admin dashboard, Cloudflare Pages deploy |
| 8.4 Production Readiness | Week 4-5 | Production env, monitoring (Grafana, Sentry), alerts, runbooks, load testing |
| 8.5 Validation | Week 5-6 | Full RAGAS evaluation, latency verification, streaming UX test, UAT |

---

## 12. Risk Assessment

| Risk | Likelihood | Impact | Mitigation | Owner |
|------|------------|--------|------------|-------|
| API latency exceeds target | Medium | High | Optimize retrieval, cache results | Dev Team |
| LLM provider downtime | Medium | High | Implement fallback providers | Dev Team |
| Qdrant Cloud issues | Low | High | Monitor closely, fallback plan | Dev Team |
| Cost overrun | Low | Medium | Stay within free tiers | Project Lead |
| Security breach | Low | High | Use API keys, SSL, monitoring | Dev Team |

---

## 13. Cost Analysis

Monthly operational cost estimate using free-tier services:

| Service | Free Tier Limit | Expected Usage | Monthly Cost |
|---------|-----------------|----------------|--------------|
| Render | 750 hours | ~750 hours | $0 |
| Qdrant Cloud | 1GB | < 100MB | $0 |
| Neon | 0.5GB | < 100MB | $0 |
| Cloudflare Pages | 500 builds/mo | < 50 builds | $0 |
| Cloudflare R2 | 1GB storage | < 100MB | $0 |
| **TOTAL** | | | **$0** |

**Note**: Usage beyond free tier will automatically scale with pay-as-you-go pricing. Estimated breakeven point: ~10x current usage.

---

## 14. Appendix

### 14.1 Critical Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/api/main.py` | Create | FastAPI entry point |
| `src/api/routes/query.py` | Create | Query endpoints |
| `src/api/routes/ingest.py` | Create | Ingestion endpoints |
| `src/api/models.py` | Create | Pydantic schemas |
| `Dockerfile` | Create | Container definition |
| `docker-compose.yml` | Create | Local dev environment |
| `.github/workflows/deploy.yml` | Create | Deployment pipeline |
| `nextjs-app/` | Create | Frontend application |
| `k8s/` | Create | Kubernetes manifests |
| `config/settings.yaml` | Modify | Production settings |
| `.env` | Modify | Production environment |

### 14.2 Verification Strategy

**Pre-Deployment Verification**:
1. All unit tests pass (`pytest tests/unit`)
2. All integration tests pass (`pytest tests/integration`)
3. Ruff + Mypy pass
4. Docker build succeeds locally

**Staging Verification**:
1. API health endpoint returns 200
2. Query endpoint processes request successfully
3. Streaming response works
4. RAGAS metrics within thresholds (sample set)

**Production Verification**:
1. Health check passes
2. Smoke test with golden set queries succeeds
3. RAGAS full evaluation within thresholds
4. Latency within 180s p95
5. Monitoring shows healthy metrics
6. Frontend loads and functions correctly

---

## Run the API

Option 1: Direct Python
cd D:\Production RAG

`python -m uvicorn src.api.main:app --reload --port 8000`

Option 2: With Docker
cd D:\Production RAG
`docker-compose up --build`

Access Swagger UI

Once running, open your browser to:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

Test the API

1. Health Check
curl http://localhost:8000/api/v1/health

2. Test Query (via Swagger UI)
- Go to /docs
- Click on POST /api/v1/query
- Click "Try it out"
- Enter: {"query": "What is the project about?", "stream": false,
"include_sources": true}
- Click "Execute"
