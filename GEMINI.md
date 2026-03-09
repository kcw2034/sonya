# Sonya 프로젝트 가이드 (GEMINI.md)

## 프로젝트 개요
Sonya는 공식 SDK(Anthropic, OpenAI, Gemini)를 얇게 감싸(Thin wrapper) 제공하는 경량 Python LLM 클라이언트 프레임워크입니다.
`**kwargs` 패스스루(passthrough)와 인터셉터(Interceptor) 기반의 관측성(observability)을 특징으로 하며, 도구(Tool) 시스템, 에이전트 런타임(Agent Runtime), 오케스트레이션(Orchestration) 기능을 제공합니다.

모노레포(Monorepo) 구조로 구성되어 있으며 주요 패키지는 다음과 같습니다:
- `sonya-core`: 코어 라이브러리 (Client, Tool, Agent, Runtime, Interceptor 구현)
- `sonya-cli`: Textual 기반 TUI 챗 커맨드 (`sonya chat`) 제공
- `sonya-extension`, `sonya-pack`, `sonya-pipeline`: 확장 및 파이프라인 기능을 위한 추가 패키지

## 빌드 및 실행

**참고:** 이 프로젝트의 패키지 및 환경 관리는 `uv`를 기본으로 사용합니다.

### 의존성 설치 (uv 사용)
```bash
# 코어 패키지 설치 (모든 프로바이더 및 개발 의존성 포함)
cd packages/sonya-core
uv pip install -e ".[all,dev]"

# CLI 패키지 설치
cd packages/sonya-cli
uv pip install -e .
```

### 실행
```bash
# CLI 앱 실행 (로컬 환경 변수 .env 로드)
cd packages/sonya-cli
uv run sonya chat
```

### 테스트 실행
테스트는 `pytest` (비동기 테스트를 위한 `pytest-asyncio` 포함)를 사용합니다.
```bash
cd packages/sonya-core
uv run pytest tests/ -v
```

## 개발 컨벤션
- **언어 및 버전:** Python 3.11 이상을 지원합니다.
- **아키텍처 설계:**
  - `BaseClient` ABC를 통한 `generate()` 및 `generate_stream()` 통합 인터페이스 제공.
  - 별도의 커스텀 모델 변환 없이 SDK의 원본 응답(Native SDK Responses)을 그대로 반환.
  - `before_request` 및 `after_response` 프로토콜을 사용한 인터셉터(Interceptor) 패턴 적극 활용.
- **테스트:** 비동기 함수 테스트 시 `pytest.ini`에 `asyncio_mode = auto`가 설정되어 있으므로, 코루틴 테스트에 별도의 `pytest.mark.asyncio` 마커를 명시할 필요가 없습니다.
- **타이핑:** `Typing :: Typed` 속성을 갖춘 프레임워크로, 정적 타입 힌팅을 철저히 준수합니다.
