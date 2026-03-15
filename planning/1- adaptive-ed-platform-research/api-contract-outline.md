---
author: Educational Technology Research Team
classification: API Specification
date: '2026-03-13'
version: '1.0'
---

# API Contract Outline: Adaptive K-12 Learning Platform

## Executive Summary

This document defines the API contracts for the adaptive K-12 learning platform, specifying endpoints, request/response formats, authentication requirements, and error handling for core services. The API follows a hybrid REST/GraphQL approach with REST for simple CRUD operations and GraphQL for complex, nested data queries.

**Key Principles:**
1. **Semantic Versioning**: All APIs versioned at URL level (/api/v1/)
2. **Backward Compatibility**: Breaking changes only in major versions
3. **Idempotency**: Safe retry semantics for network resilience
4. **Standards Compliance**: LTI 1.3, OneRoster, xAPI for educational interoperability

## Authentication and Authorization

## 2.1 Authentication Methods

### JWT Bearer Token (Primary)
```http
GET /api/v1/students/me
Authorization: Bearer <access_token>
```

**Token Lifecycle:**
- Access Token: 15 minutes
- Refresh Token: 7 days (rotate on use)
- Session binding: Device fingerprint validation

### API Key (Service-to-Service)
```http
GET /api/v1/internal/analytics
X-API-Key: <service_api_key>
X-API-Secret: <hmac_signature>
```

### OAuth 2.0 / OIDC (Third-Party)
- Authorization Code flow for web apps
- PKCE for mobile apps
- Scope restrictions: `progress:read`, `content:write`, `admin:full`

## 2.2 Authorization Scopes

