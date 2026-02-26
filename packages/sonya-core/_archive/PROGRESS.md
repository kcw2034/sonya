# Sonya Core — 기능별 진행도 비교

> 비교 대상: **LangGraph v1.0** / **Google ADK** (2025 기준)
> 최종 업데이트: 2026-02-26

## 종합 요약

| 카테고리 | Sonya Core | LangGraph | Google ADK |
|---|:---:|:---:|:---:|
| Tool 시스템 | **70%** | 95% | 90% |
| LLM 통합 | **75%** | 95% | 90% |
| Agent Runtime | **55%** | 90% | 85% |
| Graph/Workflow | **5%** | 95% | 80% |
| Memory | **15%** | 90% | 75% |
| Multi-Agent | **0%** | 90% | 90% |
| Observability | **10%** | 95% | 85% |
| Deployment | **0%** | 90% | 85% |
| Human-in-the-Loop | **0%** | 90% | 70% |
| Guardrails/Safety | **5%** | 70% | 80% |
| **종합** | **~24%** | **~90%** | **~83%** |

---

## 1. Tool 시스템 — Sonya 70%

| 기능 | Sonya | LangGraph | Google ADK | 비고 |
|---|:---:|:---:|:---:|---|
| Tool 정의 (베이스 클래스) | ✅ | ✅ | ✅ | `BaseTool[InputT, OutputT]` 제네릭 패턴 |
| JSON Schema 자동 생성 | ✅ | ✅ | ✅ | Pydantic 모델에서 자동 추출 |
| Input 검증 (Pydantic) | ✅ | ✅ | ✅ | `safe_execute()`에서 `model_validate()` |
| Output 검증 | ✅ | ✅ | ✅ | OutputT 스키마 검증 |
| 에러 핸들링 | ✅ | ✅ | △ | `ToolError(recoverable=True)` 패턴 |
| 병렬 Tool 실행 | ✅ | ✅ | ✅ | `execute_many()` — `asyncio.gather()` |
| Tool Context (상태 공유) | ✅ | ✅ | ✅ | `ToolContext` — 타입 안전 KV 저장소 |
| Tool 생명주기 (setup/teardown) | ✅ | △ | △ | `async setup()` / `teardown()` 훅 |
| 동적 Tool 로딩 (설정 기반) | ✅ | ✅ | △ | `load_registry_from_config()` |
| 멀티 프로바이더 스키마 | ✅ | ✅ | ✅ | Anthropic + OpenAI 포맷 지원 |
| MCP Tool 통합 | ❌ | ✅ | ✅ | 미구현 |
| 내장 Tool 라이브러리 | △ | ✅ | ✅ | calculator, write_file만 완성 / web_search는 stub |
| OpenAPI Tool 생성 | ❌ | △ | ✅ | 미구현 |

**평가 근거**: 핵심 Tool 인프라(정의, 스키마, 검증, 실행, 레지스트리)는 완성도가 높음. MCP 통합과 풍부한 내장 Tool이 부족.

---

## 2. LLM 통합 — Sonya 75%

| 기능 | Sonya | LangGraph | Google ADK | 비고 |
|---|:---:|:---:|:---:|---|
| 멀티 프로바이더 지원 | ✅ | ✅ | ✅ | Anthropic, OpenAI, Gemini 3개 클라이언트 |
| 메시지 포맷 추상화 | ✅ | ✅ | ✅ | 내부적으로 Anthropic 포맷 표준화 |
| 스트리밍 (토큰 단위) | ✅ | ✅ | ✅ | 3대 프로바이더 모두 SSE 스트리밍 구현 완료 |
| 재시도 / 에러 핸들링 | ✅ | ✅ | △ | 지수 백오프 재시도 + `LLMAPIError` |
| Structured Output | ✅ | ✅ | ✅ | `chat_structured()` — 프로바이더별 네이티브 구현 |
| 콜백 / 미들웨어 | ❌ | ✅ | ✅ | 미구현 |
| 노드별 모델 교체 | ❌ | ✅ | ✅ | 단일 클라이언트만 지원 |
| SDK 비의존 (httpx only) | ✅ | ❌ | ❌ | Sonya 고유 장점 — 경량 |
| 멀티모달 (이미지/오디오) | ❌ | ✅ | ✅ | 미구현 |

**평가 근거**: 3대 프로바이더 클라이언트, 재시도, 스트리밍, Structured Output 모두 완성. 콜백·멀티모달 미지원.

---

## 3. Agent Runtime — Sonya 55%

