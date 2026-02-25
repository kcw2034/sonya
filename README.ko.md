# Sonya

Python 기반 경량 범용 AI 에이전트 프레임워크. 최소 의존성과 단순한 API로 어떤 LLM Provider에서든 Tool 기반 에이전트를 구축합니다.

*Read this in other languages: [English](README.md), [한국어](README.ko.md)*

> **현재 상태**: 코어 레이어(Tool + LLM + 기본 Runtime) 구현 완료. 상태 관리, 멀티 에이전트, 관찰성 등 주요 기능은 구현 예정입니다 — 전체 로드맵 대비 약 **20~25%** 진행 중.

## 저장소 구조

```text
.
├── src/
│   ├── sonya-core/        # PyPI 배포 대상 코어 패키지
│   │   ├── llm/           # BaseLLMClient + Anthropic/OpenAI/Gemini 구현
│   │   ├── runtime/       # AgentRuntime (run / run_stream)
│   │   └── tools/         # BaseTool, ToolRegistry, ToolContext, 내장 예제
│   └── sonya-agent/       # 제품/도메인 특화 레이어 (초기 상태)
├── tests/                 # 코어 테스트 (70+ 케이스, 6개 파일)
├── AGENTS.md              # 작업/코딩 규칙
└── README.ko.md           # 이 문서
```

## 빠른 시작

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r src/sonya-core/requirements.txt
```

```python
import asyncio
from pydantic import BaseModel, Field

from sonya_core.llm import AnthropicClient
from sonya_core.runtime.agent import AgentRuntime
from sonya_core.tools.base import BaseTool
from sonya_core.tools.registry import ToolRegistry


class CalcInput(BaseModel):
    a: float = Field(description="첫 번째 숫자")
    b: float = Field(description="두 번째 숫자")

class CalcOutput(BaseModel):
    result: float

class AddTool(BaseTool[CalcInput, CalcOutput]):
    name = "add"
    description = "두 숫자를 더한다"

    async def execute(self, input: CalcInput) -> CalcOutput:
        return CalcOutput(result=input.a + input.b)


async def main() -> None:
    registry = ToolRegistry()
    registry.register(AddTool())

    async with AnthropicClient(system="수학 도우미") as client:
        agent = AgentRuntime(client=client, registry=registry)
        answer = await agent.run("3 더하기 5는?")
        print(answer)

asyncio.run(main())
```

스트리밍:

```python
async with AnthropicClient(system="helpful assistant") as client:
    agent = AgentRuntime(client=client, registry=ToolRegistry())
    async for token in agent.run_stream("서울을 한 문장으로 설명해줘"):
        print(token, end="", flush=True)
