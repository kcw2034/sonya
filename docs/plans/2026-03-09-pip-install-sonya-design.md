# pip install sonya — Meta Package Design

## Summary

`pip install sonya`로 설치하면 `sonya` 명령어로 TUI 챗을 바로 실행할 수 있도록
메타 패키지를 생성하고, CLI 기본 동작을 변경한다.

## Requirements

- `pip install sonya` → sonya-core + sonya-cli 설치, `sonya` 명령어 사용 가능
- `sonya` (인자 없이) → TUI 챗 바로 실행
- `sonya chat` → 동일하게 TUI 챗 실행 (하위 호환)
- `pip install sonya[all]` → 전체 패키지 설치
- `pip install sonya[pack]`, `[pipeline]`, `[langchain]` → 선택 설치
- 개별 패키지 (`pip install sonya-core` 등) 독립 설치 유지

## Changes

### 1. New: `packages/sonya/pyproject.toml`

순수 메타 패키지. 자체 코드 없이 의존성과 CLI 진입점만 정의.

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
```

### 2. Modify: `packages/sonya-cli/src/sonya/cli/client/cli.py`

`@app.default` 데코레이터를 추가하여 `sonya` 기본 실행 = TUI 챗.

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

### 3. Modify: `packages/sonya-cli/pyproject.toml`

`[project.scripts]` 섹션 제거 — CLI 진입점은 메타 패키지에서만 정의하여 충돌 방지.

## Package Install Matrix

| Command | Installed |
|---|---|
| `pip install sonya` | sonya-core, sonya-cli |
| `pip install sonya[pack]` | + sonya-pack |
| `pip install sonya[pipeline]` | + sonya-pipeline |
| `pip install sonya[langchain]` | + sonya-extension |
| `pip install sonya[all]` | all packages |
| `pip install sonya-core` | sonya-core only |
