from importlib.metadata import version

import entitylinkage


def test_package_version_matches_distribution_metadata() -> None:
    assert entitylinkage.__version__ == "0.1.0"
    assert version("entitylinkage") == "0.1.0"
