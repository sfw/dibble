---
based_on: architecture-design.md
date: '2026-03-14'
version: 1.0.0
---

# AKSRE Tool Source Code

## Overview

This document contains the complete source code for the Adaptive Knowledge State & Recommendation Engine (AKSRE), a FastAPI-based microservice implementing Bayesian Knowledge Tracing (BKT) with SM2 spaced repetition scheduling.

**Technology Stack:**
- Python 3.11+ with FastAPI
- Redis (hot cache)
- Cassandra (persistent storage)
- Kafka (event streaming)
- NVIDIA Triton (DKT inference - Phase 2)

## Project Structure

```
aksre/
├── pyproject.toml              # Project dependencies
├── config.yaml                 # Runtime configuration
├── Dockerfile                  # Container image
├── docker-compose.yml          # Local development
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry
│   ├── config.py               # Configuration management
│   ├── models/
│   │   ├── __init__.py
│   │   ├── bkt.py              # BKT data models
│   │   ├── requests.py         # API request schemas
│   │   └── responses.py        # API response schemas
│   ├── engines/
│   │   ├── __init__.py
│   │   ├── bkt_engine.py       # BKT inference engine
│   │   └── sm2_scheduler.py    # SM2 spaced repetition
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── knowledge_state.py  # State storage abstraction
│   │   ├── redis_store.py      # Redis implementation
│   │   └── cassandra_store.py  # Cassandra implementation
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py           # API route definitions
│   │   ├── state.py            # State endpoints
│   │   └── recommendations.py  # Recommendation endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── event_publisher.py  # Kafka event publishing
│   │   └── circuit_breaker.py  # Fault tolerance
│   └── utils/
│       ├── __init__.py
│       ├── logging.py          # Structured logging
│       └── errors.py           # Error definitions
└── tests/
    ├── test_bkt_engine.py
    ├── test_api.py
    └── test_integration.py
```

## pyproject.toml

```toml
[project]
name = "aksre"
version = "1.0.0"
description = "Adaptive Knowledge State & Recommendation Engine"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
keywords = ["education", "knowledge-tracing", "bkt", "adaptive-learning"]
authors = [
    {name = "Adaptive Ed Platform Team"}
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Education",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "redis>=5.0.0",
    "cassandra-driver>=3.29.0",
    "kafka-python>=2.0.2",
    "structlog>=23.2.0",
    "prometheus-client>=0.19.0",
    "python-json-logger>=2.0.7",
    "tenacity>=8.2.3",
    "httpx>=0.25.2",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.3",
    "pytest-asyncio>=0.21.1",
    "pytest-cov>=4.1.0",
    "black>=23.11.0",
    "ruff>=0.1.6",
    "mypy>=1.7.1",
    "httpx>=0.25.2",
    "fakeredis>=2.20.0",
]

[project.scripts]
aksre = "aksre.main:main"

[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing"
```

## config.yaml

```yaml
# AKSRE Runtime Configuration

app:
  name: "aksre"
  version: "1.0.0"
  environment: "development"  # development, staging, production
  debug: false
  host: "0.0.0.0"
  port: 8080
  workers: 4

# BKT Engine Configuration
bkt:
  default_params:
    p_l0: 0.30    # Initial probability of mastery
    p_t: 0.20     # Probability of learning (transition)
    p_g: 0.15     # Probability of guessing correctly
    p_s: 0.10     # Probability of slipping (incorrect despite mastery)
  mastery_threshold: 0.80
  min_attempts_for_mastery: 3

# SM2 Spaced Repetition Configuration
sm2:
  initial_interval: 1  # days
  initial_easiness: 2.5
  min_easiness: 1.3
  max_interval: 365    # days

# Redis Configuration
redis:
  cluster:
    enabled: false
    startup_nodes:
      - host: "localhost"
        port: 6379
  single:
    host: "localhost"
    port: 6379
    db: 0
    password: null
    socket_timeout: 5
    socket_connect_timeout: 5
    retry_on_timeout: true
    max_connections: 50
  ttl_seconds: 86400  # 24 hours

# Cassandra Configuration
cassandra:
  hosts:
    - "localhost"
  port: 9042
  keyspace: "aksre"
  username: null
  password: null
  consistency_level: "LOCAL_QUORUM"
  retry_policy:
    max_retries: 3
    delay_ms: 100

# Kafka Configuration
kafka:
  bootstrap_servers:
    - "localhost:9092"
  topic: "knowledge-state-events"
  acks: "all"
  retries: 3
  compression: "snappy"
  max_block_ms: 5000
  enabled: true

# DKT Client Configuration (Phase 2)
dkt:
  enabled: false
  triton_host: "localhost"
  triton_port: 8001
  model_name: "dkt_model"
  timeout_ms: 50
  circuit_breaker:
    failure_threshold: 3
    recovery_timeout_seconds: 20

# Circuit Breaker Configuration
circuit_breaker:
  redis:
    failure_threshold: 5
    recovery_timeout_seconds: 30
  cassandra:
    failure_threshold: 10
    recovery_timeout_seconds: 60

# Logging Configuration
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "json"  # json, console
  include_trace: true

# Health Check Configuration
health:
  cache_duration_seconds: 5
  timeout_ms: 2000

# Rate Limiting
rate_limit:
  requests_per_minute: 1000
  burst_size: 100

# Security
security:
  jwt_secret: null  # Set via environment variable
  jwt_algorithm: "HS256"
  token_expire_minutes: 60
```

## src/__init__.py

```python
"""AKSRE - Adaptive Knowledge State & Recommendation Engine."""

__version__ = "1.0.0"
__author__ = "Adaptive Ed Platform Team"
```

## src/config.py

```python
"""Configuration management for AKSRE."""

import os
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisConfig(BaseSettings):
    """Redis configuration."""
    model_config = SettingsConfigDict(env_prefix="REDIS_")
    
    cluster_enabled: bool = False
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    max_connections: int = 50
    ttl_seconds: int = 86400


class CassandraConfig(BaseSettings):
    """Cassandra configuration."""
    model_config = SettingsConfigDict(env_prefix="CASSANDRA_")
    
    hosts: List[str] = Field(default_factory=lambda: ["localhost"])
    port: int = 9042
    keyspace: str = "aksre"
    username: Optional[str] = None
    password: Optional[str] = None
    consistency_level: str = "LOCAL_QUORUM"


class BKTConfig(BaseSettings):
    """BKT engine configuration."""
    p_l0: float = 0.30
    p_t: float = 0.20
    p_g: float = 0.15
    p_s: float = 0.10
    mastery_threshold: float = 0.80
    min_attempts_for_mastery: int = 3


class SM2Config(BaseSettings):
    """SM2 scheduler configuration."""
    initial_interval: int = 1
    initial_easiness: float = 2.5
    min_easiness: float = 1.3
    max_interval: int = 365


class DKTConfig(BaseSettings):
    """DKT client configuration."""
    enabled: bool = False
    triton_host: str = "localhost"
    triton_port: int = 8001
    model_name: str = "dkt_model"
    timeout_ms: int = 50


class CircuitBreakerConfig(BaseSettings):
    """Circuit breaker configuration."""
    redis_failure_threshold: int = 5
    redis_recovery_timeout: int = 30
    cassandra_failure_threshold: int = 10
    cassandra_recovery_timeout: int = 60


class AppConfig(BaseSettings):
    """Application configuration."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    name: str = "aksre"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 4
    
    # Sub-configs
    bkt: BKTConfig = Field(default_factory=BKTConfig)
    sm2: SM2Config = Field(default_factory=SM2Config)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    cassandra: CassandraConfig = Field(default_factory=CassandraConfig)
    dkt: DKTConfig = Field(default_factory=DKTConfig)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML file and environment variables.
    
    Environment variables override YAML configuration.
    """
    if config_path is None:
        # Look for config.yaml in standard locations
        paths = [
            Path("config.yaml"),
            Path("/etc/aksre/config.yaml"),
            Path.home() / ".config" / "aksre" / "config.yaml",
        ]
        for path in paths:
            if path.exists():
                config_path = str(path)
                break
    
    config_data = {}
    if config_path and Path(config_path).exists():
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
    
    # Flatten nested config for Pydantic
    flattened = {}
    if config_data:
        for section, values in config_data.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    flattened[f"{section}_{key}"] = value
            else:
                flattened[section] = values
    
    return AppConfig(**flattened)


# Global config instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: AppConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
```

