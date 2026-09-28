import re
from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "publish.yml"


def _load_publish_workflow() -> dict:
    assert WORKFLOW_PATH.is_file(), "PyPI publishing workflow is missing"
    with WORKFLOW_PATH.open(encoding="utf-8") as stream:
        return yaml.load(stream, Loader=yaml.BaseLoader)


def test_pypi_publishing_runs_only_for_published_releases() -> None:
    workflow = _load_publish_workflow()

    assert workflow["on"] == {"release": {"types": ["published"]}}


def test_only_the_pypi_publish_job_receives_oidc_permission() -> None:
    workflow = _load_publish_workflow()
    jobs = workflow["jobs"]
    build = jobs["build"]
    publish = jobs["publish"]

    assert "id-token" not in workflow.get("permissions", {})
    assert "id-token" not in build.get("permissions", {})
    assert publish["needs"] == "build"
    assert publish["environment"]["name"] == "pypi"
    assert publish["permissions"]["id-token"] == "write"


def test_publish_job_uses_a_sha_pinned_pypa_action() -> None:
    workflow = _load_publish_workflow()
    publish_steps = workflow["jobs"]["publish"]["steps"]
    action_ref = next(
        step["uses"]
        for step in publish_steps
        if step.get("uses", "").startswith("pypa/gh-action-pypi-publish@")
    )

    assert re.fullmatch(r"pypa/gh-action-pypi-publish@[0-9a-f]{40}", action_ref)


def test_release_tag_matches_project_version_before_publishing() -> None:
    workflow = _load_publish_workflow()
    build_steps = workflow["jobs"]["build"]["steps"]
    version_check = next(
        step["run"]
        for step in build_steps
        if step.get("name") == "Verify release tag matches project version"
    )

    assert "GITHUB_REF_NAME" in version_check
    assert "uv version --short" in version_check
