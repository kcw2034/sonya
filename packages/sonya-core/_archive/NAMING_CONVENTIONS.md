# sonya-core 네이밍 패턴 규칙

이 문서는 기존 README/가이드 문서를 수정하지 않고, 기능 단위 네이밍 규칙만 별도로 정의합니다.

## 목적

- 파일/패키지 이름만 보고 역할을 예측할 수 있게 유지
- 기능 단위 모듈의 네이밍을 일관화
- 리팩터링 시 import 경로 변경 범위를 최소화

## 규칙

1. 기능 단위 모듈은 단수형을 기본으로 사용합니다.
   - 예: `error.py`, `context.py`, `registry.py`, `base.py`
   - 비권장: `errors.py`

2. 상태/대화 이력처럼 실행 컨텍스트 성격의 기능은 `context/` 하위로 그룹화합니다.
   - 예: `runtime/context/history.py`

3. 패키지 공개 API는 `__init__.py`에서만 export를 관리합니다.
   - 모듈 이동/리네임 시 `__init__.py` export를 함께 정리합니다.

4. 네이밍 변경 시 레포 전역 import 경로를 동시에 갱신합니다.
   - core 소스, 테스트, 상위 re-export를 한 번에 수정합니다.

5. 공통 헬퍼는 기능 도메인별로 `core/utils/` 트리에 배치합니다.
   - 예: `core/utils/llm/client/openai.py`
   - 예: `core/utils/llm/client/google.py`
   - 예: `core/utils/runtime/history.py`
   - 로깅도 `core/utils/logging.py`에서 관리합니다.

6. `models.py`와 역할적으로 맞닿은 스키마 변환 로직은 같은 도메인 루트에 둡니다.
   - LLM 도메인: `core/llm/models.py` + `core/llm/schema.py`
   - 원칙: 데이터 모델 정의(`models.py`)와 해당 모델의 외부 스키마 변환(`schema.py`)은 같은 패키지 레벨에서 관리합니다.

## 이번 적용 예시

- `sonya/core/llm/errors.py` -> `sonya/core/llm/error.py`
- `sonya/core/runtime/history.py` -> `sonya/core/runtime/context/history.py`
- `runtime/__init__.py`에서 `HistoryConfig`, `HistoryManager`를 공개 API로 export
- LLM/Gemini/OpenAI 변환 헬퍼를 `sonya/core/utils/llm/client/*.py`로 분리
- 스키마 헬퍼를 `sonya/core/llm/schema.py`로 이동 (`models.py`와 같은 도메인 루트로 정렬)
- 로깅 구현을 `sonya/core/utils/logging.py`로 이동

## 향후 리팩터링 기준

- 신규 모듈 생성 시 먼저 기존 디렉터리 규칙(`llm`, `runtime`, `tools`)에 맞춘 뒤 파일명을 결정합니다.
- 같은 책임을 가진 파일이 복수 생기면 폴더를 만들고 하위 파일은 단수 기능명으로 분리합니다.
