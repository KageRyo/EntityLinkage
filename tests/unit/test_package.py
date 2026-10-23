from importlib.metadata import version

import entitylinkage


def test_package_version_matches_distribution_metadata() -> None:
    assert entitylinkage.__version__ == version("entitylinkage")