## src/utils/logging.py

```python
"""Structured logging configuration for AKSRE."""

import logging
import sys
from typing import Any, Dict

import structlog
from pythonjsonlogger import jsonlogger

from ..config import get_config


def setup_logging() -> None:
    """Configure structured logging for the application."""
    config = get_config()
    
    # Configure standard library logging
    log_handler = logging.StreamHandler(sys.stdout)
    
    if config.log_format == "json":
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            rename_fields={"levelname": "level", "asctime": "timestamp"},
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    log_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level))
    root_logger.handlers = [log_handler]
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if config.log_format == "json" 
            else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
```

## src/utils/errors.py

```python
"""Error definitions and exception handling for AKSRE."""

from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException, status


class ErrorCode(Enum):
    """Application error codes."""
    # Validation errors (400)
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_LO_ID = "INVALID_LO_ID"
    INVALID_INTERACTION = "INVALID_INTERACTION"
    
    # Authentication/Authorization (401/403)
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_TOKEN = "INVALID_TOKEN"
    
    # Not found (404)
    STUDENT_NOT_FOUND = "STUDENT_NOT_FOUND"
    LO_NOT_FOUND = "LO_NOT_FOUND"
    KNOWLEDGE_STATE_NOT_FOUND = "KNOWLEDGE_STATE_NOT_FOUND"
    
    # Dependency failures (503)
    REDIS_UNAVAILABLE = "REDIS_UNAVAILABLE"
    CASSANDRA_UNAVAILABLE = "CASSANDRA_UNAVAILABLE"
    DKT_UNAVAILABLE = "DKT_UNAVAILABLE"
    KAFKA_UNAVAILABLE = "KAFKA_UNAVAILABLE"
    
    # Timeout (504)
    REQUEST_TIMEOUT = "REQUEST_TIMEOUT"
    INFERENCE_TIMEOUT = "INFERENCE_TIMEOUT"
    
    # Internal errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"


class AKSREError(Exception):
    """Base exception for AKSRE application."""
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
            }
        }


class ValidationError(AKSREError):
    """Invalid request data."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            ErrorCode.INVALID_REQUEST,
            message,
            details,
            status.HTTP_400_BAD_REQUEST,
        )


class NotFoundError(AKSREError):
    """Resource not found."""
    def __init__(self, code: ErrorCode, message: str):
        super().__init__(
            code,
            message,
            None,
            status.HTTP_404_NOT_FOUND,
        )


class DependencyError(AKSREError):
    """External dependency failure."""
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        fallback_applied: Optional[str] = None,
        retry_after: Optional[int] = None,
    ):
        details = {}
        if fallback_applied:
            details["fallback_applied"] = fallback_applied
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(
            code,
            message,
            details,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def http_exception_handler(request: Any, exc: AKSREError) -> HTTPException:
    """Convert AKSREError to HTTPException."""
    return HTTPException(
        status_code=exc.status_code,
        detail=exc.to_dict(),
    )
```


## src/models/__init__.py

```python
"""Pydantic models for AKSRE."""

from .bkt import BKTParams, BKTState, MasteryResult, SpacedInterval
from .requests import InteractionEvent, UpdateRequest, RecommendRequest
from .responses import KnowledgeStateResponse, UpdateResponse, RecommendResponse

__all__ = [
    "BKTParams",
    "BKTState", 
    "MasteryResult",
    "SpacedInterval",
    "InteractionEvent",
    "UpdateRequest",
    "RecommendRequest",
    "KnowledgeStateResponse",
    "UpdateResponse",
    "RecommendResponse",
]
```

## src/models/bkt.py

```python
"""BKT data models."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BKTParams(BaseModel):
    """Bayesian Knowledge Tracing parameters."""
    
    p_l0: float = Field(default=0.30, ge=0.0, le=1.0, description="Initial P(mastery)")
    p_t: float = Field(default=0.20, ge=0.0, le=1.0, description="P(learn)")
    p_g: float = Field(default=0.15, ge=0.0, le=1.0, description="P(guess)")
    p_s: float = Field(default=0.10, ge=0.0, le=1.0, description="P(slip)")
    
    @field_validator("p_g")
    @classmethod
    def validate_guess(cls, v: float) -> float:
        if v > 0.5:
            raise ValueError("P(guess) should typically be < 0.5")
        return v
    
    @field_validator("p_s")
    @classmethod
    def validate_slip(cls, v: float) -> float:
        if v > 0.5:
            raise ValueError("P(slip) should typically be < 0.5")
        return v


class BKTState(BaseModel):
    """Current knowledge state for a student-LO pair."""
    
    student_id: UUID
    lo_id: str
    p_mastery: float = Field(ge=0.0, le=1.0)
    p_learn: float = Field(ge=0.0, le=1.0)
    p_guess: float = Field(ge=0.0, le=1.0)
    p_slip: float = Field(ge=0.0, le=1.0)
    attempt_count: int = Field(ge=0)
    last_attempt_at: Optional[datetime] = None
    is_mastered: bool = False
    next_review_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MasteryResult(BaseModel):
    """Result of a mastery computation."""
    
    student_id: UUID
    lo_id: str
    p_mastery: float = Field(ge=0.0, le=1.0)
    is_mastered: bool
    confidence: float = Field(ge=0.0, le=1.0, description="Based on attempt count")


class SpacedInterval(BaseModel):
    """SM2 spaced repetition interval."""
    
    interval_days: int = Field(ge=1)
    repetitions: int = Field(ge=0)
    easiness_factor: float = Field(ge=1.3, le=2.5)
    next_review_at: datetime
```

## src/models/requests.py

```python
"""API request models."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class InteractionEvent(BaseModel):
    """A learning interaction event."""
    
    content_module_id: UUID
    correctness: float = Field(ge=0.0, le=1.0, description="1.0 for correct, 0.0 for incorrect")
    time_spent_seconds: int = Field(ge=0)
    hints_used: int = Field(default=0, ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator("time_spent_seconds")
    @classmethod
    def validate_time_spent(cls, v: int) -> int:
        if v > 3600:  # 1 hour max
            raise ValueError("time_spent_seconds seems too high (> 1 hour)")
        return v


class UpdateRequest(BaseModel):
    """Request to update knowledge state."""
    
    lo_id: str = Field(..., min_length=1, max_length=100)
    interaction: InteractionEvent
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @field_validator("lo_id")
    @classmethod
    def validate_lo_id(cls, v: str) -> str:
        if not v or len(v) > 100:
            raise ValueError("lo_id must be between 1 and 100 characters")
        return v


class RecommendRequest(BaseModel):
    """Request for content recommendations."""
    
    student_id: UUID
    target_lo_ids: List[str] = Field(..., min_length=1, max_length=100)
    limit: int = Field(default=5, ge=1, le=20)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
```

## src/models/responses.py

```python
"""API response models."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeStateItem(BaseModel):
    """Single knowledge state entry."""
    
    lo_id: str
    p_mastery: float = Field(ge=0.0, le=1.0)
    p_learn: float = Field(ge=0.0, le=1.0)
    p_guess: float = Field(ge=0.0, le=1.0)
    p_slip: float = Field(ge=0.0, le=1.0)
    attempt_count: int = Field(ge=0)
    last_attempt_at: Optional[datetime] = None
    is_mastered: bool
    next_review_at: Optional[datetime] = None


class KnowledgeStateResponse(BaseModel):
    """Response for knowledge state query."""
    
    student_id: UUID
    timestamp: datetime
    states: List[KnowledgeStateItem]


class UpdateResponse(BaseModel):
    """Response for knowledge state update."""
    
    student_id: UUID
    lo_id: str
    previous_p_mastery: float = Field(ge=0.0, le=1.0)
    current_p_mastery: float = Field(ge=0.0, le=1.0)
    is_mastered: bool
    next_review_at: Optional[datetime] = None
    processing_time_ms: int


class RecommendationItem(BaseModel):
    """Single recommendation item."""
    
    lo_id: str
    predicted_success_probability: float = Field(ge=0.0, le=1.0)
    bkt_p_mastery: float = Field(ge=0.0, le=1.0)
    dkt_prediction: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    difficulty_tier: int = Field(ge=1, le=5)
    recommendation_reason: str


class RecommendResponse(BaseModel):
    """Response for recommendations."""
    
    student_id: UUID
    recommendations: List[RecommendationItem]
    latency_ms: int
```

