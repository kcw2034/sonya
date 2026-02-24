---
name: readme-maintenance
description: 프로젝트 README를 코드 구조와 동기화하고 온보딩 중심으로 정리한다
compatibility: opencode
metadata:
  audience: maintainers
  scope: project-readme
---
## 목적

- README를 현재 코드 상태와 일치하게 유지한다.
- 신규 기여자가 5분 내에 구조와 실행 방법을 이해할 수 있게 만든다.

## 적용 기준

- 코드에서 확인 가능한 사실만 문서화한다.
- 파일 경로/명령어/예시 코드가 실제 구조와 맞는지 검증한다.
- 과도한 비교표, 로드맵, 추측성 내용은 README에서 제거하거나 축약한다.

## 업데이트 체크리스트

1. 프로젝트 구조 트리와 실제 디렉터리 일치 여부 확인
2. Quick Start 명령어 실행 가능 여부 확인
3. 코드 예시 import 경로/클래스명 유효성 확인
4. 테스트 명령과 현재 실패 상태(있는 경우) 명시
5. OpenCode 관련 파일 위치(agents/commands/skills) 최신화

## 결과물 형식

- 변경 요약 3~5줄
- 수정 파일 경로
- 검증 명령과 결과
