"""Resolve the source revision the current process is actually running.

Kept free of any Streamlit import so it can be unit tested without a running
app. Never raises -- every lookup (environment, git subprocess, package
metadata) is wrapped so a missing/broken source degrades to "unavailable"
instead of crashing the System Status page.
"""

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping, Optional

REVISION_SOURCE_ENVIRONMENT = "environment"
REVISION_SOURCE_GIT = "git"
REVISION_SOURCE_PACKAGE = "package"
REVISION_SOURCE_UNAVAILABLE = "unavailable"

# Contract this app defines for whoever manages deployment (e.g. via
# Streamlit Community Cloud's app-level environment/secrets settings) to
# declare the deployed revision explicitly. Not assumed to be pre-populated
# by any hosting platform -- only used when actually present and valid.
ENV_VERSION_KEY = "CRM_APP_VERSION"
ENV_COMMIT_SHA_KEY = "CRM_APP_COMMIT_SHA"
ENV_BRANCH_KEY = "CRM_APP_BRANCH"
ENV_BUILD_TIMESTAMP_KEY = "CRM_APP_BUILD_TIMESTAMP"

# Inert today (this repo has no pyproject/setup packaging metadata) -- kept
# so a future packaged build is picked up automatically via importlib.metadata.
_PACKAGE_NAME = "github-sales-dashboard"

# Only a full SHA-1 (40 hex) or SHA-256 (64 hex) counts as a deployment
# identity strong enough to compare against a target commit -- an abbreviated
# SHA is ambiguous (ties to more than one real commit) and must never be
# accepted as if it proved a specific deployed revision.
_FULL_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_SHORT_SHA_LEN = 7
_GIT_TIMEOUT_SECONDS = 3

_BRANCH_MAX_LEN = 128
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")

_VERSION_MAX_LEN = 64
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")

# Generous enough for any ISO 8601 timestamp with microseconds and a UTC
# offset (e.g. "2026-07-20T10:00:00.123456+07:00" is 33 chars) while still
# bounding the input before it ever reaches the parser.
_BUILD_TIMESTAMP_MAX_LEN = 40

GitRunner = Callable[[list, Path], Optional[str]]


def _has_control_chars(text: str) -> bool:
    return any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in text)


def _is_whitespace_wrapped(text: str) -> bool:
    # Catches leading/trailing space, tab, newline, CR, etc. Deliberately
    # checked against the RAW value -- stripping first (as this module used
    # to) hides exactly the malformed input this guards against.
    return text != text.strip()


def _valid_sha(value) -> Optional[str]:
    # SHA normalization (trim + lowercase before validating) is an
    # intentional, already-approved exception: a git SHA has no other
    # legitimate whitespace-adjacent formatting concern once its charset is
    # restricted to hex digits.
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or not _FULL_SHA_RE.fullmatch(text):
        return None
    return text


def _valid_branch(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text or _is_whitespace_wrapped(text):
        return None
    if len(text) > _BRANCH_MAX_LEN:
        return None
    if not _BRANCH_RE.fullmatch(text):
        return None
    if text.startswith("/") or text.endswith("/"):
        return None
    if "//" in text or ".." in text:
        return None
    return text


def _valid_version(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text or _is_whitespace_wrapped(text):
        return None
    if len(text) > _VERSION_MAX_LEN:
        return None
    if not _VERSION_RE.fullmatch(text):
        return None
    return text


def _valid_build_timestamp(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text or _is_whitespace_wrapped(text):
        return None
    if len(text) > _BUILD_TIMESTAMP_MAX_LEN:
        return None
    if _has_control_chars(text):
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return text


def _run_git(args: list, cwd: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _safe_call_git(run_git: GitRunner, args: list, cwd: Path) -> Optional[str]:
    # Defense in depth: even a caller-supplied run_git that misbehaves (raises
    # instead of returning None) must not be able to crash resolution.
    try:
        return run_git(args, cwd)
    except Exception:
        return None


def _package_version() -> Optional[str]:
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - stdlib always available on py3.8+
        return None
    try:
        return version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return None
    except Exception:
        return None


def resolve_app_revision(
    *,
    repo_root: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
    run_git: Optional[GitRunner] = None,
) -> dict:
    """Best-effort identification of the revision this process is running.

    Priority: explicit environment contract > git metadata of this working
    copy > installed package metadata > unavailable. Never guesses a SHA and
    never calls out to GitHub -- only reflects what this process can see
    locally, which is the only thing that proves what is actually running.
    """
    repo_root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    env = env if env is not None else os.environ
    run_git = run_git or _run_git

    env_sha = _valid_sha(env.get(ENV_COMMIT_SHA_KEY))
    branch = _valid_branch(env.get(ENV_BRANCH_KEY))
    build_timestamp = _valid_build_timestamp(env.get(ENV_BUILD_TIMESTAMP_KEY))

    commit_sha: Optional[str] = None
    short_sha: Optional[str] = None
    source = REVISION_SOURCE_UNAVAILABLE

    if env_sha:
        commit_sha = env_sha
        short_sha = env_sha[:_SHORT_SHA_LEN]
        source = REVISION_SOURCE_ENVIRONMENT
    else:
        git_marker = repo_root / ".git"
        if git_marker.exists():
            git_sha = _valid_sha(_safe_call_git(run_git, ["rev-parse", "HEAD"], repo_root))
            if git_sha:
                commit_sha = git_sha
                short_sha = git_sha[:_SHORT_SHA_LEN]
                source = REVISION_SOURCE_GIT
                if branch is None:
                    git_branch = _valid_branch(
                        _safe_call_git(run_git, ["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
                    )
                    if git_branch and git_branch != "HEAD":
                        branch = git_branch

    app_version = _valid_version(env.get(ENV_VERSION_KEY))
    if not app_version:
        package_version = _valid_version(_package_version())
        if package_version:
            app_version = package_version
            if source == REVISION_SOURCE_UNAVAILABLE:
                source = REVISION_SOURCE_PACKAGE

    return {
        "app_version": app_version,
        "commit_sha": commit_sha,
        "short_sha": short_sha,
        "branch": branch,
        "source": source,
        "build_timestamp": build_timestamp,
    }
