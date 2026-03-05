# sonya-cli

Sonya 프레임워크의 CLI 패키지입니다. `textual` 기반 TUI 채팅
인터페이스를 제공합니다.

## 설치

```bash
pip install -e .
```

로컬 `sonya-core`와 함께 개발 모드로 실행하려면:

```bash
uv sync
```

## 실행

```bash
sonya chat
```

또는 패키지 디렉터리에서:

```bash
uv run sonya chat
```

## 구조

```text
src/sonya/cli/
├── cli.py                    # Cyclopts 엔트리포인트 (`sonya chat`)
├── app.py                    # SonyaTUI 애플리케이션 부트스트랩
├── screens/
│   └── chat.py               # SettingsPanel + ChatPanel 조합 메인 화면
├── widgets/
│   ├── settings_panel.py     # 모델 선택, 시스템 프롬프트, 세션 리셋
│   └── chat_panel.py         # 채팅 로그(RichLog), 입력(Input)
└── agent_manager.py          # 프로바이더 선택, 히스토리, 스트리밍 응답 관리
```

## 환경 변수

앱 시작 시 `python-dotenv`로 `.env`를 로드합니다.

- Anthropic 사용 시: `ANTHROPIC_API_KEY`
- OpenAI 사용 시: `OPENAI_API_KEY`
- Gemini 사용 시: `GOOGLE_API_KEY`

## 단축키

- `Ctrl+Q`: 종료
- `Ctrl+D`: 다크/라이트 테마 전환
- `Ctrl+S`: 설정 패널 포커스
- `Ctrl+M`: 채팅 입력 포커스