## src/engines/__init__.py

```python
"""Inference engines for AKSRE."""

from .bkt_engine import BKTEngine
from .sm2_scheduler import SM2Scheduler

__all__ = ["BKTEngine", "SM2Scheduler"]
```

## src/engines/bkt_engine.py

```python
"""Bayesian Knowledge Tracing inference engine."""

from datetime import datetime
from typing import Tuple
from uuid import UUID

from ..config import get_config
from ..models.bkt import BKTParams, BKTState, MasteryResult
from ..utils.logging import get_logger

logger = get_logger(__name__)


class BKTEngine:
    """BKT inference engine implementing the standard BKT algorithm.
    
    BKT assumes a binary hidden state (mastered/not mastered) and models
    learning as a transition probability. The algorithm uses Bayes' rule
    to update P(mastery) after each observed interaction.
    """
    
    def __init__(self):
        self.config = get_config().bkt
        self.default_params = BKTParams(
            p_l0=self.config.p_l0,
            p_t=self.config.p_t,
            p_g=self.config.p_g,
            p_s=self.config.p_s,
        )
        self.mastery_threshold = self.config.mastery_threshold
        self.min_attempts = self.config.min_attempts_for_mastery
    
    def compute_mastery(
        self,
        student_id: UUID,
        lo_id: str,
        current_state: BKTState,
    ) -> MasteryResult:
        """Compute current mastery status from state."""
        confidence = min(1.0, current_state.attempt_count / 10)
        
        is_mastered = (
            current_state.p_mastery >= self.mastery_threshold
            and current_state.attempt_count >= self.min_attempts
        )
        
        return MasteryResult(
            student_id=student_id,
            lo_id=lo_id,
            p_mastery=current_state.p_mastery,
            is_mastered=is_mastered,
            confidence=confidence,
        )
    
    def update_parameters(
        self,
        current_state: BKTState,
        correctness: float,
    ) -> BKTState:
        """Update BKT parameters using Bayes' rule."""
        p_l = current_state.p_mastery
        p_t = current_state.p_learn
        p_g = current_state.p_guess
        p_s = current_state.p_slip
        
        # Prior probability of correctness
        p_correct = (1 - p_s) * p_l + p_g * (1 - p_l)
        
        if correctness >= 0.5:  # Correct
            p_l_given_obs = ((1 - p_s) * p_l) / p_correct if p_correct > 0 else p_l
        else:  # Incorrect
            p_incorrect = 1 - p_correct
            p_l_given_obs = (p_s * p_l) / p_incorrect if p_incorrect > 0 else p_l
        
        # Apply learning transition
        new_p_l = p_l_given_obs + (1 - p_l_given_obs) * p_t
        new_p_l = max(0.0, min(1.0, new_p_l))
        
        logger.debug(
            "BKT update",
            student_id=str(current_state.student_id),
            lo_id=current_state.lo_id,
            previous_p_mastery=round(p_l, 4),
            new_p_mastery=round(new_p_l, 4),
            correctness=correctness,
        )
        
        is_mastered = new_p_l >= self.mastery_threshold and current_state.attempt_count + 1 >= self.min_attempts
        
        return BKTState(
            student_id=current_state.student_id,
            lo_id=current_state.lo_id,
            p_mastery=new_p_l,
            p_learn=p_t,
            p_guess=p_g,
            p_slip=p_s,
            attempt_count=current_state.attempt_count + 1,
            last_attempt_at=datetime.utcnow(),
            is_mastered=is_mastered,
            next_review_at=current_state.next_review_at,
            created_at=current_state.created_at,
            updated_at=datetime.utcnow(),
        )
    
    def predict_success_probability(self, state: BKTState) -> float:
        """Predict probability of next response being correct."""
        p_l = state.p_mastery
        p_g = state.p_guess
        p_s = state.p_slip
        return p_l * (1 - p_s) + (1 - p_l) * p_g
    
    def create_initial_state(self, student_id: UUID, lo_id: str) -> BKTState:
        """Create initial BKT state with default parameters."""
        return BKTState(
            student_id=student_id,
            lo_id=lo_id,
            p_mastery=self.default_params.p_l0,
            p_learn=self.default_params.p_t,
            p_guess=self.default_params.p_g,
            p_slip=self.default_params.p_s,
            attempt_count=0,
            is_mastered=False,
        )
```


## src/engines/sm2_scheduler.py

```python
"""SM-2 spaced repetition scheduler.

Implements the SuperMemo-2 algorithm (SM2) for calculating optimal
review intervals based on performance history.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from ..config import get_config
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SM2Data(BaseModel):
    """SM2 scheduling data for a student-LO pair."""
    
    student_id: UUID
    lo_id: str
    interval: int = Field(default=1, ge=1)  # days
    repetitions: int = Field(default=0, ge=0)
    easiness_factor: float = Field(default=2.5, ge=1.3, le=2.5)
    last_reviewed_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None


class SM2Scheduler:
    """SM-2 spaced repetition scheduler.
    
    The SM2 algorithm adjusts review intervals based on how well
    the student performs. Higher performance leads to longer intervals.
    """
    
    def __init__(self):
        config = get_config().sm2
        self.initial_interval = config.initial_interval
        self.initial_ef = config.initial_easiness
        self.min_ef = config.min_easiness
        self.max_interval = config.max_interval
    
    def calculate_next_review(
        self,
        student_id: UUID,
        lo_id: str,
        performance: float,
        current_data: Optional[SM2Data] = None,
    ) -> SM2Data:
        """Calculate next review interval using SM2 algorithm.
        
        Args:
            student_id: Student UUID
            lo_id: Learning objective ID
            performance: Quality of response (0.0-1.0)
            current_data: Existing SM2 data or None for new items
            
        Returns:
            Updated SM2 data with new interval
        """
        # Convert 0-1 performance to SM2 quality rating (0-5)
        # 0-0.2 -> 0 (complete blackout)
        # 0.2-0.4 -> 1 (incorrect response)
        # 0.4-0.6 -> 2 (correct with difficulty)
        # 0.6-0.8 -> 3 (correct with hesitation)
        # 0.8-1.0 -> 4 (correct with ease)
        quality = min(5, int(performance * 5))
        
        if current_data is None:
            # First review
            data = SM2Data(
                student_id=student_id,
                lo_id=lo_id,
                interval=self.initial_interval,
                repetitions=0,
                easiness_factor=self.initial_ef,
            )
        else:
            data = current_data
        
        # SM2 algorithm
        if quality < 3:
            # Failed response - reset repetitions, keep same interval
            new_repetitions = 0
            new_interval = self.initial_interval
        else:
            # Successful response
            new_repetitions = data.repetitions + 1
            
            if new_repetitions == 1:
                new_interval = 1
            elif new_repetitions == 2:
                new_interval = 6
            else:
                # I(n) = I(n-1) * EF
                new_interval = int(data.interval * data.easiness_factor)
        
        # Update easiness factor
        # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        delta_ef = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        new_ef = max(self.min_ef, data.easiness_factor + delta_ef)
        
        # Cap interval
        new_interval = min(new_interval, self.max_interval)
        
        now = datetime.utcnow()
        next_review = now + timedelta(days=new_interval)
        
        logger.debug(
            "SM2 schedule calculated",
            student_id=str(student_id),
            lo_id=lo_id,
            quality=quality,
            new_interval=new_interval,
            new_repetitions=new_repetitions,
            new_ef=round(new_ef, 2),
        )
        
        return SM2Data(
            student_id=student_id,
            lo_id=lo_id,
            interval=new_interval,
            repetitions=new_repetitions,
            easiness_factor=new_ef,
            last_reviewed_at=now,
            next_review_at=next_review,
        )
```

## src/services/__init__.py

```python
"""Services for AKSRE."""

from .circuit_breaker import CircuitBreaker, CircuitState
from .event_publisher import EventPublisher

__all__ = ["CircuitBreaker", "CircuitState", "EventPublisher"]
```

