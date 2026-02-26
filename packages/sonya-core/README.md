# sonya-core

Sonya 프레임워크의 코어 패키지. 공식 LLM SDK를 thin wrapper로 감싸는 경량 클라이언트를 제공합니다.

## 설치

```bash
# 특정 provider
pip install -e ".[anthropic]"
pip install -e ".[openai]"
pip install -e ".[gemini]"

# 전체
pip install -e ".[all,dev]"
```

## 구조

```
src/sonya/core/
├── __init__.py        # 공개 API (AnthropicClient, OpenAIClient, GeminiClient, ...)
├── _types.py          # ClientConfig, Interceptor 프로토콜
└── client/
    ├── _base.py       # BaseClient ABC
    ├── anthropic.py   # anthropic.AsyncAnthropic 래퍼
    ├── openai.py      # openai.AsyncOpenAI 래퍼
    └── gemini.py      # google.genai.Client 래퍼
```

## 사용법

```python
from sonya.core import AnthropicClient, ClientConfig

config = ClientConfig(model="claude-sonnet-4-20250514")
async with AnthropicClient(config) as client:
    # SDK kwargs 그대로 패스스루
    response = await client.generate(
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=2048,
        temperature=0.7,
    )
```

## 설계 원칙

- **Zero core dependencies**: 코어 패키지 자체는 의존성 없음
- **SDK passthrough**: `**kwargs`가 각 SDK 메서드에 그대로 전달
- **Native response**: 통합 응답 모델 없이 SDK 원본 응답 반환
- **Interceptor**: `before_request` / `after_response` 프로토콜로 observability

## 테스트

```bash
pytest tests/ -v
```