| 기능 | Sonya | LangGraph | Google ADK | 비고 |
|---|:---:|:---:|:---:|---|
| Agent 루프 (tool use → result) | ✅ | ✅ | ✅ | `AgentRuntime.run()` |
| 최대 반복 제한 | ✅ | ✅ | ✅ | `max_iterations=10` |
| 대화 히스토리 관리 | ✅ | ✅ | ✅ | `_history` 리스트 |
| 스트리밍 응답 | ✅ | ✅ | ✅ | `run_stream()` — 토큰 단위 yield |
| 히스토리 초기화 | ✅ | ✅ | ✅ | `reset()` |
| 내구성 실행 (Durable Execution) | ❌ | ✅ | △ | 서버 재시작 후 재개 불가 |
| 히스토리 트리밍/요약 | ❌ | ✅ | ✅ | 컨텍스트 윈도우 관리 없음 |
| 비동기 + 동기 API | △ | ✅ | ✅ | async만 지원 |
| 이벤트 기반 아키텍처 | ❌ | ✅ | ✅ | 미구현 |

**평가 근거**: 기본 에이전트 루프와 스트리밍은 동작하나, 내구성 실행·히스토리 관리·이벤트 아키텍처 부재.

---

## 4. Graph / Workflow — Sonya 5%

| 기능 | Sonya | LangGraph | Google ADK | 비고 |
|---|:---:|:---:|:---:|---|
| State Graph | ❌ | ✅ | — | LangGraph 핵심 추상화 |
| 조건부 라우팅 | ❌ | ✅ | ✅ | 미구현 |
| 분기 (Fan-out) | ❌ | ✅ | ✅ | 미구현 |
| 순환 (Cycles) | ❌ | ✅ | ✅ | 미구현 |
| 서브그래프 | ❌ | ✅ | ✅ | 미구현 |
| Sequential Workflow | ❌ | ✅ | ✅ | 미구현 |
| Parallel Workflow | ❌ | ✅ | ✅ | 미구현 |
| Custom Control Flow | △ | ✅ | ✅ | `max_iterations` 수준의 단순 루프만 |

**평가 근거**: 워크플로우 엔진 자체가 없음. 단일 에이전트 루프만 존재.

---

## 5. Memory — Sonya 15%

| 기능 | Sonya | LangGraph | Google ADK | 비고 |
|---|:---:|:---:|:---:|---|
| 단기 메모리 (세션 내) | ✅ | ✅ | ✅ | `_history` + `ToolContext` |
| 장기 메모리 (세션 간) | ❌ | ✅ | ✅ | 미구현 |
| 체크포인팅 | ❌ | ✅ | △ | 미구현 |
| 시맨틱 검색 메모리 | ❌ | ✅ | △ | 미구현 |
| 유저/앱 스코프 메모리 | ❌ | ✅ | ✅ | 미구현 |
| 메모리 백엔드 (DB) | ❌ | ✅ | ✅ | 미구현 |
| 타임트래블 디버깅 | ❌ | ✅ | △ | 미구현 |

**평가 근거**: 세션 내 히스토리만 존재. 영속성·체크포인트·검색 메모리 전무.

---

## 6. Multi-Agent — Sonya 0%

| 기능 | Sonya | LangGraph | Google ADK | 비고 |
|---|:---:|:---:|:---:|---|
| Agent 간 통신 | ❌ | ✅ | ✅ | 미구현 |
| Supervisor 패턴 | ❌ | ✅ | ✅ | 미구현 |
| 계층적 에이전트 | ❌ | ✅ | ✅ | 미구현 |
| Agent Handoff | ❌ | ✅ | ✅ | 미구현 |
| A2A 프로토콜 | ❌ | △ | ✅ | 미구현 |
| 병렬 멀티에이전트 실행 | ❌ | ✅ | ✅ | 미구현 |

**평가 근거**: `sonya-agent` 패키지가 빈 셸 상태. 멀티에이전트 기능 전무.

---

## 7. Observability — Sonya 10%

| 기능 | Sonya | LangGraph | Google ADK | 비고 |
|---|:---:|:---:|:---:|---|
| 구조화 로깅 | ✅ | ✅ | ✅ | JSON 포맷터 구현 |
| 트레이싱 | ❌ | ✅ | ✅ | OpenTelemetry 미연동 |
| 디버깅 UI | ❌ | ✅ | ✅ | 미구현 |
| 3rd-party 연동 | ❌ | ✅ | ✅ | 미구현 |
| 평가(Evals) | ❌ | ✅ | ✅ | 미구현 |
| 토큰/비용 추적 | ❌ | ✅ | ✅ | `Usage` 모델은 있으나 집계 없음 |