| Scope | Description | Endpoints |
|-------|-------------|-----------|
| `student:read` | Access own profile and progress | /students/me/* |
| `student:write` | Update preferences | /students/me/preferences |
| `teacher:read` | View assigned students | /teachers/{id}/students |
| `teacher:write` | Assign content, override recommendations | /teachers/{id}/assignments |
| `parent:read` | View child's progress | /parents/{id}/children |
| `admin:read` | District-wide analytics | /admin/* |
| `admin:write` | User provisioning, settings | /admin/users, /admin/settings |

## 2.3 Role-Based Access Control

```json
{
  "user_id": "usr-12345",
  "roles": ["teacher"],
  "contexts": [
    {
      "school_id": "sch-789",
      "classes": ["cls-456", "cls-457"],
      "permissions": ["read", "write", "assign"]
    }
  ],
  "iat": 1710324000,
  "exp": 1710324900
}
```

## Core REST Endpoints

## 3.1 Student Service

### Get Current Student
```http
GET /api/v1/students/me
```

**Response 200:**
```json
{
  "id": "stu-12345",
  "grade_level": 5,
  "school_id": "sch-789",
  "language_preference": "en",
  "home_language": "es",
  "accommodations": {
    "iep_flags": ["dyslexia"],
    "extended_time": true,
    "text_to_speech": true
  },
  "created_at": "2025-09-01T00:00:00Z"
}
```

### Get Student Progress
```http
GET /api/v1/students/me/progress?standard=CCSS.MATH.4.NF
```

**Response 200:**
```json
{
  "student_id": "stu-12345",
  "standard": "CCSS.MATH.4.NF",
  "mastery_percentage": 0.75,
  "objectives": [
    {
      "lo_id": "CCSS.MATH.4.NF.A.1",
      "mastery_probability": 0.92,
      "status": "mastered",
      "last_attempted": "2026-03-12T14:30:00Z"
    }
  ]
}
```

### Submit Response
```http
POST /api/v1/students/me/interactions
Content-Type: application/json

{
  "module_id": "mod-abc123",
  "lo_id": "CCSS.MATH.4.NF.A.1",
  "response_data": {"answer": "2/4 = 1/2", "confidence": 0.8},
  "time_spent_seconds": 45,
  "hint_count": 1,
  "session_id": "ses-xyz789"
}
```

**Response 200:**
```json
{
  "interaction_id": "int-999",
  "correctness": 1.0,
  "feedback": "Excellent! You've correctly identified equivalent fractions.",
  "next_recommendation": {
    "module_id": "mod-def456",
    "estimated_difficulty": 0.65,
    "scaffolding_level": "medium"
  },
  "knowledge_update": {
    "mastery_probability": 0.94,
    "change": +0.02
  }
}
```

## 3.2 Recommendation Service

### Get Next Content
```http
GET /api/v1/recommendations/next?student_id=stu-12345&context=practice
```

**Response 200:**
```json
{
  "module_id": "mod-ghi789",
  "lo_id": "CCSS.MATH.4.NF.A.2",
  "content_url": "https://cdn.example.com/content/mod-ghi789",
  "difficulty_tier": 3,
  "scaffolding": {
    "hints_available": 3,
    "worked_example": false,
    "manipulative": true
  },
  "estimated_time_minutes": 5,
  "format_variants": ["interactive", "textual"],
  "generated_at": "2026-03-13T10:30:00Z"
}
```

### Get Learning Path
```http
POST /api/v1/recommendations/path
Content-Type: application/json

{
  "student_id": "stu-12345",
  "target_lo_id": "CCSS.MATH.5.NF.B.4",
  "max_steps": 10
}
```

**Response 200:**
```json
{
  "path_id": "path-xyz",
  "estimated_duration_minutes": 45,
  "objectives": [
    {
      "lo_id": "CCSS.MATH.4.NF.A.1",
      "action": "review",
      "priority": 1
    },
    {
      "lo_id": "CCSS.MATH.4.NF.B.3",
      "action": "master",
      "priority": 2
    }
  ]
}
```

## 3.3 Content Service

### Get Content Module
```http
GET /api/v1/content/{module_id}
```

**Response 200:**
```json
{
  "module_id": "mod-abc123",
  "lo_id": "CCSS.MATH.4.NF.A.1",
  "module_type": "worked_example",
  "difficulty_tier": 2,
  "content": {
    "title": "Equivalent Fractions",
    "body": "...",
    "media_assets": [
      {"type": "image", "url": "https://cdn...", "alt_text": "..."}
    ]
  },
  "accessibility": {
    "tts_enabled": true,
    "captions": "https://cdn.../captions.vtt",
    "dyslexia_font": true
  },
  "assessment_items": [
    {"item_id": "item-001", "type": "multiple_choice"}
  ],
  "hint_sequence": [
    {"hint_id": "hint-001", "content": "Try drawing the fractions..."}
  ],
  "format_variants": ["interactive", "video", "text"],
  "version": "1.2.0"
}
```

### List Content by Standard
```http
GET /api/v1/content?standard=CCSS.MATH.4.NF.A.1&difficulty_tier=2
```

## 3.4 Teacher Service

### Get Class Roster
```http
GET /api/v1/teachers/{teacher_id}/classes/{class_id}/students
```

### Get At-Risk Students
```http
GET /api/v1/teachers/{teacher_id}/alerts/at-risk
```

**Response 200:**
```json
{
  "generated_at": "2026-03-13T06:00:00Z",
  "students": [
    {
      "student_id": "stu-12345",
      "risk_level": "high",
      "at_risk_objectives": ["CCSS.MATH.4.NF.A.1"],
      "predicted_success_rate": 0.35,
      "recommended_action": "intervention",
      "last_activity": "2026-03-12T15:00:00Z"
    }
  ]
}
```

### Assign Content
```http
POST /api/v1/teachers/{teacher_id}/assignments
Content-Type: application/json

{
  "class_ids": ["cls-456"],
  "student_ids": ["stu-12345"],
  "module_ids": ["mod-abc123"],
  "due_date": "2026-03-20T23:59:59Z",
  "override_recommendations": false
}
```

## 3.5 Analytics Service

### Get Engagement Metrics
```http
GET /api/v1/analytics/engagement?student_id=stu-12345&days=7
```

### Export Progress Report
```http
GET /api/v1/analytics/export/progress?class_id=cls-456&format=csv
```

**Response:** CSV file (OneRoster format)

## GraphQL Schema

## 4.1 Schema Definition

```graphql
# Queries
type Query {
  # Student queries
  me: Student!
  student(id: ID!): Student
  students(filter: StudentFilter): [Student!]!
  
  # Content queries
  contentModule(id: ID!): ContentModule
  contentModules(filter: ContentFilter): [ContentModule!]!
  
  # Recommendation queries
  nextRecommendation(studentId: ID!, context: RecommendationContext): Recommendation!
  learningPath(studentId: ID!, targetLoId: ID!): LearningPath!
  
  # Analytics queries
  progress(studentId: ID!, standard: String): ProgressReport!
  engagementMetrics(filter: EngagementFilter): EngagementReport!
}

# Mutations
type Mutation {
  # Student interactions
  submitResponse(input: ResponseInput!): Feedback!
  updatePreferences(input: PreferencesInput!): Student!
  
  # Teacher actions
  createAssignment(input: AssignmentInput!): Assignment!
  overrideRecommendation(input: OverrideInput!): Recommendation!
  
  # Admin actions
  provisionUser(input: ProvisionInput!): User!
  updateContent(input: ContentUpdateInput!): ContentModule!
}

# Subscriptions
type Subscription {
  knowledgeStateUpdated(studentId: ID!): KnowledgeState!
  atRiskAlert(teacherId: ID!): AtRiskAlert!
  assignmentCompleted(assignmentId: ID!): AssignmentResult!
}
```

## 4.2 Type Definitions

```graphql
type Student {
  id: ID!
  gradeLevel: Int!
  school: School!
  knowledgeState: KnowledgeState!
  currentSession: Session
  progress(standardCode: String): [ProgressEntry!]!
  accommodations: Accommodations!
  preferences: Preferences!
}

type KnowledgeState {
  studentId: ID!
  masteryProbability(loId: String!): Float!
  masteryMap: [MasteryEntry!]!
  frontier: [LearningObjective!]!
  atRiskObjectives: [LearningObjective!]!
  lastUpdated: DateTime!
}

type LearningObjective {
  id: ID!
  standardCode: String!
  description: String!
  difficultyIndex: Float!
  cognitiveComplexity: Int!
  prerequisites: [LearningObjective!]!
  contentModules: [ContentModule!]!
}

type ContentModule {
  id: ID!
  loId: String!
  moduleType: ModuleType!
  difficultyTier: Int!
  content: ContentPayload!
  accessibility: AccessibilityFeatures!
  formatVariants: [FormatVariant!]!
  version: String!
}

type Recommendation {
  moduleId: ID!
  loId: String!
  contentUrl: String!
  difficultyTier: Int!
  scaffolding: ScaffoldingConfig!
  estimatedTimeMinutes: Int!
  confidence: Float!
}

type Feedback {
  interactionId: ID!
  correctness: Float!
  feedback: String!
  nextRecommendation: Recommendation
  knowledgeUpdate: KnowledgeUpdate!
}
```

## 4.3 Example Queries

### Student Dashboard Query
```graphql
query StudentDashboard {
  me {
    id
    gradeLevel
    knowledgeState {
      frontier(limit: 5) {
        id
        description
      }
      atRiskObjectives {
        id
        standardCode
      }
    }
    progress(standardCode: "CCSS.MATH.4.NF") {
      loId
      masteryProbability
      status
    }
  }
}
```

### Submit Response Mutation
```graphql
mutation SubmitAnswer($input: ResponseInput!) {
  submitResponse(input: $input) {
    correctness
    feedback
    nextRecommendation {
      moduleId
      contentUrl
    }
    knowledgeUpdate {
      masteryProbability
      change
    }
  }
}
```

### Real-Time Knowledge Updates
```graphql
subscription KnowledgeUpdates($studentId: ID!) {
  knowledgeStateUpdated(studentId: $studentId) {
    masteryMap {
      loId
      probability
    }
    lastUpdated
  }
}
```

## LTI 1.3 Integration

## 5.1 LTI Launch Endpoint

### Login Initiation
```http
GET /lti/login
?iss={platform_issuer}
&login_hint={user_identifier}
&target_link_uri={tool_url}
&lti_message_hint={context_hint}
```

### Launch Endpoint
```http
POST /lti/launch
Content-Type: application/x-www-form-urlencoded

id_token={jwt_token}
state={csrf_state}
```

**IdToken JWT Payload:**
```json
{
  "iss": "https://lms.school.edu",
  "sub": "user-12345",
  "aud": "tool-client-id",
  "exp": 1710324900,
  "iat": 1710324000,
  "nonce": "unique-nonce",
  "https://purl.imsglobal.org/spec/lti/claim/message_type": "LtiResourceLinkRequest",
  "https://purl.imsglobal.org/spec/lti/claim/version": "1.3.0",
  "https://purl.imsglobal.org/spec/lti/claim/resource_link": {
    "id": "resource-abc",
    "title": "Fraction Practice"
  },
  "https://purl.imsglobal.org/spec/lti/claim/roles": ["http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"],
  "https://purl.imsglobal.org/spec/lti/claim/context": {
    "id": "course-456",
    "title": "Math 4th Grade"
  }
}
```

## 5.2 Names and Roles Service

### Get Membership
```http
GET /lti/services/nrps/v2/context/{context_id}/memberships
Authorization: Bearer {access_token}
```

**Response 200:**
```json
{
  "id": "https://platform.example.com/lti/services/nrps/v2/context/course-456/memberships",
  "context": {
    "id": "course-456",
    "title": "Math 4th Grade"
  },
  "members": [
    {
      "status": "Active",
      "name": "Jane Student",
      "picture": "https://...",
      "given_name": "Jane",
      "family_name": "Student",
      "email": "jane@school.edu",
      "user_id": "user-12345",
      "roles": ["http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"]
    }
  ]
}
```

## 5.3 Assignment and Grade Services

### Create Line Item
```http
POST /lti/services/ags/v2/course/{context_id}/lineItems
Authorization: Bearer {access_token}
Content-Type: application/vnd.ims.lis.v2.lineitem+json

{
  "scoreMaximum": 100,
  "label": "Fractions Quiz",
  "resourceId": "mod-abc123",
  "tag": "quiz",
  "startDateTime": "2026-03-01T00:00:00Z",
  "endDateTime": "2026-03-31T23:59:59Z"
}
```

### Post Score
```http
PUT /lti/services/ags/v2/course/{context_id}/lineItems/{line_item_id}/scores
Authorization: Bearer {access_token}
Content-Type: application/vnd.ims.lis.v2.score+json

{
  "userId": "user-12345",
  "scoreGiven": 85,
  "scoreMaximum": 100,
  "comment": "Great work on equivalent fractions!",
  "timestamp": "2026-03-13T10:30:00Z",
  "activityProgress": "Completed",
  "gradingProgress": "FullyGraded"
}
```

## Error Handling

## 6.1 HTTP Status Codes

| Status | Meaning | Usage |
|--------|---------|-------|
| 200 | OK | Successful GET/PUT/PATCH |
| 201 | Created | Successful POST (resource created) |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Invalid request format or parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Valid auth but insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Resource state conflict (e.g., duplicate) |
| 422 | Unprocessable | Valid JSON but failed business rules |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | Internal server error |
| 503 | Service Unavailable | Temporary outage or maintenance |

## 6.2 Error Response Format

```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "The request parameter 'grade_level' must be between K and 12",
    "target": "grade_level",
    "details": [
      {
        "code": "RANGE_ERROR",
        "message": "Value 15 is outside valid range [0, 12]",
        "target": "grade_level"
      }
    ],
    "request_id": "req-abc123",
    "timestamp": "2026-03-13T10:30:00Z"
  }
}
```

## 6.3 Common Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| `INVALID_PARAMETER` | Request parameter validation failed | Check parameter format/range |
| `RESOURCE_NOT_FOUND` | Requested resource doesn't exist | Verify resource ID |
| `INSUFFICIENT_PERMISSIONS` | User lacks required role/scope | Request appropriate permissions |
| `RATE_LIMIT_EXCEEDED` | Too many requests | Implement exponential backoff |
| `DEPENDENCY_ERROR` | Downstream service failure | Retry after delay |
| `MAINTENANCE_MODE` | System undergoing maintenance | Check status page |
| `CONTENT_VERSION_MISMATCH` | Content has been updated | Refresh and retry |
| `MASTERY_THRESHOLD_NOT_MET` | Cannot advance without mastery | Complete prerequisite content |

## 6.4 Rate Limiting Headers

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1710327600
Retry-After: 300

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "API rate limit exceeded. Please retry after 300 seconds.",
    "request_id": "req-xyz789"
  }
}
```

## Versioning and Deprecation

## 7.1 Versioning Strategy

**URL Versioning:**
- Current: `/api/v1/`
- Beta: `/api/v2-beta/`
- Legacy support: Last 2 major versions

**Version Header (Optional):**
```http
Accept: application/vnd.adaptive-learning.v1+json
```

## 7.2 Deprecation Policy

| Phase | Timeline | Behavior |
|-------|----------|----------|
| **Announcement** | -6 months | Deprecation notice in docs, response headers |
| **Warning** | -3 months | `Deprecation` header added to responses |
| **Sunset** | 0 | Endpoint returns 410 Gone with migration guide |

**Deprecation Headers:**
```http
Deprecation: true
Sunset: Sun, 31 Dec 2026 23:59:59 GMT
Link: </api/v2/students>; rel="successor-version"
```

## 7.3 Breaking vs. Non-Breaking Changes

**Breaking Changes (Major Version):**
- Removing or renaming endpoints
- Changing required parameters
- Altering response structure
- Removing enum values

**Non-Breaking Changes (Minor/Patch):**
- Adding new optional parameters
- Adding new fields to responses
- Adding new endpoints
- Performance improvements

## Appendix: Complete Endpoint Reference

## A.1 Student Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /api/v1/students/me | Get current student | student:read |
| PATCH | /api/v1/students/me | Update preferences | student:write |
| GET | /api/v1/students/me/progress | Get progress by standard | student:read |
| GET | /api/v1/students/me/knowledge-state | Get current knowledge state | student:read |
| POST | /api/v1/students/me/interactions | Submit response | student:write |
| GET | /api/v1/students/{id} | Get student by ID (teacher view) | teacher:read |

## A.2 Recommendation Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /api/v1/recommendations/next | Get next content | student:read |
| POST | /api/v1/recommendations/path | Get learning path | student:read |
| POST | /api/v1/recommendations/override | Teacher override | teacher:write |

## A.3 Content Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /api/v1/content | List content modules | student:read |
| GET | /api/v1/content/{id} | Get content module | student:read |
| POST | /api/v1/content | Create content (admin) | admin:write |
| PUT | /api/v1/content/{id} | Update content | admin:write |

## A.4 Teacher Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /api/v1/teachers/{id}/classes | List teacher's classes | teacher:read |
| GET | /api/v1/teachers/{id}/classes/{cid}/students | Get class roster | teacher:read |
| POST | /api/v1/teachers/{id}/assignments | Create assignment | teacher:write |
| GET | /api/v1/teachers/{id}/alerts/at-risk | Get at-risk students | teacher:read |

## A.5 Analytics Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /api/v1/analytics/engagement | Get engagement metrics | teacher:read |
| GET | /api/v1/analytics/mastery | Get mastery reports | teacher:read |
| GET | /api/v1/analytics/export/progress | Export progress (CSV) | teacher:read |

## A.6 Admin Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | /api/v1/admin/users | Provision user | admin:write |
| GET | /api/v1/admin/users | List users | admin:read |
| GET | /api/v1/admin/analytics/district | District-wide analytics | admin:read |
| POST | /api/v1/admin/content/import | Bulk content import | admin:write |

## A.7 LTI Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /lti/login | Login initiation |
| POST | /lti/launch | Launch endpoint |
| GET | /lti/jwks.json | JWKS endpoint |
| GET | /lti/services/nrps/v2/context/{id}/memberships | Names and Roles |
| POST | /lti/services/ags/v2/course/{id}/lineItems | Gradebook sync |

## A.8 Webhooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /webhooks/clever | Clever roster sync |
| POST | /webhooks/google | Google Classroom events |
| POST | /webhooks/internal | Internal service events |
