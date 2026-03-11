# Agents.md

## Conventions

- 코드 주석과 docstring은 영어로 작성
- 사용자가 알아야 하는 함수엔 언더바를 빼고, 사용자가 몰라도 되는 내부 로직이나 변수에는 언더바를 붙이는 설계 패턴 사용
- 타입 힌트 작성 시 PEP 604(Union Type Expressions)의 | (Pipe Syntax) 패턴을 우선적으로 사용. (예: int | str, float | None)
- Indentation: 공백(Space) 4칸 사용 (Tab 사용 금지).
- Line Length: 한 줄 최대 80자 (부득이한 경우 100자까지 허용).
- Blank Lines: 최상위 수준(클래스/함수 간)은 2줄 간격. 클래스 내부 메서드 간은 1줄 간격.
- Quotes: 문자열은 가급적 작은따옴표(')를 사용하고, Docstring은 큰따옴표 세 개(""")를 사용.
- Import 순서: 1. Standard Library (내장 모듈), 2. Third-party Libraries (외부 라이브러리),3. Local Application (프로젝트 내부 모듈)
- Import 방식: 한 줄에 하나의 모듈만 임포트.
- Type Hints: 모든 함수의 인자와 반환값에 타입을 명시합니다.
- Docstrings: 함수 시작 직후 """를 사용하여 목적, Args, Returns를 작성합니다. 복잡한 로직이 아니더라도 공용 인터페이스에는 필수입니다.
- Explicit is better than implicit: 암시적인 것보다 명시적인 코드를 지향합니다.
- Error Handling: except: 와 같이 광범위한 예외 처리는 피하고, 구체적인 Exception을 명시합니다.
- None Check: if x is None: 처럼 is 또는 is not을 사용하여 체크합니다.

### Naming
| 대상 | 스타일 | 예시 |
| --- | --- | --- |
| Packages / Modules | lower_case | agent_utils.py, core/ |
| Classes | PascalCase | class SearchAgent: |
| Functions / Methods | snake_case | def run_task(): |
| Variables | snake_case | user_input = ""..."" |
| Constants | UPPER_CASE | MAX_RETRY = 3 |
| Internal | _leading_underscore | `def _helper_func():` |

## Commands

```bash
# 가상환경 활성화
source .venv/bin/activate
```

## Project Structure

- Monorepo with 5 packages under `packages/`: sonya-core, sonya-cli, sonya-extension, sonya-pack, sonya-pipeline
- Python 3.11+, `uv` package manager, `setuptools` build backend
- Each package has its own `pyproject.toml`, `src/`, `tests/`
- 언어: 코드 주석/docstring은 영어, 사용자 대화는 한국어
