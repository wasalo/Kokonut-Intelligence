"""SDK smoke tests — import and instantiate without network calls."""

import sys
from pathlib import Path

# Add sdk/python to path for import
SDK_PATH = Path(__file__).resolve().parent.parent / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))


def test_kokonut_client_import():
    from kokonut import KokonutClient
    from kokonut.client import KokonutError, AuthenticationError

    client = KokonutClient("http://localhost:8055")
    assert client.base_url == "http://localhost:8055"
    assert client.locations is not None
    assert client.farms is not None
    assert client.harvest_events is not None
    assert issubclass(AuthenticationError, KokonutError)


def test_kokonut_types_import():
    from kokonut.types import ListOptions

    opts = ListOptions(limit=10)
    assert opts.limit == 10


def test_kokonut_methods_import():
    from kokonut.methods import LocationMethods, FarmMethods, HarvestEventMethods

    assert LocationMethods is not None
    assert FarmMethods is not None
    assert HarvestEventMethods is not None


if __name__ == "__main__":
    test_kokonut_client_import()
    test_kokonut_types_import()
    test_kokonut_methods_import()
    print("All SDK smoke tests passed ✓")
