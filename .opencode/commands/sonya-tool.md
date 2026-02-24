---
description: Sonya용 새 Tool 구현 계획/스캐폴딩 가이드
agent: sonya-build
---
요청된 Tool 이름과 목적: $ARGUMENTS

다음 기준으로 구현 계획을 제시하고 바로 코드 작업까지 진행해줘.

- `BaseTool[InputModel, OutputModel]` 상속
- 입력 파라미터에 `Field(description=...)` 명시
- 실패는 `ToolError`로 처리, recoverable 여부 명확화
- 주석/docstring은 한국어 사용
- 관련 테스트를 `tests/`에 추가 또는 보완

완료 후 실행한 검증 커맨드와 결과를 함께 보고해줘.
