# Handoff Materials Inventory

Complete catalog of files in the `planning/` directory for the Adaptive Educational Platform project.

## Directory Structure Overview

```
planning/
├── adaptive-ed-platform-dev-handoff/     # Structured development handoff
│   ├── 01-executive-summary/
│   ├── 02-architecture-overview/
│   ├── 03-platform-specs/
│   ├── 04-ux-specs/
│   ├── 05-security/
│   ├── 06-implementation/
│   ├── 07-devops/
│   ├── 08-appendices/
│   └── README.md
└── adaptive-ed-platform-research/        # Research artifacts and evidence
    └── .loom_artifacts/
```

---

## Development Handoff Folder (`adaptive-ed-platform-dev-handoff/`)

### 01-executive-summary/ (2 files)
| File | Type | Purpose |
|------|------|---------|
| `README.md` | Markdown | Executive summary overview, project goals, key stakeholders |
| `developer-quickstart.md` | Markdown | Quickstart guide for developers joining the project |

### 02-architecture-overview/ (2 files)
| File | Type | Purpose |
|------|------|---------|
| `conceptual-architecture.md` | Markdown | High-level system architecture, component relationships |
| `component-specs.md` | Markdown | Detailed specifications for each system component |

### 03-platform-specs/ (7 files)
| File | Type | Purpose |
|------|------|---------|
| `api-contract-outline.md` | Markdown | Overview of API contracts and endpoints |
| `api-contract/openapi.yaml` | YAML | OpenAPI/Swagger specification for REST APIs |
| `content-architecture-spec.md` | Markdown | Content model, structure, and organization |
| `content-metadata-schema.csv` | CSV | Schema definition for content metadata fields |
| `database-schema.sql` | SQL | Database table definitions and relationships |
| `ml-model-configs/model-specification.yaml` | YAML | Machine learning model configuration and parameters |
| `personalization-engine-spec.md` | Markdown | Specifications for personalization/recommendation engine |

### 04-ux-specs/ (2 files)
| File | Type | Purpose |
|------|------|---------|
| `user-flows.md` | Markdown | User journey maps and interaction flows |
| `ux-design-spec.md` | Markdown | User experience design specifications |

### 05-security/ (2 files)
| File | Type | Purpose |
|------|------|---------|
| `security-architecture.md` | Markdown | Security architecture overview, controls, and patterns |
| `threat-model.md` | Markdown | Threat model documentation with attack vectors and mitigations |

### 06-implementation/ (2 files)
| File | Type | Purpose |
|------|------|---------|
| `requirements-backlog.csv` | CSV | Prioritized list of features and requirements |
| `roadmap.md` | Markdown | Implementation timeline and milestone planning |

### 07-devops/ (2 files)
| File | Type | Purpose |
|------|------|---------|
| `ci-cd-config.yml` | YAML | CI/CD pipeline configuration |
| `docker-compose.yml` | YAML | Docker compose for local development environment |

### 08-appendices/ (3 files)
| File | Type | Purpose |
|------|------|---------|
| `research/learning-science-report.md` | Markdown | Research findings on learning science principles |
| `research/standards-alignment-requirements.csv` | CSV | Educational standards alignment requirements |
| `user-personas.md` | Markdown | Target user personas and characteristics |

### Root Level (1 file)
| File | Type | Purpose |
|------|------|---------|
| `README.md` | Markdown | Main handoff documentation entry point |

---

## Research Folder (`adaptive-ed-platform-research/`)

### Root Research Files (20 files)
| File | Type | Purpose |
|------|------|---------|
| `algorithm-comparison-matrix.csv` | CSV | Comparison of algorithms for personalization/recommendation |
| `api-contract-outline.md` | Markdown | Initial API contract research and proposals |
| `competitive-analysis-report.md` | Markdown | Analysis of competitor platforms and features |
| `competitive-feature-matrix.csv` | CSV | Feature comparison matrix against competitors |
| `conceptual-architecture.md` | Markdown | Initial architecture research and decisions |
| `content-architecture-spec.md` | Markdown | Content architecture research and specifications |
| `content-metadata-schema.csv` | CSV | Research on content metadata requirements |
| `evidence-ledger.csv` | CSV | Ledger of evidence-based decisions and sources |
| `implementation-roadmap.md` | Markdown | Research-driven implementation planning |
| `learning-science-report.md` | Markdown | Research on learning science best practices |
| `learning-taxonomy-evidence.csv` | CSV | Evidence mapping for learning taxonomy choices |
| `personalization-engine-spec.md` | Markdown | Research specifications for personalization engine |
| `regulatory-compliance-report.md` | Markdown | Compliance requirements (FERPA, COPPA, etc.) |
| `requirements-backlog.csv` | CSV | Initial requirements research and prioritization |
| `risk-assessment-matrix.csv` | CSV | Risk assessment for technical and business decisions |
| `security-architecture.md` | Markdown | Security architecture research and recommendations |
| `standards-alignment-requirements.csv` | CSV | Educational standards alignment research |
| `success-metrics-framework.md` | Markdown | Framework for measuring platform success |
| `technical-specification.md` | Markdown | Technical requirements and constraints research |
| `user-flows.md` | Markdown | User flow research and preliminary designs |
| `user-personas.md` | Markdown | User persona research and definitions |
| `ux-design-spec.md` | Markdown | UX design research and specifications |
| `validity-scorecard.json` | JSON | Scorecard for validity of research claims |

### .loom_artifacts/ (2 files)
| File | Type | Purpose |
|------|------|---------|
| `fetched/research-regulatory-compliance/af_08350bbbf92e4597.pdf` | PDF | Fetched regulatory compliance research document |
| `fetched/research-regulatory-compliance/manifest.jsonl` | JSONL | Artifact manifest for fetched research |

---

## File Type Summary

| Type | Count | Purpose Category |
|------|-------|------------------|
| Markdown (.md) | 30 | Documentation, specifications, reports |
| CSV (.csv) | 10 | Data schemas, matrices, requirements, evidence |
| YAML (.yml/.yaml) | 4 | Configuration (API, CI/CD, Docker, ML models) |
| SQL (.sql) | 1 | Database schema definitions |
| JSON (.json) | 1 | Scorecard data |
| PDF (.pdf) | 1 | External research artifact |
| JSONL (.jsonl) | 1 | Artifact manifest |

**Total Files: 48**

---

## Key Documents by Purpose

### Entry Points
- `adaptive-ed-platform-dev-handoff/README.md` - Start here for handoff
- `adaptive-ed-platform-dev-handoff/01-executive-summary/README.md` - Executive overview
- `adaptive-ed-platform-dev-handoff/01-executive-summary/developer-quickstart.md` - Developer onboarding

### Architecture & Design
- `02-architecture-overview/conceptual-architecture.md`
- `02-architecture-overview/component-specs.md`
- `03-platform-specs/personalization-engine-spec.md`

### API & Data
- `03-platform-specs/api-contract/openapi.yaml`
- `03-platform-specs/database-schema.sql`
- `03-platform-specs/content-metadata-schema.csv`

### Implementation Planning
- `06-implementation/roadmap.md`
- `06-implementation/requirements-backlog.csv`
- `adaptive-ed-platform-research/implementation-roadmap.md`

### Research Evidence
- `adaptive-ed-platform-research/evidence-ledger.csv`
- `adaptive-ed-platform-research/learning-science-report.md`
- `adaptive-ed-platform-research/competitive-analysis-report.md`
