# Sonya

경량 Python AI 에이전트 프레임워크입니다.
복잡한 오케스트레이션 대신 Tool 중심 루프에 집중해 빠르게 에이전트를 구성할 수 있습니다.

## 핵심 특징

- Tool-first 설계: `BaseTool[InputModel, OutputModel]` 기반
- 타입 안전한 입력/출력: Pydantic 모델 검증
- LLM 응답 통합 모델: `LLMResponse`, `ContentBlock` 제공
- 런타임 루프 제공: LLM 호출 → tool_use 처리 → tool_result 재주입
- 경량 의존성: `httpx`, `pydantic`, `python-dotenv`

## 프로젝트 구조

```text
src/
├── sonya-core/
│   ├── tools/
│   │   ├── base.py
│   │   ├── models.py
│   │   ├── error.py
│   │   ├── registry.py
│   │   └── examples/
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── models.py
│   │   └── client/
│   │       ├── anthropic.py
│   │       ├── openai.py
│   │       └── google.py
│   └── runtime/
│       └── agent.py
└── sonya-agent/
```

## 빠른 시작

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r src/sonya-core/requirements.txt
```

## 사용 예시

```python
import asyncio
from pydantic import BaseModel, Field

from sonya_core.llm import AnthropicClient
from sonya_core.runtime.agent import AgentRuntime
from sonya_core.tools.base import BaseTool
from sonya_core.tools.registry import ToolRegistry


class AddInput(BaseModel):
    a: int = Field(description="첫 번째 숫자")
    b: int = Field(description="두 번째 숫자")


class AddOutput(BaseModel):
    result: int


class AddTool(BaseTool[AddInput, AddOutput]):
    name = "add"
    description = "두 수를 더합니다"

    async def execute(self, input: AddInput) -> AddOutput:
        return AddOutput(result=input.a + input.b)


async def main() -> None:
    registry = ToolRegistry()
    registry.register(AddTool())

    async with AnthropicClient(system="계산 도우미") as client:
        runtime = AgentRuntime(client=client, tools=registry)
        result = await runtime.run("3 + 5를 계산해줘")
        print(result)


asyncio.run(main())
```

## 테스트

```bash
pytest
```

현재 알려진 상태:
- `tests/test_tools.py`는 `sonya_core.tools.examples.write_file` 모듈 누락 시 수집 단계에서 실패합니다.

## OpenCode 워크플로

- 프로젝트 규칙: `AGENTS.md`
- 프로젝트 에이전트: `.opencode/agents/`
- 프로젝트 커맨드: `.opencode/commands/`
- 프로젝트 Skills: `.opencode/skills/`

추천 명령:
- `/sonya-context`: 프로젝트 컨텍스트 빠른 요약
- `/sonya-test`: 테스트 실행 및 실패 원인 정리
- `/sonya-tool <설명>`: Tool 구현 작업 시작

## 문서 작성 원칙

- README는 사람 기준으로 빠르게 이해 가능한 정보만 유지합니다.
- 구현 규칙/에이전트 규칙은 `AGENTS.md`를 단일 기준으로 사용합니다.
- 코드 구조가 바뀌면 README의 구조/예시를 먼저 동기화합니다.
