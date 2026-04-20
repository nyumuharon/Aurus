"""Import smoke tests for the initial package skeleton."""

from importlib import import_module

PACKAGES = (
    "aurus",
    "aurus.common",
    "aurus.data",
    "aurus.features",
    "aurus.backtest",
    "aurus.risk",
    "aurus.execution",
    "aurus.ops",
    "aurus.strategy",
)


def test_packages_are_importable() -> None:
    for package_name in PACKAGES:
        assert import_module(package_name).__name__ == package_name


def test_package_exports_are_minimal() -> None:
    root = import_module("aurus")

    assert sorted(root.__all__) == [
        "backtest",
        "common",
        "data",
        "execution",
        "features",
        "ops",
        "risk",
        "strategy",
    ]


def test_placeholder_components_match_package_names() -> None:
    for package_name in PACKAGES[1:]:
        package = import_module(package_name)
        assert package_name.rsplit(".", maxsplit=1)[-1] == package.COMPONENT
