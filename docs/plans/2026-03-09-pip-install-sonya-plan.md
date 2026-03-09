# pip install sonya — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `pip install sonya` 하나로 sonya 프레임워크를 설치하고 `sonya` 명령어로 TUI 챗을 바로 실행할 수 있게 한다.

**Architecture:** `packages/sonya/`에 순수 메타 패키지를 생성하여 sonya-core + sonya-cli를 의존성으로 묶고, extras로 나머지 패키지를 선택 설치 가능하게 한다. CLI 기본 동작을 `@app.default`로 변경하여 `sonya`만 입력해도 TUI 챗이 실행되도록 한다.

**Tech Stack:** Python 3.11+, setuptools, cyclopts (`@app.default`), uv

**Design doc:** `docs/plans/2026-03-09-pip-install-sonya-design.md`

---

### Task 1: Modify sonya-cli default command

**Files:**
- Modify: `packages/sonya-cli/src/sonya/cli/client/cli.py`

**Step 1: Update cli.py to add @app.default**

Replace the entire content of `packages/sonya-cli/src/sonya/cli/client/cli.py` with:

```python
"""Sonya CLI entrypoint using Cyclopts."""

from cyclopts import App

app = App(name='sonya', help='Sonya Agent Framework CLI')


@app.default
@app.command(name='chat')
def chat() -> None:
    """Launch the Sonya TUI chat interface."""
    from sonya.cli.client.app import SonyaTUI
    tui_app = SonyaTUI()
    tui_app.run()


if __name__ == '__main__':
    app()
```

**Step 2: Verify the import works**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya && python -c "from sonya.cli.client.cli import app; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add packages/sonya-cli/src/sonya/cli/client/cli.py
git commit -m "feat(sonya-cli): add @app.default to make sonya run TUI directly"
```

---

### Task 2: Remove console_scripts from sonya-cli

**Files:**
- Modify: `packages/sonya-cli/pyproject.toml`

**Step 1: Remove [project.scripts] section**

In `packages/sonya-cli/pyproject.toml`, remove lines 17-18:

```toml
[project.scripts]
sonya = "sonya.cli.client.cli:app"
```

The remaining file should have `[build-system]` directly after `dependencies`.

**Step 2: Commit**

```bash
git add packages/sonya-cli/pyproject.toml
git commit -m "refactor(sonya-cli): remove console_scripts, moved to meta package"
```

---

### Task 3: Create sonya meta package

**Files:**
- Create: `packages/sonya/pyproject.toml`

**Step 1: Create package directory**

Run: `mkdir -p /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya`

**Step 2: Create pyproject.toml**

Create `packages/sonya/pyproject.toml` with:

```toml
[project]
name = "sonya"
version = "0.1.0"
description = "Sonya Agent Framework"
readme = "README.md"
authors = [
    { name = "kcw2034", email = "cksdn2034@gmail.com" }
]
requires-python = ">=3.11"
dependencies = [
    "sonya-core",
    "sonya-cli",
]

[project.optional-dependencies]
pack = ["sonya-pack"]
pipeline = ["sonya-pipeline"]
langchain = ["sonya-extension"]
all = ["sonya-pack", "sonya-pipeline", "sonya-extension"]

[project.scripts]
sonya = "sonya.cli.client.cli:app"

[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.uv.sources]
sonya-core = { path = "../sonya-core", editable = true }
sonya-cli = { path = "../sonya-cli", editable = true }
sonya-pack = { path = "../sonya-pack", editable = true }
sonya-pipeline = { path = "../sonya-pipeline", editable = true }
sonya-extension = { path = "../sonya-extension", editable = true }
```

**Step 3: Commit**

```bash
git add packages/sonya/pyproject.toml
git commit -m "feat(sonya): add meta package for pip install sonya"
```

---

### Task 4: Install and verify

**Step 1: Install meta package**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya && uv pip install -e ".[all]"`

**Step 2: Verify sonya command exists**

Run: `which sonya`
Expected: path to sonya executable

**Step 3: Verify sonya --help shows chat command**

Run: `sonya --help`
Expected: Shows help with `chat` command listed

**Step 4: Verify sonya chat --help works**

Run: `sonya chat --help`
Expected: Shows chat command help

**Step 5: Verify import works**

Run: `python -c "from sonya.core import Agent; print('core OK'); from sonya.cli.client.cli import app; print('cli OK')"`
Expected: `core OK` then `cli OK`
