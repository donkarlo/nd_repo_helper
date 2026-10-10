"""Isolated Git integration checks; never operate on real user repositories."""

import os
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "add_commit_push_core.sh"


class TestCommitPushCore:
    @staticmethod
    def git(*args: str, cwd: Path) -> str:
        result = subprocess.run(
            ["git", *args], cwd=cwd, check=True,
            capture_output=True, text=True,
        )
        return result.stdout.strip()

    @classmethod
    def prepare(cls, tmp_path: Path) -> tuple[Path, Path, Path]:
        root = tmp_path / "repositories"
        root.mkdir()
        remote = tmp_path / "origin.git"
        cls.git("init", "--bare", "--initial-branch=main", str(remote), cwd=tmp_path)
        repository = root / "example_project"
        cls.git("clone", str(remote), str(repository), cwd=tmp_path)
        cls.git("config", "user.name", "Test Runner", cwd=repository)
        cls.git("config", "user.email", "test@example.com", cwd=repository)
        cls.git("remote", "rename", "origin", "mghub", cwd=repository)
        (repository / "file.txt").write_text("first\n", encoding="utf-8")
        cls.git("add", ".", cwd=repository)
        cls.git("commit", "-m", "Initial", cwd=repository)
        cls.git("push", "mghub", "main", cwd=repository)
        return root, repository, remote

    @staticmethod
    def execute(root: Path, user_input: str = "") -> subprocess.CompletedProcess:
        environment = {**os.environ, "ND_REPO_ROOT": str(root)}
        return subprocess.run(
            ["bash", str(SCRIPT)], env=environment,
            input=user_input, text=True, capture_output=True,
            timeout=25,
        )

    def test_existing_unpushed_commits_are_sent_without_new_edits(self, tmp_path: Path):
        root, local, remote = self.prepare(tmp_path)
        (local / "file.txt").write_text("second\n", encoding="utf-8")
        self.git("add", ".", cwd=local)
        self.git("commit", "-m", "Previously unpushed", cwd=local)
        result = self.execute(root)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "No new changes" in result.stdout
        assert "Pushing 1 local commit" in result.stdout
        assert self.git("rev-parse", "HEAD", cwd=local) == self.git(
            "rev-parse", "refs/heads/main", cwd=remote
        )

    def test_commits_staged_changes_and_pushes(self, tmp_path: Path):
        root, local, remote = self.prepare(tmp_path)
        (local / "file.txt").write_text("edited\n", encoding="utf-8")
        result = self.execute(root, "y\nDaily changes\n")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Daily changes" in self.git("log", "-1", "--format=%s", cwd=local)
        assert self.git("rev-parse", "HEAD", cwd=local) == self.git(
            "rev-parse", "refs/heads/main", cwd=remote
        )

    def test_fast_forwards_when_remote_only_commits_exist(self, tmp_path: Path):
        root, local, remote = self.prepare(tmp_path)
        other = tmp_path / "other"
        self.git("clone", str(remote), str(other), cwd=tmp_path)
        self.git("config", "user.name", "Test Runner", cwd=other)
        self.git("config", "user.email", "test@example.com", cwd=other)
        (other / "file.txt").write_text("remote update\n", encoding="utf-8")
        self.git("add", ".", cwd=other)
        self.git("commit", "-m", "Remote change", cwd=other)
        self.git("push", "origin", "main", cwd=other)
        result = self.execute(root)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Fast-forwarding" in result.stdout
        assert (local / "file.txt").read_text(encoding="utf-8") == "remote update\n"

    def test_divergence_is_reported_without_overwriting_either_side(self, tmp_path: Path):
        root, local, remote = self.prepare(tmp_path)
        other = tmp_path / "other"
        self.git("clone", str(remote), str(other), cwd=tmp_path)
        self.git("config", "user.name", "Test Runner", cwd=other)
        self.git("config", "user.email", "test@example.com", cwd=other)
        (other / "remote.txt").write_text("remote only", encoding="utf-8")
        self.git("add", ".", cwd=other)
        self.git("commit", "-m", "Remote", cwd=other)
        self.git("push", "origin", "main", cwd=other)
        (local / "local.txt").write_text("local only", encoding="utf-8")
        self.git("add", ".", cwd=local)
        self.git("commit", "-m", "Local", cwd=local)
        before_local = self.git("rev-parse", "HEAD", cwd=local)
        before_remote = self.git("rev-parse", "refs/heads/main", cwd=remote)
        result = self.execute(root)
        assert result.returncode == 1
        assert "local-only and 1 GitHub-only" in result.stderr
        assert "NOT synchronized" in result.stderr
        assert self.git("rev-parse", "HEAD", cwd=local) == before_local
        assert self.git("rev-parse", "refs/heads/main", cwd=remote) == before_remote

    def test_failed_fetch_is_visible_and_leaves_commit_safe(self, tmp_path: Path):
        root, local, remote = self.prepare(tmp_path)
        (local / "file.txt").write_text("local update\n", encoding="utf-8")
        self.git("add", ".", cwd=local)
        self.git("commit", "-m", "Saved locally", cwd=local)
        before = self.git("rev-parse", "HEAD", cwd=local)
        self.git("remote", "set-url", "mghub", str(tmp_path / "missing.git"), cwd=local)
        result = self.execute(root)
        assert result.returncode == 1
        assert "Fetch failed" in result.stderr
        assert self.git("rev-parse", "HEAD", cwd=local) == before
        assert self.git("rev-parse", "refs/heads/main", cwd=remote) != before

    def test_no_commits_does_not_need_confirmation(self, tmp_path: Path):
        root, _, _ = self.prepare(tmp_path)
        result = self.execute(root)
        assert result.returncode == 0
        assert "Synchronized example_project" in result.stdout
        assert "Do you want" not in result.stdout

    def test_first_push_of_a_new_remote_branch(self, tmp_path: Path):
        root = tmp_path / "repositories"
        root.mkdir()
        remote = tmp_path / "empty.git"
        self.git("init", "--bare", "--initial-branch=main", str(remote), cwd=tmp_path)
        repository = root / "brand_new_project"
        repository.mkdir()
        self.git("init", "--initial-branch=main", cwd=repository)
        self.git("config", "user.name", "Test Runner", cwd=repository)
        self.git("config", "user.email", "test@example.com", cwd=repository)
        self.git("remote", "add", "mghub", str(remote), cwd=repository)
        (repository / "README.md").write_text("Hello", encoding="utf-8")
        result = self.execute(root, "y\nInitial commit\n")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Publishing initial" in result.stdout
        assert self.git("rev-parse", "HEAD", cwd=repository) == self.git(
            "rev-parse", "refs/heads/main", cwd=remote
        )