## src/services/circuit_breaker.py

```python
"""Circuit breaker implementation for fault tolerance."""

import threading
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from ..utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreaker:
    """Circuit breaker for external dependencies.
    
    Implements the circuit breaker pattern to prevent cascade failures
    when external dependencies (Redis, Cassandra, DKT) become unavailable.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.RLock()
    
    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        with self._lock:
            return self._state
    
    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self._last_failure_time and \
                   time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(
                        "Circuit breaker entering half-open",
                        name=self.name,
                    )
                    return True
                return False
            
            # HALF_OPEN
            return self._half_open_calls < self.half_open_max_calls
    
    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(
                        "Circuit breaker closed",
                        name=self.name,
                    )
            else:
                self._failure_count = max(0, self._failure_count - 1)
    
    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker reopened",
                    name=self.name,
                    failure_count=self._failure_count,
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker opened",
                    name=self.name,
                    failure_count=self._failure_count,
                )
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to wrap a function with circuit breaker."""
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            if not self.can_execute():
                raise Exception(f"Circuit breaker is OPEN for {self.name}")
            
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise e
        
        return wrapper
```

## src/services/event_publisher.py

```python
"""Kafka event publisher for knowledge state events."""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError

from ..config import get_config
from ..utils.logging import get_logger

logger = get_logger(__name__)


class EventPublisher:
    """Publishes knowledge state events to Kafka."""
    
    def __init__(self):
        config = get_config()
        self.enabled = config.kafka.get("enabled", True)
        self.topic = config.kafka.get("topic", "knowledge-state-events")
        
        if self.enabled:
            try:
                self._producer = KafkaProducer(
                    bootstrap_servers=config.kafka["bootstrap_servers"],
                    value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                    acks=config.kafka.get("acks", "all"),
                    retries=config.kafka.get("retries", 3),
                    compression_type=config.kafka.get("compression", "snappy"),
                    max_block_ms=config.kafka.get("max_block_ms", 5000),
                )
                logger.info("Kafka producer initialized", topic=self.topic)
            except Exception as e:
                logger.error("Failed to initialize Kafka producer", error=str(e))
                self._producer = None
                self.enabled = False
        else:
            self._producer = None
    
    def publish_knowledge_state_updated(
        self,
        student_id: str,
        lo_id: str,
        previous_p_mastery: float,
        current_p_mastery: float,
        interaction: Dict[str, Any],
        is_mastered: bool,
    ) -> bool:
        """Publish KNOWLEDGE_STATE_UPDATED event."""
        event = {
            "eventType": "KNOWLEDGE_STATE_UPDATED",
            "schemaVersion": "1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "student_id": student_id,
                "lo_id": lo_id,
                "previous_p_mastery": previous_p_mastery,
                "current_p_mastery": current_p_mastery,
                "interaction": interaction,
                "mastery_threshold": 0.80,
                "is_mastered": is_mastered,
            },
        }
        return self._publish(event)
    
    def _publish(self, event: Dict[str, Any]) -> bool:
        """Publish event to Kafka (fire-and-forget)."""
        if not self.enabled or self._producer is None:
            logger.debug("Event publishing disabled or unavailable")
            return False
        
        try:
            self._producer.send(self.topic, event)
            logger.debug("Event published", event_type=event.get("eventType"))
            return True
        except KafkaError as e:
            logger.error("Failed to publish event", error=str(e), event_type=event.get("eventType"))
            return False
    
    def close(self) -> None:
        """Close the Kafka producer."""
        if self._producer:
            self._producer.close()
            logger.info("Kafka producer closed")
```


## src/repositories/__init__.py

```python
"""Repository layer for knowledge state storage."""

from .knowledge_state import KnowledgeStateRepository
from .redis_store import RedisKnowledgeStateRepository
from .cassandra_store import CassandraKnowledgeStateRepository

__all__ = [
    "KnowledgeStateRepository",
    "RedisKnowledgeStateRepository", 
    "CassandraKnowledgeStateRepository",
]
```

## src/repositories/knowledge_state.py

```python
"""Abstract repository interface for knowledge state storage."""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from ..models.bkt import BKTState
from ..engines.sm2_scheduler import SM2Data


class KnowledgeStateRepository(ABC):
    """Abstract interface for knowledge state persistence.
    
    Implementations handle storage/retrieval from Redis, Cassandra, etc.
    """
    
    @abstractmethod
    async def get_state(
        self, 
        student_id: UUID, 
        lo_id: str
    ) -> Optional[BKTState]:
        """Retrieve BKT state for a student-LO pair."""
        pass
    
    @abstractmethod
    async def save_state(
        self, 
        state: BKTState
    ) -> bool:
        """Save BKT state."""
        pass
    
    @abstractmethod
    async def get_sm2_data(
        self, 
        student_id: UUID, 
        lo_id: str
    ) -> Optional[SM2Data]:
        """Retrieve SM2 scheduling data."""
        pass
    
    @abstractmethod
    async def save_sm2_data(
        self, 
        data: SM2Data
    ) -> bool:
        """Save SM2 scheduling data."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if repository is healthy."""
        pass
```

## src/repositories/redis_store.py

