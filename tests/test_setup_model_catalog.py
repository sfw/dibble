from __future__ import annotations

import pytest

from dibble.models.setup import SetupModelCatalogRequest
from dibble.services.setup_model_catalog import SetupModelCatalogService


def test_list_models_returns_sorted_model_ids() -> None:
    service = SetupModelCatalogService(
        transport=lambda url, headers, timeout: {
            "data": [
                {"id": "gpt-4o"},
                {"id": "text-embedding-3-small"},
                {"id": "gpt-4o-mini"},
            ]
        }
    )

    result = service.list_models(
        SetupModelCatalogRequest(
            api_base="https://api.example.com/v1",
            api_key="sk-test",
        )
    )

    assert result.models == [
        "gpt-4o",
        "gpt-4o-mini",
        "text-embedding-3-small",
    ]


def test_list_models_rejects_missing_model_ids() -> None:
    service = SetupModelCatalogService(
        transport=lambda url, headers, timeout: {"data": []}
    )

    with pytest.raises(RuntimeError, match="did not include any model ids"):
        service.list_models(
            SetupModelCatalogRequest(
                api_base="https://api.example.com/v1",
                api_key="sk-test",
            )
        )
