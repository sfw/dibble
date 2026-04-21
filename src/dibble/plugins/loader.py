from __future__ import annotations

from inspect import Parameter, signature
from importlib import import_module
from typing import Any, Callable

from dibble.config import Settings
from dibble.plugins.contracts import GenerationPlugins, ModalityPlugins


def load_object(path: str) -> Any:
    module_path, object_name = path.split(":", 1)
    module = import_module(module_path)
    return getattr(module, object_name)


def _build_with_supported_kwargs(factory: Callable[..., Any], **kwargs: Any) -> Any:
    parameters = signature(factory).parameters.values()
    if any(parameter.kind == Parameter.VAR_KEYWORD for parameter in parameters):
        return factory(**kwargs)

    supported_kwargs = {
        name: value
        for name, value in kwargs.items()
        if name in signature(factory).parameters
    }
    return factory(**supported_kwargs)


def build_generation_plugins(
    settings: Settings, *, outcome_store: Any, connection: Any
) -> GenerationPlugins:
    router_factory: Callable[[], Any] = load_object(settings.router_plugin)
    retriever_factory: Callable[..., Any] = load_object(settings.retriever_plugin)
    provider_factory: Callable[..., Any] = load_object(settings.provider_plugin)
    validator_factory: Callable[[], Any] = load_object(settings.validator_plugin)

    return GenerationPlugins(
        router=_build_with_supported_kwargs(router_factory, settings=settings),
        retriever=_build_with_supported_kwargs(
            retriever_factory,
            settings=settings,
            outcome_store=outcome_store,
            connection=connection,
        ),
        provider=_build_with_supported_kwargs(
            provider_factory, settings=settings, connection=connection
        ),
        validator=_build_with_supported_kwargs(validator_factory, settings=settings),
    )


def build_modality_plugins() -> ModalityPlugins:
    plugin_paths = {
        "text": "dibble.plugins.modalities.text:build",
        "narrative": "dibble.plugins.modalities.narrative:build",
        "diagram": "dibble.plugins.modalities.diagram:build",
    }
    return ModalityPlugins(
        plugins={
            plugin_id: load_object(factory_path)()
            for plugin_id, factory_path in plugin_paths.items()
        }
    )
