from __future__ import annotations

import logging
import os
import stat
import tomllib
import tomli_w
import types
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

logger = logging.getLogger(__name__)

_UNSET: Any = object()


@dataclass(slots=True)
class Settings:
    database_path: str = "dibble.db"
    app_name: str = "Dibble Adaptive Platform"
    app_version: str = "0.3.0"
    router_plugin: str = "dibble.plugins.defaults.router:build"
    retriever_plugin: str = "dibble.plugins.defaults.retriever:build"
    provider_plugin: str = "dibble.plugins.defaults.provider:build"
    validator_plugin: str = "dibble.plugins.defaults.validator:build"
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = 20.0
    llm_allow_mock_fallback: bool = True
    llm_secondary_api_base: str | None = None
    llm_secondary_api_key: str | None = None
    llm_secondary_model: str | None = None
    llm_secondary_timeout_seconds: float | None = None
    llm_circuit_breaker_threshold: int = 2
    llm_circuit_breaker_cooldown_seconds: float = 30.0
    llm_selection_strategy: str = "ordered"
    prompt_library_version: str = "1.0"
    prompt_experiment_enabled: bool = False
    prompt_adaptive_selection_enabled: bool = False
    prompt_variant_override: str | None = None
    embedding_api_base: str = "https://api.openai.com/v1"
    embedding_api_key: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int = 256
    embedding_timeout_seconds: float = 15.0
    embedding_allow_local_fallback: bool = True
    auth_enabled: bool = False
    auth_token_secret: str | None = None
    auth_token_issuer: str = "dibble"
    auth_token_ttl_seconds: int = 3600
    auth_refresh_ttl_seconds: int = 604800
    generation_cache_ttl_seconds: int = 3600
    predictive_warm_inline_process_limit: int = 2


# ---------------------------------------------------------------------------
# Type introspection — derived once from the dataclass
# ---------------------------------------------------------------------------

_TYPE_HINTS: dict[str, Any] = get_type_hints(Settings)


def _base_type(hint: Any) -> type:
    """Extract the concrete scalar type from a type hint."""
    origin = get_origin(hint)
    if origin is tuple:
        return tuple
    if origin is types.UnionType:
        non_none = [a for a in get_args(hint) if a is not type(None)]
        return non_none[0] if non_none else str
    return hint


def _is_optional(hint: Any) -> bool:
    origin = get_origin(hint)
    if origin is types.UnionType:
        return type(None) in get_args(hint)
    return False


# ---------------------------------------------------------------------------
# TOML section → Settings field-name prefix mapping
# ---------------------------------------------------------------------------

_SECTION_MAP: dict[str, str] = {
    "plugins": "_{key}_plugin",  # router → router_plugin
    "llm": "llm_{key}",
    "llm.secondary": "llm_secondary_{key}",
    "prompts": "prompt_{key}",
    "embedding": "embedding_{key}",
    "auth": "auth_{key}",
    "cache": "{key}",  # keys are already fully qualified
    "performance": "{key}",
}

_SETTINGS_FIELDS: set[str] = {f.name for f in fields(Settings)}


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------


def dibble_dir() -> Path:
    """Return ``~/.dibble/`` without creating it."""
    return Path.home() / ".dibble"


def ensure_dibble_dir() -> Path:
    """Return ``~/.dibble/``, creating it (mode 0700) if absent."""
    path = dibble_dir()
    if not path.exists():
        path.mkdir(mode=0o700, parents=True)
    return path


# ---------------------------------------------------------------------------
# TOML loading
# ---------------------------------------------------------------------------


