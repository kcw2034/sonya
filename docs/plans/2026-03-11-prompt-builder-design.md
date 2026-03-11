# Prompt Builder 설계

> Date: 2026-03-11
> Status: Approved
> Package: sonya-core

## 목적

sonya-core의 프롬프트 시스템을 개선하여:

1. **구조화된 프롬프트**: 역할/가이드라인/제약/예시/출력형식을 명명된 섹션으로 구성
2. **Few-shot 예시 관리**: Example 데이터클래스로 체계적 관리
3. **동적 프롬프트 생성**: f-string 템플릿 + `render(**context)`로 런타임 치환
4. **OpenAI 시스템 메시지 버그 수정**: instructions가 system message로 주입되지 않는 문제 해결

## 결정 사항

| 항목 | 결정 |
|------|------|
| 패키지 위치 | sonya-core |
| instructions 타입 | `str \| Prompt` (하위 호환) |
| 구조화 수준 | 섹션 기반 (role, guidelines, constraints, examples, output_format) |
| 동적 생성 | `render(**context)` + `str.format_map()` |
| 아키텍처 | Prompt frozen dataclass 단독 (빌더 패턴 없음) |
| OpenAI 버그 | 같이 수정 |

## 데이터 모델

### Example

```python
@dataclass(frozen=True, slots=True)
class Example:
    """Few-shot example pair."""
    user: str
    assistant: str
```

### Prompt

```python
@dataclass(frozen=True, slots=True)
class Prompt:
    """Structured prompt with named sections."""
    role: str = ''
    guidelines: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    examples: tuple[Example, ...] = ()
    output_format: str = ''
```

**파일 위치**: `packages/sonya-core/src/sonya/core/models/prompt.py`

## render 메서드

```python
def render(self, **context: str) -> str:
    """Render prompt to final string with template substitution.

    Args:
        **context: Template variables for {placeholder} substitution.

    Returns:
        Rendered prompt string with all sections assembled.
    """
```

### 렌더링 규칙

1. 각 섹션이 비어있지 않으면 순서대로 조합
2. 섹션 순서: role → guidelines → constraints → examples → output_format
3. 각 섹션은 헤더 + 내용으로 구성
4. `{variable}` 플레이스홀더를 context dict로 치환 (`str.format_map()`)
5. 치환할 변수가 없으면 원본 유지 (`defaultdict` 활용)

### 렌더링 출력 예시

```python
prompt = Prompt(
    role='You are a {domain} expert.',
    guidelines=(
        'Use tools before answering.',
        'Respond in {language}.',
    ),
    constraints=(
        'Never fabricate data.',
        'Do not exceed {max_tokens} tokens.',
    ),
    examples=(
        Example(user='What is the weather?', assistant='Let me check...'),
    ),
    output_format='Respond in JSON format.',
)
result = prompt.render(domain='weather', language='Korean', max_tokens='500')
```

출력:
```
You are a weather expert.

## Guidelines
- Use tools before answering.
- Respond in Korean.

## Constraints
- Never fabricate data.
- Do not exceed 500 tokens.

## Examples

User: What is the weather?
Assistant: Let me check...

## Output Format
Respond in JSON format.
```

## from_str 팩토리 메서드

```python
@staticmethod
def from_str(text: str) -> 'Prompt':
    """Create a Prompt with the given text as role."""
    return Prompt(role=text)
```

기존 문자열과의 호환을 위한 편의 메서드.

## Agent.instructions 타입 변경

```python
# agent.py
@dataclass(slots=True)
class Agent:
    instructions: str | Prompt = ''
```

## AgentRuntime 통합

`AgentRuntime.run()` 내에서 instructions 처리:

```python
# agent_runtime.py — run() 메서드 내
instructions = agent.instructions
if isinstance(instructions, Prompt):
    instructions = instructions.render()

gen_kwargs = adapter.format_generate_kwargs(
    instructions, schemas
)
```

context를 전달해야 하는 경우, `Agent.run()` 또는 `AgentRuntime.run()`에 `prompt_context: dict` 선택적 매개변수 추가:

```python
async def run(
    self,
    messages: list[dict[str, Any]],
    prompt_context: dict[str, str] | None = None,
) -> AgentResult:
    instructions = agent.instructions
    if isinstance(instructions, Prompt):
        instructions = instructions.render(
            **(prompt_context or {})
        )
```

## OpenAI 시스템 메시지 버그 수정

현재: OpenAI 어댑터의 `format_generate_kwargs()`가 instructions를 무시.

수정: `format_generate_kwargs()`에서 instructions를 반환하고, `AgentRuntime`에서 OpenAI일 때 system message로 history에 prepend.

또는 더 간단한 방식: `OpenAIAdapter.format_generate_kwargs()`에서 instructions를 별도 키로 반환하고, `AgentRuntime`이 메시지 포맷팅 시 활용:

```python
# OpenAIAdapter.format_generate_kwargs()
if instructions:
    kwargs['_system_message'] = instructions

# AgentRuntime.run() 내
system_msg = gen_kwargs.pop('_system_message', None)
if system_msg:
    messages = [
        {'role': 'system', 'content': system_msg}
    ] + messages
```

더 깔끔한 접근: `ResponseAdapter` 프로토콜에 `inject_instructions(messages, instructions)` 메서드를 추가하여 각 어댑터가 프로바이더별 방식으로 처리:

```python
# adapter protocol
def inject_instructions(
    self,
    messages: list[dict[str, Any]],
    instructions: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Inject instructions into messages or kwargs.

    Returns:
        Tuple of (modified_messages, extra_kwargs).
    """
```

- **Anthropic**: messages 그대로, `{'system': instructions}` 반환
- **OpenAI**: system message를 messages에 prepend, `{}` 반환
- **Gemini**: messages 그대로, `{'system_instruction': instructions}` 반환

이 방식이 가장 깔끔하고, instructions 주입 로직을 어댑터에 완전 캡슐화합니다.

## 패키지 exports 추가

```python
# __init__.py
"Prompt",
"Example",
```

## 사용 예시

### 기본 사용 (하위 호환)

```python
agent = Agent(
    name='simple',
    client=client,
    instructions='You are a helpful assistant.',
)
```

### 구조화된 프롬프트

```python
agent = Agent(
    name='weather_bot',
    client=client,
    instructions=Prompt(
        role='You are a weather assistant.',
        guidelines=(
            'Use the get_weather tool before answering.',
            'Always include temperature in Celsius.',
        ),
        constraints=(
            'Never fabricate weather data.',
            'Only answer weather-related questions.',
        ),
        examples=(
            Example(
                user='What is the weather in Seoul?',
                assistant='Let me check the weather in Seoul for you.',
            ),
        ),
        output_format='Include location, temperature, and conditions.',
    ),
    tools=[get_weather],
)
```

### 동적 프롬프트

```python
agent = Agent(
    name='translator',
    client=client,
    instructions=Prompt(
        role='You are a {source_lang} to {target_lang} translator.',
        guidelines=('Preserve the original tone and style.',),
        constraints=('Do not add explanations.',),
    ),
)
result = await AgentRuntime(agent).run(
    messages,
    prompt_context={
        'source_lang': 'English',
        'target_lang': 'Korean',
    },
)
```
