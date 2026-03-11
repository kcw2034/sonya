# sonya-cli

Sonya 프레임워크의 CLI 패키지입니다. `textual` 기반 TUI 채팅
인터페이스를 제공합니다.

## 설치

```bash
pip install -e .
```

로컬 워크스페이스 의존성과 함께 개발 모드로 실행하려면:

```bash
uv sync
```

## 실행

```bash
sonya chat
```

기본 명령(`sonya`)도 `chat`과 동일하게 동작합니다.

API 키 등록:

```bash
sonya auth
sonya auth anthropic
sonya auth openai
sonya auth google
```

Gateway 서버 단독 실행:

```bash
sonya gateway start --host 127.0.0.1 --port 8340
```

패키지 디렉터리에서 실행하려면:

```bash
uv run sonya chat
```

## 구조

```text
src/sonya/cli/
├── client/
│   ├── cli.py                # Cyclopts 엔트리포인트
│   ├── app.py                # SonyaTUI 애플리케이션 + gateway subprocess
│   └── gateway_client.py     # sonya-gateway REST/SSE 클라이언트
└── utils/
    ├── auth.py               # API 키 조회/저장(.env)
    ├── chat_screen.py        # 메인 화면 로직(세션/스트리밍/단축키)
    ├── settings_panel.py     # 모델 선택 + 시스템 프롬프트 + 세션 리셋
    └── chat_panel.py         # 로그/입력/Thinking indicator
```

## 환경 변수

앱 시작 시 `python-dotenv`로 `.env`를 로드합니다.
`sonya auth` 명령으로 `.env`에 키를 저장할 수 있습니다.

- Anthropic: `ANTHROPIC_API_KEY`
- OpenAI: `OPENAI_API_KEY`
- Gemini: `GOOGLE_API_KEY`

## 단축키

- `Ctrl+C`: 종료
- `Ctrl+D`: 다크/라이트 테마 전환
- `Ctrl+B`: 설정 패널 포커스
- `Ctrl+N`: 채팅 입력 포커스
- `Ctrl+Y`: 마지막 어시스턴트 응답 복사