def _flatten_toml(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten a sectioned TOML dict into Settings field names."""
    flat: dict[str, Any] = {}

    for key, value in raw.items():
        if isinstance(value, dict):
            continue  # handled below via sections
        flat[key] = value

    for section, pattern in _SECTION_MAP.items():
        parts = section.split(".")
        node: Any = raw
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                node = None
                break
            node = node[part]
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if isinstance(value, dict):
                continue  # nested sub-tables handled by deeper entries
            if pattern == "_{key}_plugin":
                field_name = f"{key}_plugin"
            else:
                field_name = pattern.format(key=key)
            if field_name in _SETTINGS_FIELDS:
                flat[field_name] = value

    return flat


# ---------------------------------------------------------------------------
# TOML writing
# ---------------------------------------------------------------------------

# Reverse mapping: Settings field name → (section, key_in_section)
_FIELD_TO_SECTION: dict[str, tuple[str, str]] = {}
for _section, _pattern in _SECTION_MAP.items():
    # We populate this lazily per-field below in _unflatten_to_toml
    pass  # built dynamically because patterns vary


def _unflatten_to_toml(flat: dict[str, Any]) -> dict[str, Any]:
    """Convert a flat dict of Settings field names into a sectioned TOML dict.

    Inverse of ``_flatten_toml``.
    """
    result: dict[str, Any] = {}

    # Sort sections by prefix length descending so more-specific patterns
    # (e.g. "llm.secondary" → "llm_secondary_") match before shorter ones
    # (e.g. "llm" → "llm_").
    sorted_sections = sorted(
        _SECTION_MAP.items(),
        key=lambda item: len(item[1].split("{key}")[0]),
        reverse=True,
    )

    for field_name, value in flat.items():
        placed = False
        for section, pattern in sorted_sections:
            if pattern == "_{key}_plugin":
                if field_name.endswith("_plugin"):
                    key = field_name.removesuffix("_plugin")
                    _set_nested(result, section, key, value)
                    placed = True
                    break
            elif pattern == "{key}":
                continue
            else:
                prefix = pattern.split("{key}")[0]
                if field_name.startswith(prefix):
                    key = field_name[len(prefix) :]
                    _set_nested(result, section, key, value)
                    placed = True
                    break

        if not placed:
            result[field_name] = value

    return result


def _set_nested(d: dict[str, Any], section: str, key: str, value: Any) -> None:
    """Set ``d[section_parts...][key] = value``, creating intermediate dicts."""
    parts = section.split(".")
    node = d
    for part in parts:
        if part not in node:
            node[part] = {}
        node = node[part]
    # Convert tuples to lists for TOML serialization
    if isinstance(value, tuple):
        value = list(value)
    node[key] = value


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *updates* into *base*, returning a new dict."""
    merged = dict(base)
    for key, value in updates.items():
        if value is None:
            merged.pop(key, None)
            continue
        if isinstance(value, dict):
            existing = merged.get(key)
            merged[key] = _deep_merge(
                existing if isinstance(existing, dict) else {}, value
            )
            continue
        merged[key] = value
    return merged


def _prune_empty_tables(value: Any) -> Any:
    """Remove empty nested TOML tables after merge/delete operations."""
    if not isinstance(value, dict):
        return value

    pruned: dict[str, Any] = {}
    for key, child in value.items():
        cleaned = _prune_empty_tables(child)
        if cleaned is None or cleaned == {}:
            continue
        pruned[key] = cleaned
    return pruned


def write_config_toml(updates: dict[str, Any], *, path: Path | None = None) -> Path:
    """Merge *updates* (flat Settings field names) into ``~/.dibble/config.toml``.

    Creates ``~/.dibble/`` if absent.  Sets file permissions to ``0o600``.
    Returns the path written.
    """
    if path is None:
        path = ensure_dibble_dir() / "config.toml"

    # Read existing TOML (sectioned, not flattened)
    existing: dict[str, Any] = {}
    if path.is_file():
        with path.open("rb") as fh:
            existing = tomllib.load(fh)

    # Convert flat updates to sectioned structure, then merge
    sectioned_updates = _unflatten_to_toml(updates)
    merged = _prune_empty_tables(_deep_merge(existing, sectioned_updates))

    with path.open("wb") as fh:
        tomli_w.dump(merged, fh)

    path.chmod(0o600)
    return path


def _check_permissions(path: Path) -> None:
    """Warn if the config file is world-readable."""
    try:
        mode = path.stat().st_mode
        if mode & stat.S_IROTH:
            logger.warning(
                "%s is world-readable. Consider: chmod 600 %s",
                path,
                path,
            )
    except OSError:
        pass


def _load_toml_config(path: Path | None = None) -> dict[str, Any]:
    """Read ``~/.dibble/config.toml`` and return flattened Settings overrides.

    Returns an empty dict when the file does not exist.
    """
    if path is None:
        path = dibble_dir() / "config.toml"

    if not path.is_file():
        return {}

    _check_permissions(path)

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    return _flatten_toml(raw)


# ---------------------------------------------------------------------------
# Type coercion helpers
# ---------------------------------------------------------------------------


def _coerce(field_name: str, value: Any) -> Any:
    """Coerce a TOML/env value to match the Settings field type."""
    if value is None:
        return value

    # Expand ~ in paths
    if field_name == "database_path" and isinstance(value, str) and "~" in value:
        return str(Path(value).expanduser())

    return value


# ---------------------------------------------------------------------------
# Env-var reading
# ---------------------------------------------------------------------------

# Fields not configurable via environment variables.
_ENV_EXCLUDED: set[str] = {"app_name", "app_version"}

# Fields whose env-var name doesn't follow the DIBBLE_{FIELD_UPPER} pattern.
_ENV_NAME_OVERRIDES: dict[str, str] = {
    "prompt_variant_override": "DIBBLE_PROMPT_VARIANT",
}


def _env_name(field_name: str) -> str:
    if field_name in _ENV_NAME_OVERRIDES:
        return _ENV_NAME_OVERRIDES[field_name]
    return f"DIBBLE_{field_name.upper()}"


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _get_csv_env(name: str) -> tuple[str, ...]:
    value = os.getenv(name, "")
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _read_env_overrides() -> dict[str, Any]:
    """Return only Settings fields that have an explicit env-var set."""
    overrides: dict[str, Any] = {}

    for f in fields(Settings):
        if f.name in _ENV_EXCLUDED:
            continue
        env = _env_name(f.name)
        raw = os.getenv(env)
        if raw is None:
            continue

        hint = _TYPE_HINTS[f.name]
        base = _base_type(hint)

        if base is bool:
            overrides[f.name] = _get_bool_env(env, False)
        elif base is int:
            overrides[f.name] = int(raw)
        elif base is float:
            if _is_optional(hint) and not raw:
                overrides[f.name] = None
            else:
                overrides[f.name] = float(raw)
        elif base is tuple:
            overrides[f.name] = _get_csv_env(env)
        else:
            overrides[f.name] = raw

    return overrides


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_settings(*, config_path: Path | None = _UNSET) -> Settings:  # type: ignore[assignment]
    """Build ``Settings`` with precedence: env vars > TOML > dataclass defaults.

    Pass ``config_path`` to override the TOML file location (useful for tests).
    Pass ``config_path=None`` to skip TOML loading entirely.
    """
    # Layer 1: TOML overrides (skip if caller passes None explicitly)
    if config_path is _UNSET:
        toml_overrides = _load_toml_config()
    elif config_path is None:
        toml_overrides = {}
    else:
        toml_overrides = _load_toml_config(config_path)

    # Layer 2: env-var overrides
    env_overrides = _read_env_overrides()

    # Merge: defaults ← toml ← env
    merged: dict[str, Any] = {}
    for f in fields(Settings):
        if f.name in env_overrides:
            merged[f.name] = env_overrides[f.name]
        elif f.name in toml_overrides:
            merged[f.name] = _coerce(f.name, toml_overrides[f.name])
        # else: leave unset → dataclass default

    # Embedding API key fallback: inherit from LLM key if not explicitly set
    if "embedding_api_key" not in merged:
        llm_key = merged.get("llm_api_key") or toml_overrides.get("llm_api_key")
        if llm_key:
            merged["embedding_api_key"] = llm_key

    # Database path default: ~/.dibble/dibble.db when loaded via get_settings()
    if "database_path" not in merged:
        merged["database_path"] = str(ensure_dibble_dir() / "dibble.db")
    elif "~" in str(merged.get("database_path", "")):
        merged["database_path"] = str(Path(merged["database_path"]).expanduser())

    return Settings(**merged)
