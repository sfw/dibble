from dibble.bootstrap import build_application_services
from dibble.config import Settings


def test_plugin_loader_supports_custom_router(tmp_path):
    settings = Settings(
        database_path=str(tmp_path / "plugins.db"),
        router_plugin="tests.fake_plugins:build_router",
        retriever_plugin="tests.fake_plugins:build_retriever",
        provider_plugin="tests.fake_plugins:build_provider",
        validator_plugin="tests.fake_plugins:build_validator",
    )

    services = build_application_services(settings, settings_loader=lambda: settings)

    assert services.router_plugin.__class__.__name__ == "CalibratedRouter"
    assert (
        services.router_plugin.base_router.__class__.__name__ == "AlwaysReteachRouter"
    )
