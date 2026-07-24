import ast
import subprocess
from pathlib import Path

import app_revision
from app_revision import (
    ENV_BRANCH_KEY,
    ENV_BUILD_TIMESTAMP_KEY,
    ENV_COMMIT_SHA_KEY,
    ENV_VERSION_KEY,
    REVISION_SOURCE_ENVIRONMENT,
    REVISION_SOURCE_GIT,
    REVISION_SOURCE_PACKAGE,
    REVISION_SOURCE_UNAVAILABLE,
    _run_git,
    _valid_branch,
    _valid_build_timestamp,
    _valid_sha,
    _valid_version,
    resolve_app_revision,
)


FULL_SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
OTHER_FULL_SHA = "0011223344556677889900112233445566778899"
SHA256_SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678a1b2c3d4e5f60718293a4b5c"

assert len(FULL_SHA) == 40
assert len(OTHER_FULL_SHA) == 40
assert len(SHA256_SHA) == 64


class RecordingEnv(dict):
    """Records every key looked up via .get() so tests can prove the
    resolver only ever reads its four whitelisted contract keys."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.accessed_keys: list = []

    def get(self, key, default=None):
        self.accessed_keys.append(key)
        return super().get(key, default)


def raising_run_git(args, cwd):
    raise AssertionError(f"run_git must not be called when .git is absent (got {args!r} for {cwd!r})")


# 1. Reads a valid full SHA from environment.
def test_reads_valid_full_sha_from_environment(tmp_path):
    env = {ENV_COMMIT_SHA_KEY: FULL_SHA}
    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)

    assert result["commit_sha"] == FULL_SHA
    assert result["source"] == REVISION_SOURCE_ENVIRONMENT


# 2. Whitespace around the SHA is trimmed before validation.
def test_environment_sha_whitespace_is_trimmed_before_validation(tmp_path):
    env = {ENV_COMMIT_SHA_KEY: f"  {FULL_SHA}\n"}
    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)

    assert result["commit_sha"] == FULL_SHA
    assert result["source"] == REVISION_SOURCE_ENVIRONMENT


# 3. Malformed SHAs are rejected outright (fall through to unavailable here
# since there is no git/package fallback in this scenario). Only exactly 40
# (SHA-1) or 64 (SHA-256) hex chars count -- abbreviated SHAs are ambiguous
# and must never be accepted as a full deployment identity.
MALFORMED_SHAS = [
    "not-a-sha",
    "abc123",  # too short
    "g1b2c3d4e5f60718293a4b5c6d7e8f9012345678",  # non-hex character
    "a1b2 c3d4e5f60718293a4b5c6d7e8f9012345678",  # internal whitespace
    "",
    "   ",
    FULL_SHA[:7],  # abbreviated, 7 hex chars
    FULL_SHA[:8],  # abbreviated, 8 hex chars
    FULL_SHA[:12],  # abbreviated, 12 hex chars
    FULL_SHA[:39],  # one short of a full SHA-1
    FULL_SHA + "a",  # one over a full SHA-1 (41 chars)
    SHA256_SHA[:63],  # one short of a full SHA-256
    SHA256_SHA + "a",  # one over a full SHA-256 (65 chars)
]


def test_malformed_sha_is_rejected(tmp_path):
    for malformed in MALFORMED_SHAS:
        env = {ENV_COMMIT_SHA_KEY: malformed}
        result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)

        assert result["commit_sha"] is None, f"expected rejection for {malformed!r}"
        assert result["source"] == REVISION_SOURCE_UNAVAILABLE, f"expected rejection for {malformed!r}"


# Full SHA-256 (64 hex chars) is also accepted, not just SHA-1 (40 hex chars).
def test_reads_valid_sha256_length_sha_from_environment(tmp_path):
    env = {ENV_COMMIT_SHA_KEY: SHA256_SHA}
    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)

    assert result["commit_sha"] == SHA256_SHA
    assert result["short_sha"] == SHA256_SHA[:7]
    assert result["source"] == REVISION_SOURCE_ENVIRONMENT


# An abbreviated env SHA is rejected and resolution falls back to git, exactly
# like the "environment absent" case -- an invalid override must not block
# the fallback chain.
def test_abbreviated_env_sha_falls_back_to_git(tmp_path):
    (tmp_path / ".git").mkdir()
    env = {ENV_COMMIT_SHA_KEY: FULL_SHA[:12]}

    def fake_run_git(args, cwd):
        if args == ["rev-parse", "HEAD"]:
            return OTHER_FULL_SHA
        return None

    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=fake_run_git)

    assert result["commit_sha"] == OTHER_FULL_SHA
    assert result["source"] == REVISION_SOURCE_GIT


def test_valid_sha_helper_rejects_abbreviated_hex_directly():
    assert _valid_sha(FULL_SHA[:12]) is None
    assert _valid_sha(FULL_SHA) == FULL_SHA
    assert _valid_sha(SHA256_SHA) == SHA256_SHA


# 4. Short SHA is derived correctly.
def test_short_sha_is_first_seven_chars():
    env = {ENV_COMMIT_SHA_KEY: FULL_SHA}
    result = resolve_app_revision(repo_root=Path("unused"), env=env, run_git=raising_run_git)

    assert result["short_sha"] == FULL_SHA[:7]
    assert FULL_SHA.startswith(result["short_sha"])


# 5. Environment takes priority over git even when both resolve.
def test_environment_takes_priority_over_git(tmp_path):
    (tmp_path / ".git").mkdir()
    env = {ENV_COMMIT_SHA_KEY: FULL_SHA}

    def fake_run_git(args, cwd):
        return OTHER_FULL_SHA if args[:2] == ["rev-parse", "HEAD"] else "main"

    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=fake_run_git)

    assert result["commit_sha"] == FULL_SHA
    assert result["source"] == REVISION_SOURCE_ENVIRONMENT


# 6. Falls back to git metadata when environment provides nothing.
def test_falls_back_to_git_metadata_when_environment_absent(tmp_path):
    (tmp_path / ".git").mkdir()

    def fake_run_git(args, cwd):
        assert cwd == tmp_path
        if args == ["rev-parse", "HEAD"]:
            return OTHER_FULL_SHA
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return "feature/x"
        raise AssertionError(f"unexpected git args: {args}")

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=fake_run_git)

    assert result["commit_sha"] == OTHER_FULL_SHA
    assert result["short_sha"] == OTHER_FULL_SHA[:7]
    assert result["branch"] == "feature/x"
    assert result["source"] == REVISION_SOURCE_GIT


# ---------------------------------------------------------------------------
# Git-derived branch must pass through the same _valid_branch() validator as
# CRM_APP_BRANCH -- a malformed `git rev-parse --abbrev-ref HEAD` result must
# never leak into the result dict, and must never break commit/version/
# build-timestamp resolution.
# ---------------------------------------------------------------------------

def _git_runner_returning(sha, branch_value):
    def fake_run_git(args, cwd):
        if args == ["rev-parse", "HEAD"]:
            return sha
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return branch_value
        return None

    return fake_run_git


def test_git_branch_valid_is_used(tmp_path):
    (tmp_path / ".git").mkdir()
    result = resolve_app_revision(
        repo_root=tmp_path, env={}, run_git=_git_runner_returning(OTHER_FULL_SHA, "feature/nice-branch")
    )

    assert result["branch"] == "feature/nice-branch"
    assert result["commit_sha"] == OTHER_FULL_SHA
    assert result["source"] == REVISION_SOURCE_GIT


def test_git_branch_with_spaces_is_rejected(tmp_path):
    (tmp_path / ".git").mkdir()
    result = resolve_app_revision(
        repo_root=tmp_path, env={}, run_git=_git_runner_returning(OTHER_FULL_SHA, "bad branch with spaces")
    )

    assert result["branch"] is None
    # An invalid branch must not take down commit resolution.
    assert result["commit_sha"] == OTHER_FULL_SHA
    assert result["source"] == REVISION_SOURCE_GIT


def test_git_branch_with_control_character_is_rejected(tmp_path):
    (tmp_path / ".git").mkdir()
    for bad_branch in ["feature\nx", "feature\tx", "feature\x00x"]:
        result = resolve_app_revision(
            repo_root=tmp_path, env={}, run_git=_git_runner_returning(OTHER_FULL_SHA, bad_branch)
        )
        assert result["branch"] is None, f"expected rejection for {bad_branch!r}"
        assert result["commit_sha"] == OTHER_FULL_SHA


def test_git_branch_with_slash_dotdot_variants_is_rejected(tmp_path):
    (tmp_path / ".git").mkdir()
    for bad_branch in ["/main", "main/", "feature//x", "feature/../x", ".."]:
        result = resolve_app_revision(
            repo_root=tmp_path, env={}, run_git=_git_runner_returning(OTHER_FULL_SHA, bad_branch)
        )
        assert result["branch"] is None, f"expected rejection for {bad_branch!r}"
        assert result["commit_sha"] == OTHER_FULL_SHA


def test_git_branch_invalid_does_not_raise(tmp_path):
    (tmp_path / ".git").mkdir()
    result = resolve_app_revision(
        repo_root=tmp_path, env={}, run_git=_git_runner_returning(OTHER_FULL_SHA, "bad branch with spaces")
    )
    assert result["branch"] is None


def test_git_detached_head_sentinel_is_still_excluded(tmp_path):
    (tmp_path / ".git").mkdir()
    result = resolve_app_revision(
        repo_root=tmp_path, env={}, run_git=_git_runner_returning(OTHER_FULL_SHA, "HEAD")
    )
    # "HEAD" is a syntactically valid branch-charset string but is the
    # detached-HEAD sentinel, not a real branch name -- must stay excluded.
    assert result["branch"] is None
    assert result["commit_sha"] == OTHER_FULL_SHA
    assert result["source"] == REVISION_SOURCE_GIT


# 7. A failing git command (non-zero exit / injected runner failure) never
# raises out of resolve_app_revision.
def test_git_command_failure_does_not_raise(tmp_path):
    (tmp_path / ".git").mkdir()

    def failing_run_git(args, cwd):
        raise RuntimeError("git exploded")

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=failing_run_git)

    assert result["commit_sha"] is None
    assert result["source"] == REVISION_SOURCE_UNAVAILABLE


def test_run_git_swallows_nonzero_exit(monkeypatch, tmp_path):
    class FakeCompleted:
        returncode = 128
        stdout = ""

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: FakeCompleted()
    )
    assert _run_git(["rev-parse", "HEAD"], tmp_path) is None


# 8. A git timeout never raises out of resolve_app_revision, at either the
# default runner level or via an injected runner that itself times out.
def test_run_git_swallows_timeout(monkeypatch, tmp_path):
    def fake_subprocess_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=3)

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    assert _run_git(["rev-parse", "HEAD"], tmp_path) is None


def test_resolve_app_revision_survives_injected_runner_timeout(tmp_path):
    (tmp_path / ".git").mkdir()

    def timing_out_run_git(args, cwd):
        raise subprocess.TimeoutExpired(cmd="git", timeout=3)

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=timing_out_run_git)

    assert result["commit_sha"] is None
    assert result["source"] == REVISION_SOURCE_UNAVAILABLE


# 9. No git executable / no .git directory both resolve to unavailable, and
# a missing .git must short-circuit without even invoking the git runner.
def test_missing_git_executable_returns_none(monkeypatch, tmp_path):
    def missing_executable(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(subprocess, "run", missing_executable)
    assert _run_git(["rev-parse", "HEAD"], tmp_path) is None


def test_no_git_directory_returns_unavailable_without_calling_git(tmp_path, monkeypatch):
    monkeypatch.setattr(app_revision, "_package_version", lambda: None)

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=raising_run_git)

    assert result["commit_sha"] is None
    assert result["app_version"] is None
    assert result["source"] == REVISION_SOURCE_UNAVAILABLE


# 10. No environment/secret leakage: only the four whitelisted keys are ever
# read, and no unrelated value can end up in the returned dict.
def test_does_not_leak_unrelated_environment_values(tmp_path):
    env = RecordingEnv(
        {
            ENV_COMMIT_SHA_KEY: FULL_SHA,
            "SUPER_SECRET_TOKEN": "sk-should-never-appear",
            "DATABASE_URL": "postgres://user:pass@host/db",
        }
    )

    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)

    serialized = repr(result)
    assert "sk-should-never-appear" not in serialized
    assert "postgres://user:pass@host/db" not in serialized
    assert set(env.accessed_keys) <= {
        ENV_COMMIT_SHA_KEY,
        ENV_BRANCH_KEY,
        ENV_BUILD_TIMESTAMP_KEY,
        ENV_VERSION_KEY,
    }


# 11. Build timestamp only ever renders when a real, non-blank value exists,
# and is resolved independently of which tier supplied the commit sha.
def test_build_timestamp_blank_is_treated_as_absent(tmp_path):
    env = {ENV_COMMIT_SHA_KEY: FULL_SHA, ENV_BUILD_TIMESTAMP_KEY: "   "}
    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)

    assert result["build_timestamp"] is None


def test_build_timestamp_present_is_accepted_verbatim(tmp_path):
    env = {ENV_COMMIT_SHA_KEY: FULL_SHA, ENV_BUILD_TIMESTAMP_KEY: "2026-07-20T10:00:00Z"}
    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)

    assert result["build_timestamp"] == "2026-07-20T10:00:00Z"


def test_build_timestamp_whitespace_wrapped_is_rejected_not_trimmed(tmp_path):
    # Regression guard: this value must NOT be silently trimmed into the
    # valid "2026-07-20T10:00:00Z" -- leading/trailing whitespace makes the
    # raw env value malformed and it must be rejected outright.
    env = {ENV_COMMIT_SHA_KEY: FULL_SHA, ENV_BUILD_TIMESTAMP_KEY: "  2026-07-20T10:00:00Z  "}
    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)

    assert result["build_timestamp"] is None


def test_build_timestamp_from_env_applies_even_when_git_resolves_sha(tmp_path):
    (tmp_path / ".git").mkdir()
    env = {ENV_BUILD_TIMESTAMP_KEY: "2026-07-20T10:00:00Z"}

    def fake_run_git(args, cwd):
        if args == ["rev-parse", "HEAD"]:
            return OTHER_FULL_SHA
        return None

    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=fake_run_git)

    assert result["source"] == REVISION_SOURCE_GIT
    assert result["commit_sha"] == OTHER_FULL_SHA
    assert result["build_timestamp"] == "2026-07-20T10:00:00Z"


# ---------------------------------------------------------------------------
# CRM_APP_BRANCH format/length validation.
# ---------------------------------------------------------------------------

VALID_BRANCHES = [
    "main",
    "feature/x",
    "release-1.2.3",
    "hotfix/2026_07_20",
    "a" * 128,  # exactly at the length cap
]

INVALID_BRANCHES = [
    "a" * 129,  # one over the length cap
    "",
    "   ",
    " main",  # leading space
    "main ",  # trailing space
    "feature x",  # internal whitespace
    "feature\tx",  # tab
    "feature\nx",  # newline
    "feature\x00x",  # control character
    "/main",  # leading slash
    "main/",  # trailing slash
    "feature//x",  # doubled slash
    "feature/../x",  # parent-dir traversal token
    "..",
    "feature@x",  # disallowed character
    "feature:x",  # disallowed character
]


def test_valid_branches_are_accepted():
    for branch in VALID_BRANCHES:
        assert _valid_branch(branch) == branch, f"expected acceptance for {branch!r}"


def test_invalid_branches_are_rejected():
    for branch in INVALID_BRANCHES:
        assert _valid_branch(branch) is None, f"expected rejection for {branch!r}"


def test_branch_env_var_is_validated_end_to_end(tmp_path):
    env = {ENV_COMMIT_SHA_KEY: FULL_SHA, ENV_BRANCH_KEY: "feature/x"}
    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)
    assert result["branch"] == "feature/x"

    env_bad = {ENV_COMMIT_SHA_KEY: FULL_SHA, ENV_BRANCH_KEY: "feature//x"}
    result_bad = resolve_app_revision(repo_root=tmp_path, env=env_bad, run_git=raising_run_git)
    assert result_bad["branch"] is None


# Regression guards: leading/trailing whitespace must not be silently
# trimmed into a valid branch -- it must be rejected outright, for both the
# CRM_APP_BRANCH env var and the git-derived branch.
def test_env_branch_leading_space_is_rejected(tmp_path):
    env = {ENV_COMMIT_SHA_KEY: FULL_SHA, ENV_BRANCH_KEY: " feature/x"}
    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)
    assert result["branch"] is None
    assert result["commit_sha"] == FULL_SHA


def test_env_branch_trailing_space_is_rejected(tmp_path):
    env = {ENV_COMMIT_SHA_KEY: FULL_SHA, ENV_BRANCH_KEY: "feature/x "}
    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)
    assert result["branch"] is None
    assert result["commit_sha"] == FULL_SHA


def test_git_branch_leading_or_trailing_space_is_rejected(tmp_path):
    (tmp_path / ".git").mkdir()
    for bad_branch in [" feature/x", "feature/x "]:
        result = resolve_app_revision(
            repo_root=tmp_path, env={}, run_git=_git_runner_returning(OTHER_FULL_SHA, bad_branch)
        )
        assert result["branch"] is None, f"expected rejection for {bad_branch!r}"
        # Invalid branch formatting must not disturb the resolved commit sha.
        assert result["commit_sha"] == OTHER_FULL_SHA
        assert result["source"] == REVISION_SOURCE_GIT


# ---------------------------------------------------------------------------
# CRM_APP_VERSION format/length validation.
# ---------------------------------------------------------------------------

VALID_VERSIONS = [
    "1.2.3",
    "v1.2.3-beta+build.5",
    "2026.07.20",
    "9" + "a" * 63,  # exactly at the length cap (64 total)
]

INVALID_VERSIONS = [
    "9" + "a" * 64,  # one over the length cap
    "",
    "   ",
    " 1.2.3",  # leading space
    "1.2.3 ",  # trailing space
    ".1.2.3",  # does not start with alnum
    "-1.2.3",  # does not start with alnum
    "1 2 3",  # internal whitespace
    "1.2\n3",  # embedded newline (not trimmed away since it isn't leading/trailing)
    "1.2\x003",  # embedded control character
    "1.2.3@build",  # disallowed character
]


def test_valid_versions_are_accepted():
    for version in VALID_VERSIONS:
        assert _valid_version(version) == version, f"expected acceptance for {version!r}"


def test_invalid_versions_are_rejected():
    for version in INVALID_VERSIONS:
        assert _valid_version(version) is None, f"expected rejection for {version!r}"


def test_version_env_var_is_validated_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(app_revision, "_package_version", lambda: None)

    env = {ENV_VERSION_KEY: "1.2.3"}
    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)
    assert result["app_version"] == "1.2.3"

    env_bad = {ENV_VERSION_KEY: ".1.2.3"}
    result_bad = resolve_app_revision(repo_root=tmp_path, env=env_bad, run_git=raising_run_git)
    assert result_bad["app_version"] is None


# Regression guard: leading/trailing whitespace around CRM_APP_VERSION must
# not be silently trimmed into a valid version -- it must be rejected.
def test_env_version_leading_or_trailing_whitespace_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(app_revision, "_package_version", lambda: None)

    for bad_version in [" 1.2.3", "1.2.3 ", "  1.2.3  "]:
        env = {ENV_VERSION_KEY: bad_version}
        result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)
        assert result["app_version"] is None, f"expected rejection for {bad_version!r}"


# Regression guard: package metadata must go through the exact same
# whitespace/control-character rules as CRM_APP_VERSION.
def test_package_version_whitespace_wrapped_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(app_revision, "_package_version", lambda: " 9.9.9 ")

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=raising_run_git)

    assert result["app_version"] is None
    assert result["source"] == REVISION_SOURCE_UNAVAILABLE


def test_package_version_control_characters_are_rejected(tmp_path, monkeypatch):
    for bad_version in ["9.9.9\n", "9.9\t.9", "9.9\x00.9", "9.9.9\r"]:
        monkeypatch.setattr(app_revision, "_package_version", lambda v=bad_version: v)

        result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=raising_run_git)

        assert result["app_version"] is None, f"expected rejection for {bad_version!r}"
        assert result["source"] == REVISION_SOURCE_UNAVAILABLE, f"expected rejection for {bad_version!r}"


# ---------------------------------------------------------------------------
# CRM_APP_BUILD_TIMESTAMP: real, parseable, timezone-aware ISO 8601 only.
# ---------------------------------------------------------------------------

VALID_BUILD_TIMESTAMPS = [
    "2026-07-20T10:00:00Z",
    "2026-07-20T10:00:00+07:00",
    "2026-07-20T10:00:00.123456+00:00",
]

INVALID_BUILD_TIMESTAMPS = [
    "2026-07-20T10:00:00",  # no timezone
    "not-a-timestamp",
    "2026-13-40T25:99:00Z",  # impossible date/time
    "2026-07-20T10:00\n:00Z",  # embedded newline (not trimmed away)
    "2026-07-20T10:00:00Z" + "x" * 40,  # far over the length cap
    " 2026-07-20T10:00:00Z",  # leading space
    "2026-07-20T10:00:00Z ",  # trailing space
    "2026-07-20T10:00:00Z\n",  # trailing newline
    "2026-07-20T10:00:00Z\r",  # trailing carriage return
    "\t2026-07-20T10:00:00Z",  # leading tab
]


def test_valid_build_timestamps_are_accepted():
    for value in VALID_BUILD_TIMESTAMPS:
        assert _valid_build_timestamp(value) == value, f"expected acceptance for {value!r}"


def test_invalid_build_timestamps_are_rejected():
    for value in INVALID_BUILD_TIMESTAMPS:
        assert _valid_build_timestamp(value) is None, f"expected rejection for {value!r}"


def test_build_timestamp_with_embedded_control_character_is_rejected():
    assert _valid_build_timestamp("2026-07-20T10:00:00\nZ") is None
    assert _valid_build_timestamp("2026-07-20T10:00:00\x00Z") is None


def test_build_timestamp_missing_timezone_is_rejected_end_to_end(tmp_path):
    env = {ENV_COMMIT_SHA_KEY: FULL_SHA, ENV_BUILD_TIMESTAMP_KEY: "2026-07-20T10:00:00"}
    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)
    assert result["build_timestamp"] is None


# Regression guards: leading/trailing whitespace (space, tab) and a trailing
# newline/CR must not be silently trimmed into a valid timestamp.
def test_build_timestamp_leading_space_is_rejected():
    assert _valid_build_timestamp(" 2026-07-20T10:00:00Z") is None


def test_build_timestamp_trailing_space_is_rejected():
    assert _valid_build_timestamp("2026-07-20T10:00:00Z ") is None


def test_build_timestamp_trailing_newline_is_rejected():
    assert _valid_build_timestamp("2026-07-20T10:00:00Z\n") is None


def test_build_timestamp_trailing_carriage_return_is_rejected():
    assert _valid_build_timestamp("2026-07-20T10:00:00Z\r") is None


def test_build_timestamp_leading_tab_is_rejected():
    assert _valid_build_timestamp("\t2026-07-20T10:00:00Z") is None


def test_build_timestamp_nul_byte_is_rejected():
    assert _valid_build_timestamp("2026-07-20T10:00:00Z\x00") is None
    assert _valid_build_timestamp("\x002026-07-20T10:00:00Z") is None


def test_build_timestamp_whitespace_and_control_variants_never_raise(tmp_path):
    for bad_value in [
        " 2026-07-20T10:00:00Z",
        "2026-07-20T10:00:00Z ",
        "2026-07-20T10:00:00Z\n",
        "2026-07-20T10:00:00Z\r",
        "\t2026-07-20T10:00:00Z",
        "2026-07-20T10:00:00Z\x00",
    ]:
        env = {ENV_COMMIT_SHA_KEY: FULL_SHA, ENV_BUILD_TIMESTAMP_KEY: bad_value}
        result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)
        assert result["build_timestamp"] is None, f"expected rejection for {bad_value!r}"
        # Malformed build timestamp must not disturb the resolved commit sha.
        assert result["commit_sha"] == FULL_SHA


# ---------------------------------------------------------------------------
# Invalid metadata across all four env keys simultaneously never raises.
# ---------------------------------------------------------------------------

def test_all_invalid_metadata_together_never_raises(tmp_path):
    env = {
        ENV_COMMIT_SHA_KEY: "abc123",
        ENV_BRANCH_KEY: "feature//x\n",
        ENV_VERSION_KEY: ".bad",
        ENV_BUILD_TIMESTAMP_KEY: "garbage\x00",
    }

    result = resolve_app_revision(repo_root=tmp_path, env=env, run_git=raising_run_git)

    assert result["commit_sha"] is None
    assert result["branch"] is None
    assert result["app_version"] is None
    assert result["build_timestamp"] is None
    assert result["source"] == REVISION_SOURCE_UNAVAILABLE


# 12. Helper is importable, and provably free of any Streamlit dependency,
# without opening Streamlit.
def test_helper_import_has_no_streamlit_dependency():
    source = Path(app_revision.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name.split(".")[0] == "streamlit" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"


# Package metadata tier: used only when neither environment nor git resolve,
# and never fabricates a commit sha.
def test_package_metadata_tier_used_when_env_and_git_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(app_revision, "_package_version", lambda: "9.9.9")

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=raising_run_git)

    assert result["app_version"] == "9.9.9"
    assert result["commit_sha"] is None
    assert result["source"] == REVISION_SOURCE_PACKAGE


def test_package_metadata_does_not_override_git_source(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(app_revision, "_package_version", lambda: "9.9.9")

    def fake_run_git(args, cwd):
        if args == ["rev-parse", "HEAD"]:
            return OTHER_FULL_SHA
        return None

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=fake_run_git)

    assert result["source"] == REVISION_SOURCE_GIT
    assert result["commit_sha"] == OTHER_FULL_SHA
    assert result["app_version"] == "9.9.9"


# ---------------------------------------------------------------------------
# Package-metadata version must pass through the same _valid_version() as
# CRM_APP_VERSION -- a malformed installed-package version string must never
# leak into the result, and must never be allowed to claim source="package".
# ---------------------------------------------------------------------------

def test_invalid_package_version_does_not_set_package_source(tmp_path, monkeypatch):
    monkeypatch.setattr(app_revision, "_package_version", lambda: ".bad")

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=raising_run_git)

    assert result["app_version"] is None
    assert result["source"] == REVISION_SOURCE_UNAVAILABLE


def test_invalid_package_version_with_whitespace_or_control_char_is_rejected(tmp_path, monkeypatch):
    for bad_version in ["1 2 3", "1.2\n3", "1.2\x003", ""]:
        monkeypatch.setattr(app_revision, "_package_version", lambda v=bad_version: v)

        result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=raising_run_git)

        assert result["app_version"] is None, f"expected rejection for {bad_version!r}"
        assert result["source"] == REVISION_SOURCE_UNAVAILABLE, f"expected rejection for {bad_version!r}"


def test_invalid_package_version_too_long_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(app_revision, "_package_version", lambda: "9" + "a" * 64)

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=raising_run_git)

    assert result["app_version"] is None
    assert result["source"] == REVISION_SOURCE_UNAVAILABLE


def test_invalid_package_version_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(app_revision, "_package_version", lambda: "\x00\x00garbage\n")

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=raising_run_git)

    assert result["app_version"] is None


def test_invalid_package_version_falls_back_to_unavailable_even_with_git(tmp_path, monkeypatch):
    # Package tier only ever contributes app_version -- an invalid package
    # version must not disturb an already-resolved git commit identity, and
    # must not itself claim source="package" (git already owns "source" here).
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(app_revision, "_package_version", lambda: ".bad")

    def fake_run_git(args, cwd):
        return OTHER_FULL_SHA if args == ["rev-parse", "HEAD"] else None

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=fake_run_git)

    assert result["commit_sha"] == OTHER_FULL_SHA
    assert result["source"] == REVISION_SOURCE_GIT
    assert result["app_version"] is None


def test_valid_package_version_still_sets_package_source(tmp_path, monkeypatch):
    monkeypatch.setattr(app_revision, "_package_version", lambda: "9.9.9")

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=raising_run_git)

    assert result["app_version"] == "9.9.9"
    assert result["source"] == REVISION_SOURCE_PACKAGE


def test_completely_unavailable_when_nothing_resolves(tmp_path, monkeypatch):
    monkeypatch.setattr(app_revision, "_package_version", lambda: None)

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=raising_run_git)

    assert result == {
        "app_version": None,
        "commit_sha": None,
        "short_sha": None,
        "branch": None,
        "source": REVISION_SOURCE_UNAVAILABLE,
        "build_timestamp": None,
    }


# No network call happens anywhere during resolution.
def test_no_network_call_during_resolution(tmp_path, monkeypatch):
    import socket

    def forbidden_socket(*args, **kwargs):
        raise AssertionError("resolve_app_revision must not touch the network")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    (tmp_path / ".git").mkdir()

    def fake_run_git(args, cwd):
        return OTHER_FULL_SHA if args == ["rev-parse", "HEAD"] else None

    result = resolve_app_revision(repo_root=tmp_path, env={}, run_git=fake_run_git)
    assert result["commit_sha"] == OTHER_FULL_SHA


def test_module_has_no_networking_imports():
    source = Path(app_revision.__file__).read_text(encoding="utf-8")
    assert "import requests" not in source
    assert "import urllib" not in source
    assert "import socket" not in source


# ---------------------------------------------------------------------------
# UI behavior: pages/system_status.py rendering of the revision section.
# ---------------------------------------------------------------------------

PAGE_PATH = Path(__file__).resolve().parents[1] / "pages" / "system_status.py"
PAGE_SOURCE = PAGE_PATH.read_text(encoding="utf-8")
PAGE_TREE = ast.parse(PAGE_SOURCE)


def _function_node(name: str) -> ast.FunctionDef:
    for node in PAGE_TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function: {name}")


def _function_source(name: str) -> str:
    segment = ast.get_source_segment(PAGE_SOURCE, _function_node(name))
    assert segment is not None
    return segment


class FakeSt:
    def __init__(self) -> None:
        self.calls: list = []

    def markdown(self, text, *args, **kwargs):
        self.calls.append(("markdown", text))

    def write(self, text, *args, **kwargs):
        self.calls.append(("write", text))

    def info(self, text, *args, **kwargs):
        self.calls.append(("info", text))

    def code(self, text, *args, **kwargs):
        self.calls.append(("code", text))


def _run_revision_section(resolve_fn):
    node = _function_node("_render_app_revision_section")
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    fake_st = FakeSt()
    runtime = {
        "st": fake_st,
        "resolve_app_revision": resolve_fn,
        "REVISION_SOURCE_UNAVAILABLE": REVISION_SOURCE_UNAVAILABLE,
    }
    exec(compile(module, str(PAGE_PATH), "exec"), runtime)
    runtime["_render_app_revision_section"]()
    return fake_st


def test_ui_renders_full_revision_details():
    def fake_resolve():
        return {
            "app_version": "1.2.3",
            "commit_sha": FULL_SHA,
            "short_sha": FULL_SHA[:7],
            "branch": "main",
            "source": REVISION_SOURCE_GIT,
            "build_timestamp": "2026-07-20T10:00:00Z",
        }

    fake_st = _run_revision_section(fake_resolve)

    call_kinds = [kind for kind, _ in fake_st.calls]
    assert "info" not in call_kinds
    assert ("code", FULL_SHA) in fake_st.calls
    written = "\n".join(text for kind, text in fake_st.calls if kind == "write")
    assert "1.2.3" in written
    assert "main" in written
    assert REVISION_SOURCE_GIT in written
    assert "2026-07-20T10:00:00Z" in written


def test_ui_renders_unavailable_state():
    def fake_resolve():
        return {
            "app_version": None,
            "commit_sha": None,
            "short_sha": None,
            "branch": None,
            "source": REVISION_SOURCE_UNAVAILABLE,
            "build_timestamp": None,
        }

    fake_st = _run_revision_section(fake_resolve)

    info_messages = [text for kind, text in fake_st.calls if kind == "info"]
    assert len(info_messages) == 1
    assert "Revision unavailable" in info_messages[0]
    assert not any(kind == "code" for kind, _ in fake_st.calls)


def test_ui_never_crashes_when_resolver_raises():
    def broken_resolve():
        raise RuntimeError("resolver blew up")

    fake_st = _run_revision_section(broken_resolve)

    info_messages = [text for kind, text in fake_st.calls if kind == "info"]
    assert len(info_messages) == 1
    assert "Revision unavailable" in info_messages[0]


def test_ui_does_not_display_full_sha_only_hint_when_unavailable():
    # Guards against ever fabricating a value in the unavailable branch.
    section_source = _function_source("_render_app_revision_section")
    assert "origin/main" not in section_source
    assert "HEAD" not in section_source


def test_revision_section_is_gated_behind_existing_permission_check():
    main_node = _function_node("main")

    stop_lineno = None
    call_lineno = None
    for node in ast.walk(main_node):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "stop"
        ):
            stop_lineno = node.lineno
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "_render_app_revision_section"
        ):
            call_lineno = node.lineno

    assert stop_lineno is not None, "permission gate st.stop() call not found"
    assert call_lineno is not None, "revision section call not found in main()"
    assert call_lineno > stop_lineno

    # The permission gate itself is untouched: still driven by can_view_system_page.
    assert "can_view_system_page(auth_user)" in PAGE_SOURCE
    assert "require_login()" in PAGE_SOURCE


print("app revision resolver + system status UI safety OK")