```python
"""Redis implementation of knowledge state repository."""

import json
from typing import Optional
from uuid import UUID

import redis
from redis.exceptions import RedisError

from ..config import get_config
from ..models.bkt import BKTState
from ..engines.sm2_scheduler import SM2Data
from ..services.circuit_breaker import CircuitBreaker
from ..utils.logging import get_logger
from .knowledge_state import KnowledgeStateRepository

logger = get_logger(__name__)


class RedisKnowledgeStateRepository(KnowledgeStateRepository):
    """Redis-backed knowledge state storage (hot cache)."""
    
    def __init__(self):
        self.config = get_config().redis
        self.circuit_breaker = CircuitBreaker(
            name="redis",
            failure_threshold=5,
            recovery_timeout=30,
        )
        self._client: Optional[redis.Redis] = None
        self._connect()
    
    def _connect(self) -> None:
        """Establish Redis connection."""
        try:
            if self.config.cluster_enabled:
                # Redis Cluster support
                from redis.cluster import RedisCluster
                startup_nodes = [{"host": n["host"], "port": n["port"]} 
                                for n in self.config.startup_nodes]
                self._client = RedisCluster(
                    startup_nodes=startup_nodes,
                    password=self.config.password,
                    socket_timeout=self.config.socket_timeout,
                    socket_connect_timeout=self.config.socket_connect_timeout,
                    retry_on_timeout=self.config.retry_on_timeout,
                )
            else:
                # Single Redis instance
                self._client = redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.db,
                    password=self.config.password,
                    socket_timeout=self.config.socket_timeout,
                    socket_connect_timeout=self.config.socket_connect_timeout,
                    retry_on_timeout=self.config.retry_on_timeout,
                    max_connections=self.config.max_connections,
                    decode_responses=True,
                )
            logger.info("Redis connection established")
        except RedisError as e:
            logger.error("Failed to connect to Redis", error=str(e))
            self._client = None
    
    def _get_key(self, student_id: UUID, lo_id: str) -> str:
        """Generate Redis key for BKT state."""
        return f"ks:{student_id}:{lo_id}"
    
    def _get_sm2_key(self, student_id: UUID, lo_id: str) -> str:
        """Generate Redis key for SM2 data."""
        return f"ks:{student_id}:{lo_id}:sm2"
    
    async def get_state(self, student_id: UUID, lo_id: str) -> Optional[BKTState]:
        """Retrieve BKT state from Redis."""
        if not self.circuit_breaker.can_execute():
            logger.warning("Redis circuit breaker open, skipping cache read")
            return None
        
        if self._client is None:
            return None
        
        try:
            key = self._get_key(student_id, lo_id)
            data = self._client.hgetall(key)
            
            if not data:
                return None
            
            # Convert string values back to appropriate types
            state = BKTState(
                student_id=student_id,
                lo_id=lo_id,
                p_mastery=float(data.get("p_mastery", 0.3)),
                p_learn=float(data.get("p_learn", 0.2)),
                p_guess=float(data.get("p_guess", 0.15)),
                p_slip=float(data.get("p_slip", 0.10)),
                attempt_count=int(data.get("attempt_count", 0)),
                is_mastered=data.get("is_mastered", "false").lower() == "true",
            )
            
            self.circuit_breaker.record_success()
            logger.debug("Retrieved state from Redis", student_id=str(student_id), lo_id=lo_id)
            return state
            
        except RedisError as e:
            self.circuit_breaker.record_failure()
            logger.error("Redis get_state failed", error=str(e))
            return None
    
    async def save_state(self, state: BKTState) -> bool:
        """Save BKT state to Redis."""
        if not self.circuit_breaker.can_execute():
            logger.warning("Redis circuit breaker open, skipping cache write")
            return False
        
        if self._client is None:
            return False
        
        try:
            key = self._get_key(state.student_id, state.lo_id)
            data = {
                "p_mastery": str(state.p_mastery),
                "p_learn": str(state.p_learn),
                "p_guess": str(state.p_guess),
                "p_slip": str(state.p_slip),
                "attempt_count": str(state.attempt_count),
                "is_mastered": str(state.is_mastered).lower(),
            }
            
            pipe = self._client.pipeline()
            pipe.hset(key, mapping=data)
            pipe.expire(key, self.config.ttl_seconds)
            pipe.execute()
            
            self.circuit_breaker.record_success()
            logger.debug("Saved state to Redis", student_id=str(state.student_id), lo_id=state.lo_id)
            return True
            
        except RedisError as e:
            self.circuit_breaker.record_failure()
            logger.error("Redis save_state failed", error=str(e))
            return False
    
    async def get_sm2_data(self, student_id: UUID, lo_id: str) -> Optional[SM2Data]:
        """Retrieve SM2 data from Redis."""
        if not self.circuit_breaker.can_execute():
            return None
        
        if self._client is None:
            return None
        
        try:
            key = self._get_sm2_key(student_id, lo_id)
            data = self._client.hgetall(key)
            
            if not data:
                return None
            
            sm2_data = SM2Data(
                student_id=student_id,
                lo_id=lo_id,
                interval=int(data.get("interval", 1)),
                repetitions=int(data.get("repetitions", 0)),
                easiness_factor=float(data.get("easiness_factor", 2.5)),
            )
            
            self.circuit_breaker.record_success()
            return sm2_data
            
        except RedisError as e:
            self.circuit_breaker.record_failure()
            logger.error("Redis get_sm2_data failed", error=str(e))
            return None
    
    async def save_sm2_data(self, data: SM2Data) -> bool:
        """Save SM2 data to Redis."""
        if not self.circuit_breaker.can_execute():
            return False
        
        if self._client is None:
            return False
        
        try:
            key = self._get_sm2_key(data.student_id, data.lo_id)
            redis_data = {
                "interval": str(data.interval),
                "repetitions": str(data.repetitions),
                "easiness_factor": str(data.easiness_factor),
            }
            
            pipe = self._client.pipeline()
            pipe.hset(key, mapping=redis_data)
            pipe.expire(key, self.config.ttl_seconds)
            pipe.execute()
            
            self.circuit_breaker.record_success()
            return True
            
        except RedisError as e:
            self.circuit_breaker.record_failure()
            logger.error("Redis save_sm2_data failed", error=str(e))
            return False
    
    async def health_check(self) -> bool:
        """Check Redis health."""
        if self._client is None:
            return False
        try:
            return self._client.ping()
        except RedisError:
            return False
```

## src/repositories/cassandra_store.py

```python
"""Cassandra implementation of knowledge state repository."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement
from cassandra import ConsistencyLevel

from ..config import get_config
from ..models.bkt import BKTState
from ..engines.sm2_scheduler import SM2Data
from ..services.circuit_breaker import CircuitBreaker
from ..utils.logging import get_logger
from .knowledge_state import KnowledgeStateRepository

logger = get_logger(__name__)


class CassandraKnowledgeStateRepository(KnowledgeStateRepository):
    """Cassandra-backed knowledge state storage (persistent)."""
    
    def __init__(self):
        self.config = get_config().cassandra
        self.circuit_breaker = CircuitBreaker(
            name="cassandra",
            failure_threshold=10,
            recovery_timeout=60,
        )
        self._cluster: Optional[Cluster] = None
        self._session = None
        self._connect()
        self._ensure_schema()
    
    def _connect(self) -> None:
        """Establish Cassandra connection."""
        try:
            self._cluster = Cluster(
                self.config.hosts,
                port=self.config.port,
            )
            
            if self.config.username and self.config.password:
                self._cluster.auth_provider = (
                    self.config.username,
                    self.config.password,
                )
            
            self._session = self._cluster.connect()
            
            # Ensure keyspace exists
            self._session.execute(f"""
                CREATE KEYSPACE IF NOT EXISTS {self.config.keyspace}
                WITH REPLICATION = {{'class': 'SimpleStrategy', 'replication_factor': 3}}
            """)
            self._session.set_keyspace(self.config.keyspace)
            
            logger.info("Cassandra connection established", keyspace=self.config.keyspace)
        except Exception as e:
            logger.error("Failed to connect to Cassandra", error=str(e))
            self._session = None
    
    def _ensure_schema(self) -> None:
        """Ensure database schema exists."""
        if self._session is None:
            return
        
        try:
            # BKT state table
            self._session.execute("""
                CREATE TABLE IF NOT EXISTS student_knowledge_state (
                    student_id uuid,
                    lo_id text,
                    timestamp timestamp,
                    p_mastery double,
                    p_learn double,
                    p_guess double,
                    p_slip double,
                    attempt_count int,
                    is_mastered boolean,
                    next_review_at timestamp,
                    PRIMARY KEY ((student_id, lo_id), timestamp)
                ) WITH CLUSTERING ORDER BY (timestamp DESC)
            """)
            
            # SM2 data table
            self._session.execute("""
                CREATE TABLE IF NOT EXISTS student_sm2_data (
                    student_id uuid,
                    lo_id text,
                    interval_days int,
                    repetitions int,
                    easiness_factor double,
                    last_reviewed_at timestamp,
                    next_review_at timestamp,
                    PRIMARY KEY ((student_id, lo_id))
                )
            """)
            
            logger.info("Cassandra schema ensured")
        except Exception as e:
            logger.error("Failed to ensure schema", error=str(e))
    
    async def get_state(self, student_id: UUID, lo_id: str) -> Optional[BKTState]:
        """Retrieve latest BKT state from Cassandra."""
        if not self.circuit_breaker.can_execute():
            return None
        
        if self._session is None:
            return None
        
        try:
            query = """
                SELECT p_mastery, p_learn, p_guess, p_slip, 
                       attempt_count, is_mastered, next_review_at
                FROM student_knowledge_state
                WHERE student_id = %s AND lo_id = %s
                LIMIT 1
            """
            result = self._session.execute(query, (student_id, lo_id))
            row = result.one()
            
            if row is None:
                return None
            
            state = BKTState(
                student_id=student_id,
                lo_id=lo_id,
                p_mastery=row.p_mastery,
                p_learn=row.p_learn,
                p_guess=row.p_guess,
                p_slip=row.p_slip,
                attempt_count=row.attempt_count,
                is_mastered=row.is_mastered,
                next_review_at=row.next_review_at,
            )
            
            self.circuit_breaker.record_success()
            return state
            
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error("Cassandra get_state failed", error=str(e))
            return None
    
    async def save_state(self, state: BKTState) -> bool:
        """Save BKT state to Cassandra."""
        if not self.circuit_breaker.can_execute():
            return False
        
        if self._session is None:
            return False
        
        try:
            query = """
                INSERT INTO student_knowledge_state
                (student_id, lo_id, timestamp, p_mastery, p_learn, p_guess, 
                 p_slip, attempt_count, is_mastered, next_review_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            self._session.execute(query, (
                state.student_id,
                state.lo_id,
                datetime.utcnow(),
                state.p_mastery,
                state.p_learn,
                state.p_guess,
                state.p_slip,
                state.attempt_count,
                state.is_mastered,
                state.next_review_at,
            ))
            
            self.circuit_breaker.record_success()
            return True
            
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error("Cassandra save_state failed", error=str(e))
            return False
    
    async def get_sm2_data(self, student_id: UUID, lo_id: str) -> Optional[SM2Data]:
        """Retrieve SM2 data from Cassandra."""
        if not self.circuit_breaker.can_execute():
            return None
        
        if self._session is None:
            return None
        
        try:
            query = """
                SELECT interval_days, repetitions, easiness_factor, next_review_at
                FROM student_sm2_data
                WHERE student_id = %s AND lo_id = %s
            """
            result = self._session.execute(query, (student_id, lo_id))
            row = result.one()
            
            if row is None:
                return None
            
            return SM2Data(
                student_id=student_id,
                lo_id=lo_id,
                interval=row.interval_days,
                repetitions=row.repetitions,
                easiness_factor=row.easiness_factor,
                next_review_at=row.next_review_at,
            )
            
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error("Cassandra get_sm2_data failed", error=str(e))
            return None
    
    async def save_sm2_data(self, data: SM2Data) -> bool:
        """Save SM2 data to Cassandra."""
        if not self.circuit_breaker.can_execute():
            return False
        
        if self._session is None:
            return False
        
        try:
            query = """
                INSERT INTO student_sm2_data
                (student_id, lo_id, interval_days, repetitions, 
                 easiness_factor, last_reviewed_at, next_review_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            self._session.execute(query, (
                data.student_id,
                data.lo_id,
                data.interval,
                data.repetitions,
                data.easiness_factor,
                datetime.utcnow(),
                data.next_review_at,
            ))
            
            self.circuit_breaker.record_success()
            return True
            
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error("Cassandra save_sm2_data failed", error=str(e))
            return False
    
    async def health_check(self) -> bool:
        """Check Cassandra health."""
        if self._session is None:
            return False
        try:
            self._session.execute("SELECT now() FROM system.local")
            return True
        except Exception:
            return False
```


