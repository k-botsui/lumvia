import pytest
from app.config import Settings
from app.local_network import is_lan_origin, lan_address

BASE = {"database_url": "postgresql://localhost/test", "secret_key": "x" * 32, "_env_file": None}


@pytest.mark.parametrize(
    "origin", ["https://10.0.0.3:8443", "https://172.16.4.12:8443", "https://192.168.1.10:8443"]
)
def test_private_wifi_is_explicit_and_https(origin):
    with pytest.raises(ValueError):
        Settings(**BASE, app_url=origin)
    with pytest.raises(ValueError):
        Settings(**BASE, app_url=origin, local_network=True)
    config = Settings(**BASE, app_url=origin, local_network=True, environment="production")
    assert config.storage_backend == "local" and config.app_url == origin


@pytest.mark.parametrize(
    "origin",
    [
        "http://192.168.1.2:8443",
        "https://192.168.1.2",
        "https://8.8.8.8:8443",
        "https://lumvia.example:8443",
        "https://0.0.0.0:8443",
        "https://169.254.1.2:8443",
        "https://192.168.1.2:8443/?token=private",
        "https://user:password@192.168.1.2:8443",
        "https://192.168.1.2:8443/#private",
    ],
)
def test_mobile_cannot_create_public_or_unprotected_origin(origin):
    assert not is_lan_origin(origin)
    with pytest.raises(ValueError):
        Settings(**BASE, app_url=origin, local_network=True, environment="production")


def test_mobile_keeps_database_and_cloud_restrictions():
    with pytest.raises(ValueError):
        lan_address("8.8.8.8")
    with pytest.raises(ValueError):
        Settings(
            **BASE,
            app_url="https://192.168.1.2:8443",
            local_network=True,
            environment="production",
            storage_backend="s3",
        )