```

## 현재 구현 (sonya-core)

### LLM Client 추상화

`BaseLLMClient` 인터페이스 위에 3개 Provider 클라이언트 구현:

| 클라이언트 | 환경 변수 | 스트리밍 |
|---|---|---|
| `AnthropicClient` | `ANTHROPIC_API_KEY` | 네이티브 스트리밍 |
| `OpenAIClient` | `OPENAI_API_KEY` | 네이티브 스트리밍 |
| `GeminiClient` | `GEMINI_API_KEY` | 폴백(비스트리밍) |

모든 클라이언트는 `async with` 컨텍스트 매니저를 지원하며 `LLMResponse`로 응답을 통합합니다.

### Tool 시스템

- `BaseTool[InputT, OutputT]` — Pydantic 제네릭으로 Input/Output 타입 정의
- `to_llm_schema(provider=)` — Pydantic 모델에서 Anthropic/OpenAI 포맷 JSON Schema 자동 추출
- `safe_execute()` — 검증 + 실행 + 에러 핸들링 통합
- `ToolRegistry` — 이름 기반 Tool 관리, 병렬 실행(`execute_many`), 라이프사이클(`startup/shutdown`)
- `ToolContext` — 단일 `run()` 호출 스코프 내 Tool 간 데이터 공유
- `ToolError(recoverable=True/False)` — LLM 재시도 가능 여부 포함
- sync `execute()` 자동 비동기 래핑 (`asyncio.to_thread`)

내장 예제 Tool: `CalculatorTool`, `WebSearchTool`(mock), `WriteFileTool`

### Agent Runtime

`user → LLM → tool_use → tool_result → LLM` 루프를 `max_iterations`까지 반복:

- `run(user_message)` — 최종 텍스트 응답 반환
- `run_stream(user_message)` — 토큰 단위 스트리밍, Tool 루프 자동 처리
- `reset()` — 대화 히스토리 초기화
- `history` 프로퍼티 — 현재 대화 히스토리 읽기

---

## 로드맵 (TODO)

LangGraph / Google ADK 수준의 프로덕션 에이전트 프레임워크를 목표로 합니다.

### 진행률 매트릭스

| 카테고리 | Sonya | LangGraph | Google ADK | 진행률 |
|---|---|---|---|---|
| LLM Client 추상화 | 3 Provider | 다수 | Gemini + LiteLLM | ~60% |
| Tool 시스템 | 완료 | 완료 | 완료 | ~80% |
| Agent Runtime (단일) | 기본 루프 | 그래프 기반 | 이벤트 기반 | ~50% |
| 상태/메모리 | 미구현 | 완료 | 완료 | ~5% |
| 멀티 에이전트 | 미구현 | 완료 | 완료 | 0% |
| Human-in-the-Loop | 미구현 | 완료 | 부분 | 0% |
| 관찰성/추적 | 미구현 | LangSmith | Cloud Trace | 0% |
| 가드레일/안전 | 미구현 | 통합 | 콜백 기반 | 0% |
| 스트리밍 | 토큰 스트리밍 | 이벤트 스트리밍 | 멀티모달 | ~30% |
| 배포 도구 | 미구현 | Platform | Vertex AI | 0% |
| 평가 프레임워크 | 미구현 | LangSmith | 내장 | 0% |

---

### Phase 1: 코어 안정화 (Core Stabilization)

현재 구현을 배포 가능한 수준으로 다듬는 단계입니다.

- [ ] **패키지 배포 구조** — `pyproject.toml` 정비, PyPI 배포 준비
- [ ] **WebSearch Tool 실제 API 연동** — Serper, Tavily 등 실제 검색 API 연결 (현재 mock)
- [ ] **Gemini Client 스트리밍** — 현재 폴백 방식, 네이티브 SSE 스트리밍으로 전환
- [ ] **에러 핸들링 강화** — 스트리밍 중 에러 복구, 지수 백오프 재시도 로직
- [ ] **Tool 출력값 스키마 검증** — OutputModel validation 추가
- [ ] **로깅 시스템 통합** — 구조화 로깅, 레벨별 설정

---

### Phase 2: 상태 & 메모리 (State & Memory)

현재 `AgentRuntime`은 인메모리 히스토리만 유지하며, 세션 간 상태 영속화 기능이 없습니다.

- [ ] **Session 기반 상태 관리 (`SessionService`)**
  - LangGraph: Thread 기반 상태 + Checkpointer
  - Google ADK: `session.state` + `user:/app:` 스코프 분리
  - Sonya 목표: session_id 기반 상태 조회/갱신 서비스

- [ ] **대화 히스토리 영속화**
  - SQLite/Postgres 백엔드
  - 세션 재개 시 히스토리 복원

- [ ] **장기 메모리 시스템 (cross-session)**
  - LangGraph: LangMem / Store
  - Google ADK: `MemoryService`
  - Sonya 목표: 벡터 DB 기반 의미론적 메모리 검색

- [ ] **체크포인팅 / 실행 상태 저장-복원**
  - LangGraph: 매 super-step 자동 저장, 시간여행 디버깅
  - Google ADK: 이벤트 기반 체크포인트

---

### Phase 3: 멀티 에이전트 오케스트레이션 (Multi-Agent)

현재는 단일 에이전트 루프만 지원합니다.

- [ ] **에이전트 계층 구조 (parent-child)**
  - LangGraph: Sub-graph composition
  - Google ADK: `sub_agents` 리스트 + `transfer_to_agent()`
  - Sonya 목표: 부모 에이전트가 자식 에이전트를 Tool로 호출하는 패턴

- [ ] **워크플로우 에이전트 패턴**
  - Sequential Agent — 정해진 순서로 에이전트 체인 실행
  - Parallel Agent — 여러 에이전트 병렬 실행 후 결과 집계
  - Loop Agent — 조건 충족까지 에이전트 반복 실행

- [ ] **에이전트 간 통신 프로토콜** — 메시지 포맷 표준화
- [ ] **동적 라우팅** — LLM이 다음 에이전트를 선택하는 패턴
- [ ] **A2A (Agent-to-Agent) 프로토콜 지원** — 외부 에이전트와 상호운용

---

### Phase 4: Human-in-the-Loop

에이전트 실행 중 사람이 개입할 수 있는 메커니즘이 없습니다.

- [ ] **실행 중단/재개 (Interrupt/Resume)**
  - LangGraph: `interrupt()` + `Command(resume=...)`
  - Google ADK: 콜백 기반 중단
  - Sonya 목표: `await agent.interrupt()` / `agent.resume(value)` API

- [ ] **Tool 실행 전 승인/거부/수정 패턴**
  - 민감한 Tool(파일 쓰기, API 호출 등) 실행 전 사용자 확인 요청

- [ ] **사용자 입력 대기 및 주입**
  - 에이전트가 추가 정보 요청 시 실행을 일시 정지하고 입력을 기다리는 패턴

---

### Phase 5: 관찰성 & 안전성 (Observability & Safety)

현재는 Python 표준 `logging`만 사용하며, 구조화된 추적/감사 기능이 없습니다.

- [ ] **실행 추적 (Tracing) 시스템**
  - LangGraph: LangSmith 통합
  - Google ADK: Cloud Trace + 3-layer 아키텍처
  - Sonya 목표: span 기반 추적, OpenTelemetry 호환

- [ ] **콜백/미들웨어 시스템**
  - `before_agent` / `after_agent`
  - `before_tool` / `after_tool`
  - `before_model` / `after_model`

- [ ] **가드레일 (Guardrails)**
  - 입력/출력 필터링
  - 콘텐츠 안전성 검사
  - 정책 기반 Tool 실행 제어

- [ ] **토큰/비용 추적** — Provider별 사용량 집계, 비용 계산

---

### Phase 6: 스트리밍 & 배포 (Streaming & Deployment)

현재는 텍스트 토큰 스트리밍만 지원합니다.

- [ ] **이벤트 스트리밍** — 노드 진입/퇴출, Tool 실행 시작/완료, 상태 변경 이벤트
- [ ] **SSE (Server-Sent Events) 지원** — HTTP 스트리밍 엔드포인트
- [ ] **MCP (Model Context Protocol) Tool 지원** — MCP 서버의 Tool을 `BaseTool`로 브리징
- [ ] **CLI 개발 서버** — `sonya serve` 명령어로 로컬 에이전트 서버 실행
- [ ] **컨테이너 배포 가이드** — Docker, Cloud Run 배포 레시피

---

### Phase 7: 평가 & 테스트 (Evaluation)

에이전트 품질을 측정하는 체계가 없습니다.

- [ ] **에이전트 평가 프레임워크**
  - LangGraph: LangSmith 평가 기능
  - Google ADK: 내장 평가 파이프라인
  - Sonya 목표: 품질/관련성/정확성 메트릭, 궤적 평가(Tool 선택 전략 분석)

- [ ] **벤치마크 데이터셋 지원** — 표준 에이전트 벤치마크 연동
- [ ] **회귀 테스트 자동화** — PR 단위 에이전트 동작 회귀 감지

---

## 테스트

```bash
pytest
```

6개 파일, 70+ 테스트 케이스:

| 파일 | 대상 |
|---|---|
| `test_tools.py` | BaseTool, ToolRegistry, ToolContext |
| `test_llm_models.py` | LLMResponse, Message, ContentBlock |
| `test_llm_client.py` | AnthropicClient |
| `test_openai_client.py` | OpenAIClient |
| `test_runtime.py` | AgentRuntime (run / run_stream) |
| `test_extensions.py` | 확장/통합 시나리오 |

## 기여 가이드

- 기존 패턴과 네이밍을 우선 따릅니다.
- 새 Tool 추가 시 `BaseTool[InputModel, OutputModel]`을 상속하고 `name`, `description`, `execute()` 구현
- Pydantic `Field(description=...)` 으로 LLM에 전달할 파라미터 설명 명시
- 코드 주석과 docstring은 한국어로 작성
- 변경 후 관련 테스트를 반드시 실행합니다.
- 요청 범위를 벗어나는 리팩터링은 지양합니다.
- 세부 규칙은 `AGENTS.md`를 기준으로 합니다.

## 문서

- 코어 패키지 상세 문서: `src/sonya-core/README.md`
- 작업/코딩 규칙: `AGENTS.md`
