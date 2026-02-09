from src.registry_manager.version import Version


def test_version_smaller():
    assert Version("1.0.0") < Version("1.0.1")
    assert Version("1.0.0") < Version("1.1.0")
    assert Version("1.0.0") < Version("2.0.0")
    assert Version("1.0.0-alpha") < Version("1.0.0")
    assert Version("A") < Version("B")
