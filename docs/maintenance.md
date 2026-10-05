# Maintenance

Dependency and GitHub Actions updates are proposed weekly by Dependabot (the native `uv` ecosystem maintains `uv.lock`), with grouped updates and a small open-PR limit. Review behavior changes and merge only after required CI passes; automatic merging and mandatory human approvals are not configured.

External Actions are pinned to verified full commit SHAs with readable version comments. Update the SHA and comment together. Pinning an Action implementation does not freeze a Rust stable toolchain or every transitive package; committed lockfiles define the resolved test dependencies. Isolated build-backend requirements and clean-wheel consumer dependencies can still resolve separately; these checks do not assert bitwise reproducible builds.

Main should reject force pushes and deletion and require a pull request with the always-running CI checks listed below. No human approval is required. Required checks must not use workflow-level PR path filters, which can leave documentation or dependency PRs pending indefinitely. Keep check names stable or migrate the ruleset when changing them.

Release tags must match package and Action binary versions where applicable. Validate tests, build artifacts, metadata and clean installs before publishing. Python packages use PyPI Trusted Publishing; binary Actions verify the selected release archive against its SHA256SUMS before running it. Never replace assets on an already published release. Versioned integration dependencies are updated explicitly and compatibility is checked before adoption.

Required CI: `Python 3.11`, `Python 3.12` and `Python 3.13`. CI checks the locked environment, wheel install and deterministic CLI reports. Publishing validates the selected tag, tests and builds before the PyPI OIDC job.
