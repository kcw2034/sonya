# CLAUDE.md

## Project Overview

Sonya는 Python 기반 경량 범용 AI 에이전트 프레임워크입니다. 최소 의존성과 단순한 API로 어떤 LLM Provider에서든 Tool 기반 에이전트를 구축합니다.

## Repository Structure

```
src/
├── sonya-core/          # 코어 라이브러리 (Tool 시스템)
│   ├── tools/
│   │   ├── base.py      # BaseTool - 모든 Tool의 베이스 클래스
│   │   ├── models.py    # ToolResult - 실행 결과 래퍼
│   │   ├── error.py     # ToolError - Tool 에러 클래스
│   │   └── builtins/    # 내장 Tool (web_search, calculator)
│   └── requirements.txt
└── sonya-agent/         # 에이전트 레이어 (미구현)
```

## Tech Stack

- **Language**: Python 3.11
- **Validation**: Pydantic (스키마 자동 생성, input/output 검증)
- **LLM Provider**: 현재 Anthropic Claude API → BaseLLMClient 추상화로 멀티벤더 확장 예정
- **Virtual Env**: `.venv/`

## Architecture Patterns

- `BaseTool[InputT, OutputT]` 제네릭 패턴 — Pydantic 모델로 Input/Output 타입 정의
- `to_llm_schema()` — Pydantic 모델에서 Anthropic API tools 포맷 JSON Schema 자동 추출
- `safe_execute()` — 검증 + 실행 + 에러 핸들링 통합 메서드
- `ToolError(recoverable=True)` — LLM 재시도 가능 여부 포함

## Conventions

- 코드 주석과 docstring은 한국어로 작성
- 새 Tool 추가 시 `BaseTool[InputModel, OutputModel]`을 상속하고 `name`, `description`, `execute()` 구현
- Pydantic `Field(description=...)` 으로 LLM에 전달할 파라미터 설명 명시

## Commands

```bash
# 가상환경 활성화
source .venv/bin/activate

# 의존성 설치
pip install -r src/sonya-core/requirements.txt
```
