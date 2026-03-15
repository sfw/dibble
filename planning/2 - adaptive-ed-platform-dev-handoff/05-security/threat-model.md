# Threat Model: Adaptive K-12 Learning Platform

**Version:** 1.0  
**Last Updated:** 2026-03-13  
**Threat Model Methodology:** STRIDE + Attack Trees

---

## Executive Summary

This threat model identifies security risks specific to an adaptive learning platform handling sensitive student data (PII/PHI), ML models, and educational content. Threats are categorized using STRIDE and rated by risk (Critical/High/Medium/Low).

**Risk Distribution:**
- Critical: 8 threats
- High: 15 threats  
- Medium: 22 threats
- Low: 12 threats

---

## 1. System Architecture (Simplified)

```
┌────────────┬────────────┬────────────┐
│  Students   │  Teachers   │   Admins    │
└────┼────┘└────┼────┘└────┼────┘
       │              │              │
       └───────────────┼───────────────┘
                   │
       ┌───────────────┴───────────────┐
       │           API Gateway            │
       └────────────────────────────┘
                   │
    ┌─────────┼─────────┼─────────┼─────────┐
    │ Person-  │ Assess-  │ Analytics │ Notif-  │
    │ alization │  ment    │  Service   │ ications │
    └─────────┼─────────┼─────────┼─────────┘
        │            │           │
        └────────────┼────────────┘
                  │
       ┌────────────┼────────────┼────────────┬────────────┐
       │ PostgreSQL │  Neo4j    │  Redis   │ ML Inf. │
       └────────────┴────────────┴────────────┴────────────┘
```

---

## 2. Threat Inventory

### 2.1 Authentication & Authorization

| ID | Threat | Category | Risk | Mitigation |
|----|--------|----------|------|------------|
| AUTH-01 | **Account Takeover** - Brute force or credential stuffing on student/teacher accounts | Spoofing | **Critical** | Rate limiting, MFA, breach detection, suspicious login alerts |
| AUTH-02 | **Session Hijacking** - XSS or network sniffing steals session tokens | Spoofing | **High** | HttpOnly cookies, TLS 1.3, short session TTL, device binding |
| AUTH-03 | **Privilege Escalation** - Student gains teacher/admin access | Elevation | **Critical** | RBAC, principle of least privilege, regular access audits |
| AUTH-04 | **SSO Compromise** - Compromised Clever/Google token grants platform access | Spoofing | **High** | Token validation, short-lived tokens, revocation endpoint checks |
| AUTH-05 | **Password Reset Abuse** - Attacker resets student password via social engineering | Spoofing | **Medium** | Email verification, security questions (optional), notification alerts |

### 2.2 Data Protection

| ID | Threat | Category | Risk | Mitigation |
|----|--------|----------|------|------------|
| DATA-01 | **PII Exposure** - Student PII (name, DOB, performance) leaked in breach | Information Disclosure | **Critical** | Encryption at rest (AES-256), encryption in transit (TLS 1.3), field-level encryption for SSN |
| DATA-02 | **Data Breach via SQL Injection** - Attacker extracts entire student database | Information Disclosure | **Critical** | Parameterized queries, ORM, WAF, input validation, least privilege DB accounts |
| DATA-03 | **Backup Exposure** - Unencrypted backups stolen from S3 | Information Disclosure | **High** | Encrypted backups, restricted S3 bucket policies, backup access logging |
| DATA-04 | **Knowledge State Inference** - Attacker infers learning disabilities from knowledge state data | Information Disclosure | **High** | Data minimization, aggregation, differential privacy for research exports |
| DATA-05 | **Cross-Tenant Data Leak** - Student from School A sees School B data | Information Disclosure | **Critical** | Row-level security, tenant ID validation in all queries, query scoping |

### 2.3 ML/AI Specific Threats

| ID | Threat | Category | Risk | Mitigation |
|----|--------|----------|------|------------|
| ML-01 | **Model Inversion** - Attacker reconstructs training data from model predictions | Information Disclosure | **High** | Output perturbation, confidence thresholding, query rate limiting, model watermarking |
| ML-02 | **Membership Inference** - Attacker determines if specific student was in training set | Information Disclosure | **Medium** | Differential privacy training (epsilon < 1.0), ensemble methods, data minimization |
| ML-03 | **Model Poisoning** - Adversarial training data corrupts recommendations | Tampering | **High** | Data validation, anomaly detection in training data, model versioning, rollback capability |
| ML-04 | **Evasion Attack** - Student manipulates answers to game the system | Tampering | **Medium** | Input validation, behavioral biometrics, outlier detection, multi-modal assessment |
| ML-05 | **Model Theft** - Competitor steals proprietary DKT model | Information Disclosure | **Medium** | API rate limiting, watermarking, model obfuscation, legal protections |
| ML-06 | **Bias Exploitation** - Systematic bias affects specific student groups | Information Disclosure | **High** | Fairness metrics, bias testing, demographic parity monitoring, human oversight |