## src/api/__init__.py

```python
"""API layer for AKSRE."""

from .router import api_router

__all__ = ["api_router"]
```

## src/api/router.py

```python
"""Main API router configuration."""

from fastapi import APIRouter

from .state import router as state_router
from .recommendations import router as rec_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(state_router, prefix="/students", tags=["knowledge-state"])
api_router.include_router(rec_router, prefix="/personalization", tags=["recommendations"])
```

## src/api/state.py

```python
"""Knowledge state API endpoints."""

import time
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..config import get_config
from ..engines.bkt_engine import BKTEngine
from ..engines.sm2_scheduler import SM2Scheduler
from ..models.requests import UpdateRequest
from ..models.responses import KnowledgeStateItem, KnowledgeStateResponse, UpdateResponse
from ..repositories.redis_store import RedisKnowledgeStateRepository
from ..repositories.cassandra_store import CassandraKnowledgeStateRepository
from ..services.event_publisher import EventPublisher
from ..utils.errors import NotFoundError, ErrorCode, ValidationError
from ..utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Initialize components
bkt_engine = BKTEngine()
sm2_scheduler = SM2Scheduler()
redis_repo = RedisKnowledgeStateRepository()
cassandra_repo = CassandraKnowledgeStateRepository()
event_publisher = EventPublisher()


async def get_student_or_404(student_id: UUID) -> bool:
    """Validate student exists (placeholder for auth service integration)."""
    # In production, this would call the Identity Service
    return True


@router.get("/{student_id}/knowledge-state")
async def get_knowledge_state(
    student_id: UUID,
    lo_ids: Optional[List[str]] = Query(None),
    request: Request = None,
) -> KnowledgeStateResponse:
    """Get knowledge state for a student.
    
    Returns BKT parameters and mastery status for specified LOs.
    If no LOs specified, returns all tracked LOs (paginated in production).
    """
    start_time = time.time()
    
    # Validate student exists
    await get_student_or_404(student_id)
    
    # Default to empty list if no LOs specified
    target_lo_ids = lo_ids or []
    
    states = []
    for lo_id in target_lo_ids:
        # Try Redis first (hot cache)
        state = await redis_repo.get_state(student_id, lo_id)
        
        # Fallback to Cassandra if not in Redis
        if state is None:
            state = await cassandra_repo.get_state(student_id, lo_id)
            # Backfill to Redis if found
            if state:
                await redis_repo.save_state(state)
        
        if state:
            states.append(KnowledgeStateItem(
                lo_id=state.lo_id,
                p_mastery=state.p_mastery,
                p_learn=state.p_learn,
                p_guess=state.p_guess,
                p_slip=state.p_slip,
                attempt_count=state.attempt_count,
                last_attempt_at=state.last_attempt_at,
                is_mastered=state.is_mastered,
                next_review_at=state.next_review_at,
            ))
    
    latency_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "Knowledge state retrieved",
        student_id=str(student_id),
        lo_count=len(states),
        latency_ms=latency_ms,
    )
    
    return KnowledgeStateResponse(
        student_id=student_id,
        timestamp=datetime.utcnow(),
        states=states,
    )


@router.post("/{student_id}/knowledge-state/update")
async def update_knowledge_state(
    student_id: UUID,
    update: UpdateRequest,
    request: Request = None,
) -> UpdateResponse:
    """Update knowledge state based on a learning interaction.
    
    Processes the interaction through BKT update and SM2 scheduling,
    then persists to Redis (cache) and Cassandra (persistent store).
    """
    from datetime import datetime
    
    start_time = time.time()
    
    # Validate student exists
    await get_student_or_404(student_id)
    
    # Get current state (try Redis, fallback to Cassandra)
    current_state = await redis_repo.get_state(student_id, update.lo_id)
    if current_state is None:
        current_state = await cassandra_repo.get_state(student_id, update.lo_id)
    
    # Create initial state if not found
    if current_state is None:
        current_state = bkt_engine.create_initial_state(student_id, update.lo_id)
        logger.info(
            "Created initial knowledge state",
            student_id=str(student_id),
            lo_id=update.lo_id,
        )
    
    previous_p_mastery = current_state.p_mastery
    
    # Update BKT parameters
    updated_state = bkt_engine.update_parameters(
        current_state,
        update.interaction.correctness,
    )
    
    # Get current SM2 data and calculate next review
    sm2_data = await redis_repo.get_sm2_data(student_id, update.lo_id)
    if sm2_data is None:
        sm2_data = await cassandra_repo.get_sm2_data(student_id, update.lo_id)
    
    new_sm2_data = sm2_scheduler.calculate_next_review(
        student_id,
        update.lo_id,
        update.interaction.correctness,
        sm2_data,
    )
    
    updated_state.next_review_at = new_sm2_data.next_review_at
    
    # Persist to storage
    redis_success = await redis_repo.save_state(updated_state)
    cassandra_success = await cassandra_repo.save_state(updated_state)
    
    if new_sm2_data:
        await redis_repo.save_sm2_data(new_sm2_data)
        await cassandra_repo.save_sm2_data(new_sm2_data)
    
    # Publish event (fire-and-forget)
    event_publisher.publish_knowledge_state_updated(
        student_id=str(student_id),
        lo_id=update.lo_id,
        previous_p_mastery=previous_p_mastery,
        current_p_mastery=updated_state.p_mastery,
        interaction=update.interaction.model_dump(),
        is_mastered=updated_state.is_mastered,
    )
    
    processing_time_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "Knowledge state updated",
        student_id=str(student_id),
        lo_id=update.lo_id,
        previous_p_mastery=round(previous_p_mastery, 4),
        current_p_mastery=round(updated_state.p_mastery, 4),
        is_mastered=updated_state.is_mastered,
        processing_time_ms=processing_time_ms,
    )
    
    return UpdateResponse(
        student_id=student_id,
        lo_id=update.lo_id,
        previous_p_mastery=previous_p_mastery,
        current_p_mastery=updated_state.p_mastery,
        is_mastered=updated_state.is_mastered,
        next_review_at=updated_state.next_review_at,
        processing_time_ms=processing_time_ms,
    )


@router.get("/health/live")
async def liveness_check():
    """Liveness probe for Kubernetes."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_check():
    """Readiness probe for Kubernetes."""
    checks = {}
    
    # Check Redis
    redis_healthy = await redis_repo.health_check()
    checks["redis"] = "up" if redis_healthy else "down"
    
    # Check Cassandra
    cassandra_healthy = await cassandra_repo.health_check()
    checks["cassandra"] = "up" if cassandra_healthy else "down"
    
    all_healthy = all(c == "up" for c in checks.values())
    
    if not all_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "checks": checks},
        )
    
    return {"status": "ready", "checks": checks}
```

