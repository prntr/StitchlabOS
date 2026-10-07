"""Tests for stitchlab-clone-at-ref against local repositories (no network)."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "filesystem/usr/local/bin/stitchlab-clone-at-ref"
GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def git(cwd, *args) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], env=GIT_ENV, check=True,
                          capture_output=True, text=True).stdout.strip()


def make_upstream(tmp_path: Path, commits: int, tags: dict[int, str],
                  annotated: bool = True) -> tuple[Path, list[str]]:
    """A repo with `commits` commits on master; tags maps commit number -> name."""
    repo = tmp_path / "upstream"
    repo.mkdir()
    git(repo, "init", "-q", "--initial-branch=master")
    # One fast-import run instead of a process per commit.
    stream = []
    for i in range(1, commits + 1):
        msg = f"c{i}"
        stream += [f"commit refs/heads/master", f"mark :{i}",
                   f"committer t <t@t> {1700000000 + i} +0000",
                   f"data {len(msg)}", msg]
        if i > 1:
            stream.append(f"from :{i - 1}")
        stream += [f"M 644 inline f", f"data {len(msg)}", msg, ""]
    subprocess.run(["git", "-C", str(repo), "fast-import", "--quiet"], env=GIT_ENV, check=True,
                   input="\n".join(stream) + "\n", text=True)
    shas = git(repo, "rev-list", "--reverse", "master").split("\n")
    git(repo, "checkout", "-q", "master")
    for i, name in tags.items():
        if annotated:
            git(repo, "tag", "-a", name, "-m", name, shas[i - 1])
        else:
            git(repo, "tag", name, shas[i - 1])
    return repo, shas


def clone(tmp_path, upstream, ref, branch="master"):
    dest = tmp_path / "dest"
    result = subprocess.run(["bash", str(SCRIPT), f"file://{upstream}", branch, ref, str(dest)],
                            env=GIT_ENV, capture_output=True, text=True, timeout=120)
    return dest, result


@pytest.mark.parametrize("annotated", [True, False])
def test_ref_behind_the_tip_gets_its_last_release_tag(tmp_path, annotated):
    # 120 commits, release tag at 5, a later pre-release after the pin.
    upstream, shas = make_upstream(tmp_path, 120, {5: "v1.2.0", 110: "v1.3.0-beta.1"},
                                   annotated=annotated)
    dest, result = clone(tmp_path, upstream, shas[99])
    assert result.returncode == 0, result.stderr
    assert git(dest, "rev-parse", "HEAD") == shas[99]
    assert git(dest, "rev-parse", "--abbrev-ref", "HEAD") == "master"
    assert git(dest, "rev-parse", "--abbrev-ref", "@{u}") == "origin/master"
    # What Moonraker's update_manager runs for the installed version:
    assert git(dest, "describe", "--always", "--tags", "--long", "--dirty",
               "--abbrev=8").startswith("v1.2.0-95-g")
    assert git(dest, "status", "--porcelain") == ""


def test_repo_without_version_tags_clones_with_a_warning(tmp_path):
    upstream, shas = make_upstream(tmp_path, 3, {2: "release-two"})
    dest, result = clone(tmp_path, upstream, shas[2])
    assert result.returncode == 0, result.stderr
    assert "no version tags" in result.stderr
    assert git(dest, "rev-parse", "HEAD") == shas[2]


def test_ref_not_on_the_branch_fails(tmp_path):
    upstream, shas = make_upstream(tmp_path, 3, {})
    git(upstream, "checkout", "-q", "-b", "side", shas[0])
    git(upstream, "commit", "-q", "--allow-empty", "-m", "side")  # a branch off master
    side = git(upstream, "rev-parse", "HEAD")
    git(upstream, "checkout", "-q", "master")
    dest, result = clone(tmp_path, upstream, side)
    assert result.returncode == 1
    assert "is not on origin/master" in result.stderr