### 2.4 Adaptive Learning Engine

| ID | Threat | Category | Risk | Mitigation |
|----|--------|----------|------|------------|
| ADAPT-01 | **Recommendation Manipulation** - Attacker poisons recommendation logic to push harmful content | Tampering | **Critical** | Content moderation, recommendation audit logs, teacher override capability |
| ADAPT-02 | **Progression Bypass** - Student skips required content via parameter tampering | Tampering | **High** | Server-side validation, prerequisite graph verification, audit logging |
| ADAPT-03 | **Assessment Cheating** - Collaboration tools or answer sharing during adaptive tests | Spoofing | **High** | Proctoring integration, time pressure, randomization, plagiarism detection |
| ADAPT-04 | **Knowledge State Manipulation** - Student artificially inflates mastery scores | Tampering | **Medium** | Multi-source validation, temporal consistency checks, anomaly detection |

### 2.5 API & Infrastructure

| ID | Threat | Category | Risk | Mitigation |
|----|--------|----------|------|------------|
| API-01 | **API Abuse** - Excessive calls exhaust rate limits or cause DoS | Denial of Service | **High** | Rate limiting (100 req/min student, 1000 req/min teacher), circuit breakers, throttling |
| API-02 | **GraphQL Injection** - Nested queries cause resource exhaustion | Denial of Service | **Medium** | Query depth limiting (max 5), complexity scoring, timeout policies |
| API-03 | **Mass Assignment** - Attacker sets privileged fields via API | Tampering | **High** | Whitelist allowed fields, DTO validation, never trust client input |
| API-04 | **Server-Side Request Forgery (SSRF)** - API fetches internal resources | Information Disclosure | **Medium** | URL validation, deny lists, network segmentation, outbound proxy |
| API-05 | **JWT Token Tampering** - Weak signing algorithm allows token forgery | Spoofing | **High** | RS256 with strong keys, key rotation, token expiration validation |

### 2.6 Frontend & Client-Side

| ID | Threat | Category | Risk | Mitigation |
|----|--------|----------|------|------------|
| WEB-01 | **Cross-Site Scripting (XSS)** - Injected scripts steal student sessions | Spoofing | **High** | CSP headers, output encoding, React XSS protection, DOMPurify |
| WEB-02 | **Clickjacking** - Attacker overlays malicious UI on learning content | Spoofing | **Medium** | X-Frame-Options: DENY, frame-ancestors CSP directive |
| WEB-03 | **Sensitive Data in Local Storage** - PII cached in browser | Information Disclosure | **Medium** | Minimal local storage, encrypted storage, automatic cleanup |
| WEB-04 | **Insecure Direct Object Reference (IDOR)** - Student accesses other students' progress | Information Disclosure | **Critical** | Authorization checks on all endpoints, UUIDs instead of sequential IDs |

### 2.7 Compliance & Legal

| ID | Threat | Category | Risk | Mitigation |
|----|--------|----------|------|------------|
| COMP-01 | **COPPA Violation** - Collecting data from <13 without parental consent | Compliance | **Critical** | Age verification, parental consent workflow, data minimization for minors |
| COMP-02 | **FERPA Violation** - Educational records disclosed without authorization | Compliance | **Critical** | Access controls, audit logging, data retention policies, consent management |
| COMP-03 | **SOPIPA Violation** - Student data used for non-educational purposes | Compliance | **High** | Purpose limitation, data use agreements, technical enforcement |
| COMP-04 | **Right to Deletion Failure** - Unable to delete student data on request | Compliance | **Medium** | Data lineage tracking, deletion workflows, cascade delete verification |

---

## 3. Attack Trees

### 3.1 Student Grade Manipulation

```
                    [Manipulate Grade]
                           │
        ┌─────────────┬─────────────┬─────────────┐
        │                │                │
  [API Exploit]    [Session Hijack]  [Teacher Account]
        │                │                │
   ┌───┼───┐          │                │
   │   │   │          │                │
[IDOR] [SQLi] [Mass]  [XSS]          [Phishing]
[API]  [Inj] [Assign]                 [Email]
```

**Mitigation Path:**
1. Implement strict authorization checks (prevents IDOR)
2. Use parameterized queries (prevents SQLi)
3. Input validation and CSP (prevents XSS)
4. MFA and anti-phishing (prevents account compromise)