## src/api/recommendations.py

```python
"""Recommendation API endpoints."""

import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from ..config import get_config
from ..engines.bkt_engine import BKTEngine
from ..models.requests import RecommendRequest
from ..models.responses import RecommendResponse, RecommendationItem
from ..repositories.redis_store import RedisKnowledgeStateRepository
from ..repositories.cassandra_store import CassandraKnowledgeStateRepository
from ..utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Initialize components
bkt_engine = BKTEngine()
redis_repo = RedisKnowledgeStateRepository()
cassandra_repo = CassandraKnowledgeStateRepository()


@router.post("/recommendations")
async def get_recommendations(
    request: RecommendRequest,
    req: Request = None,
) -> RecommendResponse:
    """Get content recommendations for a student.
    
    Returns ranked list of LOs with predicted success probabilities.
    Currently uses BKT-only predictions (Phase 1 MVP).
    Phase 2 will integrate DKT for hybrid predictions.
    """
    start_time = time.time()
    
    recommendations = []
    
    for lo_id in request.target_lo_ids:
        # Get knowledge state
        state = await redis_repo.get_state(request.student_id, lo_id)
        if state is None:
            state = await cassandra_repo.get_state(request.student_id, lo_id)
        
        if state is None:
            # Use default state for cold start
            state = bkt_engine.create_initial_state(request.student_id, lo_id)
        
        # Calculate predicted success probability
        p_success = bkt_engine.predict_success_probability(state)
        
        # Determine difficulty tier (1-5 based on predicted success)
        if p_success >= 0.8:
            difficulty_tier = 1  # Easy
            reason = "review_ready"
        elif p_success >= 0.6:
            difficulty_tier = 2
            reason = "mastery_building"
        elif p_success >= 0.4:
            difficulty_tier = 3  # Optimal ZPD
            reason = "zpd_optimal"
        elif p_success >= 0.2:
            difficulty_tier = 4
            reason = "challenge_zone"
        else:
            difficulty_tier = 5  # Hard
            reason = "prerequisite_needed"
        
        recommendations.append(RecommendationItem(
            lo_id=lo_id,
            predicted_success_probability=round(p_success, 4),
            bkt_p_mastery=round(state.p_mastery, 4),
            dkt_prediction=None,  # Phase 2: DKT integration
            difficulty_tier=difficulty_tier,
            recommendation_reason=reason,
        ))
    
    # Sort by predicted success (descending) - optimal ZPD items first
    recommendations.sort(key=lambda x: x.predicted_success_probability, reverse=True)
    
    # Limit results
    recommendations = recommendations[:request.limit]
    
    latency_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "Recommendations generated",
        student_id=str(request.student_id),
        count=len(recommendations),
        latency_ms=latency_ms,
    )
    
    return RecommendResponse(
        student_id=request.student_id,
        recommendations=recommendations,
        latency_ms=latency_ms,
    )
```


## src/main.py

```python
"""Main FastAPI application entry point for AKSRE."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.router import api_router
from .config import get_config, load_config
from .services.event_publisher import EventPublisher
from .utils.errors import AKSREError
from .utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("AKSRE starting up", version=get_config().version)
    yield
    # Shutdown
    logger.info("AKSRE shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_config()
    
    # Setup logging
    setup_logging()
    
    app = FastAPI(
        title="AKSRE - Adaptive Knowledge State & Recommendation Engine",
        description="""
        AKSRE provides real-time student knowledge state management, 
        BKT-based mastery inference, and learning interaction processing.
        
        ## Features
        - Bayesian Knowledge Tracing (BKT) for mastery prediction
        - SM-2 spaced repetition scheduling
        - RESTful API for knowledge state updates and queries
        - Hybrid hot/cold storage (Redis + Cassandra)
        """,
        version=config.version,
        docs_url="/docs" if config.debug else None,
        redoc_url="/redoc" if config.debug else None,
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Exception handlers
    @app.exception_handler(AKSREError)
    async def aksre_exception_handler(request: Request, exc: AKSREError):
        logger.error(
            "Application error",
            code=exc.code.value,
            message=exc.message,
            request_path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                }
            },
        )
    
    # Include API router
    app.include_router(api_router)
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "name": "AKSRE",
            "version": config.version,
            "docs": "/docs",
            "health": "/api/v1/students/health/ready",
        }
    
    return app


def main():
    """Main entry point."""
    import uvicorn
    
    config = get_config()
    
    uvicorn.run(
        "aksre.main:create_app",
        host=config.host,
        port=config.port,
        workers=config.workers,
        factory=True,
        log_level=config.log_level.lower(),
        access_log=config.debug,
    )


if __name__ == "__main__":
    main()
```

## Dockerfile

```dockerfile
# AKSRE - Adaptive Knowledge State & Recommendation Engine
# Multi-stage build for optimized production image

# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libev-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir --user -e .

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN groupadd -r aksre && useradd -r -g aksre aksre

# Copy Python packages from builder
COPY --from=builder /root/.local /home/aksre/.local
ENV PATH=/home/aksre/.local/bin:$PATH

# Copy application code
COPY src/ ./src/
COPY config.yaml ./

# Set permissions
RUN chown -R aksre:aksre /app /home/aksre

# Switch to non-root user
USER aksre

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/v1/students/health/ready')" || exit 1

# Run application
CMD ["python", "-m", "uvicorn", "src.main:create_app", "--host", "0.0.0.0", "--port", "8080", "--factory"]
```

## docker-compose.yml

```yaml
version: '3.8'

services:
  aksre:
    build: .
    ports:
      - "8080:8080"
    environment:
      - AKSRE_ENVIRONMENT=development
      - AKSRE_LOG_LEVEL=INFO
      - REDIS_HOST=redis
      - CASSANDRA_HOSTS=cassandra
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    depends_on:
      - redis
      - cassandra
      - kafka
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    networks:
      - aksre-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/v1/students/health/ready"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - aksre-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  cassandra:
    image: cassandra:4.1
    ports:
      - "9042:9042"
    environment:
      - CASSANDRA_KEYSPACE=aksre
      - HEAP_NEWSIZE=2G
      - MAX_HEAP_SIZE=4G
    volumes:
      - cassandra-data:/var/lib/cassandra
    networks:
      - aksre-network
    healthcheck:
      test: ["CMD-SHELL", "nodetool status"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092'
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_JMX_PORT: 9101
      KAFKA_JMX_HOSTNAME: localhost
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@kafka:29093'
      KAFKA_LISTENERS: 'PLAINTEXT://kafka:29092,CONTROLLER://kafka:29093,PLAINTEXT_HOST://0.0.0.0:9092'
      KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_LOG_DIRS: '/tmp/kraft-combined-logs'
      CLUSTER_ID: 'MkU3OEVBNTcwNTJENDM2Qk'
    volumes:
      - kafka-data:/var/lib/kafka/data
    networks:
      - aksre-network
    healthcheck:
      test: ["CMD", "kafka-broker-api-versions", "--bootstrap-server", "localhost:9092"]
      interval: 10s
      timeout: 5s
      retries: 5

  prometheus:
    image: prom/prometheus:v2.47.0
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    networks:
      - aksre-network

  grafana:
    image: grafana/grafana:10.1.0
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro
    networks:
      - aksre-network
    depends_on:
      - prometheus

volumes:
  redis-data:
  cassandra-data:
  kafka-data:
  prometheus-data:
  grafana-data:

networks:
  aksre-network:
    driver: bridge
```


## tests/__init__.py

```python
"""Test suite for AKSRE."""
```

## tests/test_bkt_engine.py

