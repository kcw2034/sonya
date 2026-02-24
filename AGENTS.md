# Sonya OpenCode Agent Guide

## Project Overview

Sonya는 Python 기반 AI 에이전트 프레임워크입니다.
Anthropic tool_use 포맷을 타겟으로 Tool 시스템을 핵심으로 개발합니다.

## Tech Stack

- Python 3.11
- Pydantic
- Anthropic API

## Repository Structure

- `src/sonya-core/`: 코어 라이브러리
- `src/sonya-core/tools/`: Tool 기본 클래스/모델/에러/레지스트리
- `src/sonya-core/runtime/`: 에이전트 런타임
- `src/sonya-core/llm/`: LLM 클라이언트/모델
- `src/sonya-agent/`: 에이전트 레이어 (초기 상태)
- `tests/`: 테스트 스위트

## Commands

- 가상환경 활성화: `source .venv/bin/activate`
- 의존성 설치: `pip install -r src/sonya-core/requirements.txt`
- 테스트 실행: `pytest`

## Coding Conventions

- 코드 주석과 docstring은 한국어로 작성합니다.
- 새 Tool은 `BaseTool[InputModel, OutputModel]`을 상속합니다.
- Tool 입력 파라미터는 `Field(description=...)`를 명시합니다.
- Tool 실패는 `ToolError`를 사용하고 recoverable 여부를 명확히 표현합니다.

## Working Rules For Agents

- 기존 파일의 네이밍/구조/에러 처리 패턴을 우선 따릅니다.
- 요청 범위를 벗어나는 리팩터링은 하지 않습니다.
- 새 기능/수정 후 관련 테스트(`pytest`)를 실행하고 결과를 공유합니다.
