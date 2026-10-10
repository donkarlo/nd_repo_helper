# repotool

A lightweight set of developer tools for managing multiple Python repositories under the same folder.

This toolkit includes:

- **Editable package installation** for Python packages found in subdirectories
- **Git commit and push helper** for syncing local changes across multiple repositories

---

## 📁 Folder Structure

This script suite assumes the following structure:

```
~/repos/
├── repo1/
│   ├── setup.py or pyproject.toml
│   └── ...
├── repo2/
│   ├── setup.py or pyproject.toml
│   └── ...
└── ...
```

---

## 🚀 Usage

### 1. Install All Editable Python Packages

This script finds all valid Python packages in `repos` and installs them using pip in editable mode (`-e`).

```bash
./install_python_packages.sh
```

Output will include which packages were installed or skipped.

---

### 1. Uninstall All Editable Python Packages

This script finds all valid Python packages in `repos` and installs them using pip in editable mode (`-e`).

```bash
./install_python_packages.sh
```

Output will include which packages were installed or skipped.

---

### 2. Commit & Push Changes in All Git Repositories

The classic helper scans Git repositories in `~/Dropbox/repo`, stages pending changes, and asks before committing. It then fetches each repository's `mghub/main` and performs a **normal, non-forced push** whenever local commits are waiting, even when no new file changes exist.

```bash
bash /home/donkarlo/Dropbox/repo/nd_repo_helper/add_commit_push.sh
```

The interactive terminal and Qt GUI both use `add_commit_push_core.sh` and its **single** repository pass. An already-updated branch is skipped without asking for a new commit. Remote-only commits are fast-forwarded when safe; divergent branches or unfinished merges are reported as errors without rewriting either history. Fetch or push failures leave all local commits intact and produce a nonzero final exit status. The GUI stays open on failure, displays the errors, and provides a Close button; it never silently reports a successful synchronization when any repository failed.

To test without touching actual repositories, set `ND_REPO_ROOT` to a separate directory containing disposable test Git repositories. `ND_REPO_REMOTE` (default `mghub`) and `ND_REPO_BRANCH` (default `main`) are optional overrides. Integration checks are in `tests/test_add_commit_push_core.py` and `tests/test_add_commit_push_gui.py`.

> Confirmation is requested only when new changes must be committed. Previously committed changes are eligible for safe synchronization automatically.

---

## 🔧 Requirements

- Bash
- Python (>= 3.9)
- Git
- Pip
- Proper `origin` or `mghub` remote in each repository (you can change `mghub` to `origin` in the script if needed)

---

## 📦 License

This project is personal utility code — no license restrictions, use freely.