```python
"""Tests for the BKT engine."""

import pytest
from uuid import UUID, uuid4

from aksre.engines.bkt_engine import BKTEngine
from aksre.models.bkt import BKTState, BKTParams


@pytest.fixture
def student_id() -> UUID:
    return uuid4()


@pytest.fixture
def bkt_engine() -> BKTEngine:
    return BKTEngine()


@pytest.fixture
def initial_state(student_id) -> BKTState:
    return BKTState(
        student_id=student_id,
        lo_id="3.NF.A.1",
        p_mastery=0.30,
        p_learn=0.20,
        p_guess=0.15,
        p_slip=0.10,
        attempt_count=0,
        is_mastered=False,
    )


class TestBKTEngine:
    """Test suite for BKT engine."""

    def test_create_initial_state(self, bkt_engine, student_id):
        """Test initial state creation."""
        state = bkt_engine.create_initial_state(student_id, "3.NF.A.1")
        
        assert state.student_id == student_id
        assert state.lo_id == "3.NF.A.1"
        assert state.p_mastery == 0.30
        assert state.p_learn == 0.20
        assert state.p_guess == 0.15
        assert state.p_slip == 0.10
        assert state.attempt_count == 0
        assert state.is_mastered is False

    def test_update_parameters_correct_response(self, bkt_engine, initial_state):
        """Test BKT update after correct response."""
        updated = bkt_engine.update_parameters(initial_state, correctness=1.0)
        
        # Mastery should increase after correct response
        assert updated.p_mastery > initial_state.p_mastery
        assert updated.attempt_count == 1

    def test_update_parameters_incorrect_response(self, bkt_engine, initial_state):
        """Test BKT update after incorrect response."""
        updated = bkt_engine.update_parameters(initial_state, correctness=0.0)
        
        # Mastery should decrease after incorrect response
        assert updated.p_mastery < initial_state.p_mastery
        assert updated.attempt_count == 1

    def test_mastery_threshold(self, bkt_engine, student_id):
        """Test mastery detection with sufficient attempts."""
        # Create state above threshold with enough attempts
        state = BKTState(
            student_id=student_id,
            lo_id="3.NF.A.1",
            p_mastery=0.85,  # Above 0.80 threshold
            p_learn=0.20,
            p_guess=0.15,
            p_slip=0.10,
            attempt_count=5,  # Above min_attempts=3
            is_mastered=False,
        )
        
        result = bkt_engine.compute_mastery(student_id, "3.NF.A.1", state)
        
        assert result.is_mastered is True
        assert result.p_mastery == 0.85

    def test_mastery_not_achieved_without_attempts(self, bkt_engine, student_id):
        """Test that mastery requires minimum attempts."""
        state = BKTState(
            student_id=student_id,
            lo_id="3.NF.A.1",
            p_mastery=0.85,  # Above threshold
            p_learn=0.20,
            p_guess=0.15,
            p_slip=0.10,
            attempt_count=1,  # Below min_attempts=3
            is_mastered=False,
        )
        
        result = bkt_engine.compute_mastery(student_id, "3.NF.A.1", state)
        
        assert result.is_mastered is False

    def test_predict_success_probability(self, bkt_engine, initial_state):
        """Test success probability prediction."""
        p_success = bkt_engine.predict_success_probability(initial_state)
        
        # P(success) = P(L)*(1-P(S)) + (1-P(L))*P(G)
        # = 0.30 * (1-0.10) + (1-0.30) * 0.15
        # = 0.30 * 0.90 + 0.70 * 0.15
        # = 0.27 + 0.105 = 0.375
        expected = 0.30 * 0.90 + 0.70 * 0.15
        assert abs(p_success - expected) < 0.001

    def test_multiple_updates(self, bkt_engine, initial_state):
        """Test multiple sequential updates."""
        state = initial_state
        
        # Multiple correct responses
        for i in range(5):
            state = bkt_engine.update_parameters(state, correctness=1.0)
        
        # Mastery should be achieved
        assert state.p_mastery > 0.80
        assert state.attempt_count == 5

    def test_confidence_increases_with_attempts(self, bkt_engine, student_id):
        """Test confidence increases with more attempts."""
        state = BKTState(
            student_id=student_id,
            lo_id="3.NF.A.1",
            p_mastery=0.50,
            p_learn=0.20,
            p_guess=0.15,
            p_slip=0.10,
            attempt_count=10,
            is_mastered=False,
        )
        
        result = bkt_engine.compute_mastery(student_id, "3.NF.A.1", state)
        
        # Confidence should be 1.0 for 10+ attempts
        assert result.confidence == 1.0
```

## tests/test_api.py

```python
"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from aksre.main import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_liveness(self, client):
        """Test liveness probe."""
        response = client.get("/api/v1/students/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_readiness(self, client):
        """Test readiness probe."""
        response = client.get("/api/v1/students/health/ready")
        # May fail if dependencies unavailable in test
        assert response.status_code in [200, 503]


class TestKnowledgeStateEndpoints:
    """Test knowledge state endpoints."""

    def test_update_knowledge_state(self, client):
        """Test knowledge state update."""
        student_id = str(uuid4())
        
        response = client.post(
            f"/api/v1/students/{student_id}/knowledge-state/update",
            json={
                "lo_id": "3.NF.A.1",
                "interaction": {
                    "content_module_id": str(uuid4()),
                    "correctness": 1.0,
                    "time_spent_seconds": 45,
                    "hints_used": 0,
                },
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["student_id"] == student_id
        assert data["lo_id"] == "3.NF.A.1"
        assert "current_p_mastery" in data
        assert "processing_time_ms" in data

    def test_update_invalid_lo_id(self, client):
        """Test update with invalid LO ID."""
        student_id = str(uuid4())
        
        response = client.post(
            f"/api/v1/students/{student_id}/knowledge-state/update",
            json={
                "lo_id": "",  # Invalid empty LO ID
                "interaction": {
                    "content_module_id": str(uuid4()),
                    "correctness": 1.0,
                    "time_spent_seconds": 45,
                    "hints_used": 0,
                },
            },
        )
        
        assert response.status_code == 422  # Validation error

    def test_get_knowledge_state(self, client):
        """Test getting knowledge state."""
        student_id = str(uuid4())
        
        response = client.get(
            f"/api/v1/students/{student_id}/knowledge-state",
            params={"lo_ids": ["3.NF.A.1", "3.NF.A.2"]},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["student_id"] == student_id
        assert "states" in data
        assert isinstance(data["states"], list)


class TestRecommendationEndpoints:
    """Test recommendation endpoints."""

    def test_get_recommendations(self, client):
        """Test getting recommendations."""
        student_id = str(uuid4())
        
        response = client.post(
            "/api/v1/personalization/recommendations",
            json={
                "student_id": student_id,
                "target_lo_ids": ["3.NF.A.1", "3.NF.A.2", "3.NF.A.3"],
                "limit": 3,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["student_id"] == student_id
        assert "recommendations" in data
        assert len(data["recommendations"]) <= 3
        
        for rec in data["recommendations"]:
            assert "lo_id" in rec
            assert "predicted_success_probability" in rec
            assert "difficulty_tier" in rec
```

## README.md

```markdown
# AKSRE - Adaptive Knowledge State & Recommendation Engine

AKSRE is a core microservice for the Adaptive K-12 Learning Platform, implementing Bayesian Knowledge Tracing (BKT) for real-time student mastery prediction and spaced repetition scheduling.

## Features

- **Bayesian Knowledge Tracing**: Updates P(mastery) using Bayes' rule after each interaction
- **SM-2 Spaced Repetition**: Calculates optimal review intervals
- **Hybrid Storage**: Redis for hot cache (<5ms reads), Cassandra for persistent storage
- **Event Streaming**: Publishes knowledge state changes to Kafka
- **Circuit Breakers**: Fault tolerance for external dependencies

## Quick Start

### Local Development

```bash
# Start dependencies
docker-compose up -d redis cassandra kafka

# Install dependencies
pip install -e ".[dev]"

# Run application
python -m aksre.main
```

### Docker

```bash
docker-compose up --build
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/students/{id}/knowledge-state` | GET | Get knowledge state |
| `/api/v1/students/{id}/knowledge-state/update` | POST | Update from interaction |
| `/api/v1/personalization/recommendations` | POST | Get recommendations |
| `/api/v1/students/health/ready` | GET | Readiness probe |

## Configuration

Edit `config.yaml` or set environment variables:

```yaml
bkt:
  default_params:
    p_l0: 0.30
    p_t: 0.20
```

Environment variables override YAML config:
- `AKSRE_LOG_LEVEL`
- `REDIS_HOST`
- `CASSANDRA_HOSTS`

## Testing

```bash
pytest tests/ -v --cov=src
```

## Architecture

See `architecture-design.md` for detailed specifications.

## License

MIT
```