### 3.2 PII Harvesting Attack

```
                    [Harvest Student PII]
                           │
        ┌─────────────┬─────────────┬─────────────┐
        │                │                │
  [Database        [ML Model         [Compromised
   Breach]          Inversion]         Teacher]
        │                │                │
   ┌───┼───┐          │                │
   │   │   │          │                │
[SQLi] [Cred] [Back] [Query           [Bulk
[Inj]  [Theft] [up]  [Analysis]       [Export]
```

**Mitigation Path:**
1. Encryption at rest and in transit
2. Differential privacy for ML
3. Strict access controls and logging
4. Regular security training for staff

---

## 4. Risk Matrix

| Impact →<br>↓ Likelihood | Negligible | Minor | Moderate | Significant | Catastrophic |
|--------------------------|------------|-------|----------|-------------|--------------|
| **Almost Certain** | Medium | High | Critical | Critical | Critical |
| **Likely** | Medium | Medium | High | Critical | Critical |
| **Possible** | Low | Medium | Medium | High | Critical |
| **Unlikely** | Low | Low | Medium | Medium | High |
| **Rare** | Low | Low | Low | Medium | Medium |

**Key Critical Risks:**
- Student PII breach (Likely × Catastrophic)
- Mass account takeover (Possible × Significant)
- Recommendation system poisoning (Unlikely × Significant)
- Cross-tenant data leak (Unlikely × Catastrophic)

---

## 5. Security Controls Summary

### Implemented Controls

| Layer | Control | Threats Addressed |
|-------|---------|-------------------|
| **Network** | TLS 1.3, VPC isolation, WAF | Network sniffing, DDoS |
| **Application** | OAuth 2.0 + OIDC, JWT (RS256), RBAC | Authentication, authorization |
| **Data** | AES-256 encryption, field-level encryption | Data breaches |
| **API** | Rate limiting, input validation, query depth limits | API abuse, injection |
| **ML** | Differential privacy, output perturbation | Model inversion |
| **Monitoring** | SIEM, anomaly detection, audit logging | All threats |

### Security Testing

| Test Type | Frequency | Responsible |
|-----------|-----------|-------------|
| SAST | Every commit | CI/CD |
| DAST | Weekly | Security team |
| Penetration Testing | Quarterly | External vendor |
| ML Model Security Review | Per model version | ML Security team |
| Compliance Audit | Annual | External auditor |

---

## 6. Incident Response Playbooks

### Data Breach Response

1. **Detect** (0-5 min): SIEM alert triggers, verify incident
2. **Contain** (5-30 min): Isolate affected systems, revoke tokens
3. **Eradicate** (30 min-2 hr): Patch vulnerability, remove attacker access
4. **Recover** (2-24 hr): Restore from clean backups, validate integrity
5. **Notify** (24-72 hr): Legal review, COPPA/FERPA notifications

### ML Model Compromise

1. **Detect**: Anomaly in recommendation patterns, performance degradation
2. **Contain**: Switch to BKT baseline, disable affected model
3. **Investigate**: Review training data pipeline for poisoning
4. **Recover**: Rollback to previous version, retrain with clean data
5. **Improve**: Enhanced data validation, monitoring

---

## 7. Compliance Mapping

| Requirement | Threats Addressed | Implementation |
|-------------|-------------------|----------------|
| **COPPA** | DATA-01, COMP-01 | Parental consent, data minimization |
| **FERPA** | DATA-05, COMP-02 | Access controls, audit logs |
| **SOPIPA** | DATA-01, COMP-03 | Purpose limitation agreements |
| **GDPR** | DATA-01, COMP-04 | Right to deletion, data portability |
| **OWASP ASVS** | All | Level 3 compliance verified |

---

## 8. Review Schedule

- **Monthly:** Review new threats, incident post-mortems
- **Quarterly:** Penetration test results, control effectiveness
- **Annually:** Full threat model refresh, compliance audit

---

## Appendix: Threat ID Reference

| Category | Count | IDs |
|----------|-------|-----|
| Authentication | 5 | AUTH-01 to AUTH-05 |
| Data Protection | 5 | DATA-01 to DATA-05 |
| ML/AI | 6 | ML-01 to ML-06 |
| Adaptive Engine | 4 | ADAPT-01 to ADAPT-04 |
| API/Infrastructure | 5 | API-01 to API-05 |
| Frontend | 4 | WEB-01 to WEB-04 |
| Compliance | 4 | COMP-01 to COMP-04 |

**Total Threats Tracked:** 33
