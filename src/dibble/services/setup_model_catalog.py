from __future__ import annotations

import json
from typing import Any, Callable
from urllib import error, request

from dibble.models.setup import SetupModelCatalogRequest, SetupModelCatalogResponse

ModelCatalogTransport = Callable[[str, dict[str, str], float], dict[str, Any]]


def fetch_json(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    http_request = request.Request(url=url, headers=headers, method="GET")

    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Model catalog request failed with status {exc.code}: {details}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(
            f"Model catalog request could not be completed: {exc.reason}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Model catalog response was not valid JSON.") from exc


class SetupModelCatalogService:
    def __init__(
        self,
        *,
        transport: ModelCatalogTransport = fetch_json,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    def list_models(
        self, request_model: SetupModelCatalogRequest
    ) -> SetupModelCatalogResponse:
        payload = self._transport(
            f"{request_model.api_base.rstrip('/')}/models",
            headers={
                "Authorization": f"Bearer {request_model.api_key}",
                "Accept": "application/json",
            },
            timeout=self._timeout_seconds,
        )
        raw_models = payload.get("data")
        if not isinstance(raw_models, list):
            raise RuntimeError("Model catalog response did not include a data list.")

        models = sorted(
            {
                model_id
                for item in raw_models
                if isinstance(item, dict)
                for model_id in [item.get("id")]
                if isinstance(model_id, str) and model_id.strip()
            }
        )
        if not models:
            raise RuntimeError("Model catalog response did not include any model ids.")

        return SetupModelCatalogResponse(models=models)