**평가 근거**: JSON 로깅만 존재. 트레이싱·디버깅·평가 인프라 전무.

---

## 8. Deployment — Sonya 0%

| 기능 | Sonya | LangGraph | Google ADK | 비고 |
|---|:---:|:---:|:---:|---|
| 매니지드 클라우드 | ❌ | ✅ | ✅ | 미구현 |
| 셀프호스트 / Docker | ❌ | ✅ | ✅ | 미구현 |
| API 서버 | ❌ | ✅ | ✅ | 미구현 |
| 수평 스케일링 | ❌ | ✅ | ✅ | 미구현 |
| CLI 배포 도구 | ❌ | ✅ | ✅ | 미구현 |

**평가 근거**: 배포 관련 기능 없음. 라이브러리로만 사용 가능.

---

## 9. Human-in-the-Loop — Sonya 0%

| 기능 | Sonya | LangGraph | Google ADK | 비고 |
|---|:---:|:---:|:---:|---|
| 실행 중단 / 브레이크포인트 | ❌ | ✅ | ✅ | 미구현 |
| 승인 플로우 | ❌ | ✅ | ✅ | 미구현 |
| 상태 편집 후 재개 | ❌ | ✅ | △ | 미구현 |
| 비차단 대기 | ❌ | ✅ | ✅ | 미구현 |

**평가 근거**: HITL 기능 전무.

---

## 10. Guardrails / Safety — Sonya 5%

| 기능 | Sonya | LangGraph | Google ADK | 비고 |
|---|:---:|:---:|:---:|---|
| Input 검증 | △ | ✅ | ✅ | Pydantic 수준만 (콘텐츠 필터 없음) |
| Output 검증 | △ | ✅ | ✅ | 스키마 검증만 |
| 경로 순회 방어 | ✅ | — | — | `WriteFileTool` 구현 |
| 안전한 코드 실행 | ✅ | — | — | AST 기반 calculator (eval 미사용) |
| PII 탐지 | ❌ | ✅ | △ | 미구현 |
| 콘텐츠 안전 필터 | ❌ | △ | ✅ | 미구현 |
| Rate Limiting | ❌ | △ | △ | 미구현 |
| 프롬프트 인젝션 방어 | ❌ | △ | ✅ | 미구현 |

**평가 근거**: Tool 레벨의 보안(경로 순회, 안전한 eval)은 잘 되어 있으나, 프레임워크 수준 가드레일 없음.

---

## Sonya Core 강점 (차별화 포인트)

| 강점 | 설명 |
|---|---|
| **경량 / 무의존성** | SDK 없이 `httpx` + `pydantic`만으로 3대 LLM 프로바이더 지원 |
| **제네릭 타입 안전** | `BaseTool[InputT, OutputT]` — 런타임에서 타입 힌트 자동 추출 |
| **Sync→Async 자동 변환** | `__init_subclass__`에서 동기 `execute()`를 자동으로 `asyncio.to_thread()` 래핑 |
| **프로바이더 투명 추상화** | 내부 Anthropic 포맷으로 통일 → `AgentRuntime`은 프로바이더 무관 |
| **안전한 Tool 실행** | AST 기반 calculator, 경로 순회 방어 등 보안 우선 설계 |
| **네이티브 Structured Output** | 프로바이더별 최적 방식 자동 선택 (Anthropic: tool_choice, OpenAI: json_schema, Gemini: responseSchema) |

---

## 우선순위 로드맵 제안

### Phase 1 — 핵심 격차 해소 (현재 → 40%)
1. ~~OpenAI / Gemini 스트리밍 구현~~ ✅ 완료
2. ~~Structured Output 지원~~ ✅ 완료
3. 히스토리 트리밍 / 요약 전략
4. OpenTelemetry 트레이싱 연동
5. 내장 Tool 확충 (web_search 실제 연동)

### Phase 2 — 워크플로우 엔진 (40% → 60%)
6. 워크플로우 추상화 (Sequential, Parallel, Conditional)
7. 체크포인팅 / 상태 영속성
8. 콜백 / 미들웨어 시스템
9. MCP Tool 통합

### Phase 3 — 멀티에이전트 & 프로덕션 (60% → 80%)
10. 멀티에이전트 오케스트레이션
11. Human-in-the-Loop (브레이크포인트, 승인 플로우)
12. API 서버 / 배포 도구
13. 가드레일 프레임워크
14. 장기 메모리 백엔드
