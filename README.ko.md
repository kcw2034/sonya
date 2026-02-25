# Sonya

Tool-first 실행 루프에 집중한 경량 Python AI 에이전트 프레임워크입니다.
Sonya는 LLM 클라이언트 추상화, 타입 안전한 Tool, 그리고 `LLM -> tool_use -> tool_result`를 반복하는 Runtime을 최소한의 구조로 제공합니다.

English: `README.md`

## 현재 상태

- 코어 패키지(`sonya-core`)는 구현 및 테스트가 완료된 상태입니다.
- `src/sonya-agent/greedy/persona/`는 미리 잡아둔 에이전트 예제 구조이며 OpenClaw를 레퍼런스로 작성한 초안입니다.
- 현재 범위: 단일 에이전트 런타임, Tool 실행 루프, Provider 클라이언트, 스트리밍 인터페이스, 로깅 헬퍼.
- 다음 범위: 상태/메모리, 멀티 에이전트 오케스트레이션, 관찰성, 가드레일.

## 저장소 구조

```text
.
├── src/
│   ├── sonya-core/
│   │   ├── llm/           # BaseLLMClient + Anthropic/OpenAI/Gemini 클라이언트
│   │   ├── runtime/       # AgentRuntime
│   │   ├── tools/         # BaseTool, ToolRegistry, ToolContext
│   │   └── logging.py     # setup_logging 헬퍼
│   └── sonya-agent/       # 제품/도메인 레이어 (초기 단계)
├── tests/                 # pytest 테스트 스위트
├── AGENTS.md              # 프로젝트 작업 규칙
└── README.ko.md
```

## 요구 사항

- Python 3.11+

## 설치

가상환경 생성 및 활성화:

```bash
python -m venv .venv
source .venv/bin/activate
```

로컬 개발 설치:

```bash
pip install -e .
pip install -e ".[dev]"
```

또는 핵심 의존성만 설치:

```bash
pip install pydantic httpx python-dotenv
```

## 빠른 시작

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
    description = "두 숫자를 더한다"

    async def execute(self, input: AddInput) -> AddOutput:
        return AddOutput(result=input.a + input.b)


async def main() -> None:
    registry = ToolRegistry()
    registry.register(AddTool())

    async with AnthropicClient(system="수학 도우미") as client:
        agent = AgentRuntime(client=client, registry=registry)
        answer = await agent.run("3 더하기 5는?")
        print(answer)


asyncio.run(main())
```

## 스트리밍

```python
import asyncio

from sonya_core.llm import AnthropicClient
from sonya_core.runtime.agent import AgentRuntime
from sonya_core.tools.registry import ToolRegistry


async def main() -> None:
    async with AnthropicClient(system="도움이 되는 어시스턴트") as client:
        agent = AgentRuntime(client=client, registry=ToolRegistry())
        async for token in agent.run_stream("서울을 한 문장으로 설명해줘"):
            print(token, end="", flush=True)
        print()


asyncio.run(main())
```

## 핵심 구성 요소

### LLM

- `BaseLLMClient`: Provider 공통 인터페이스.
- 클라이언트: `AnthropicClient`, `OpenAIClient`, `GeminiClient`.
- 공통 응답 모델: `LLMResponse`, `ContentBlock`, `StopReason`, `Usage`.
- API 실패는 재시도 가능 여부를 포함한 `LLMAPIError`로 래핑됩니다.

환경 변수:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

스트리밍 지원:

- `AnthropicClient`: 네이티브 SSE 스트리밍 구현.
- `OpenAIClient`, `GeminiClient`: 베이스 클라이언트 기반 폴백 스트림(`chat` 결과를 스트림 청크로 래핑).

### Tools

- `BaseTool[InputModel, OutputModel]` 기반 Pydantic 검증.
- `ToolRegistry`로 등록/조회/스키마 내보내기/배치 실행 지원.
- `ToolContext`로 단일 런타임 루프 내 Tool 간 데이터 공유.
- `ToolError`로 recoverable/non-recoverable 실패 표현.
- 내장 예제: `CalculatorTool`, `WebSearchTool`(mock), `WriteFileTool`.

### Runtime

- `AgentRuntime.run(user_message)`는 최종 텍스트를 반환합니다.
- `AgentRuntime.run_stream(user_message)`는 텍스트 토큰을 순차 반환합니다.
- 루프는 `end_turn` 또는 `max_iterations`까지 `tool_use`를 자동 처리합니다.

### Logging

- `setup_logging(level=..., format="text" | "json")`
- 구조화 로그를 위한 JSON 포매터를 지원합니다.

## 개발

전체 테스트 실행:

```bash
pytest
```

일부 테스트 실행:

```bash
pytest tests/test_runtime.py -v
```

## 기여 안내

- `AGENTS.md` 규칙을 우선 따릅니다.
- 변경은 요청 범위 안에서만 수행합니다.
- 기존 네이밍/스타일/에러 처리 패턴을 우선 적용합니다.
- 코드 주석과 docstring은 한국어로 작성합니다.

## 라이선스

MIT (`LICENSE` 참고)
