# sonya-cli

CLI package for the Sonya framework. It provides a `textual`-based
TUI chat interface.

## Installation

```bash
pip install -e .
```

To run in development mode with local workspace dependencies:

```bash
uv sync
```

## Run

```bash
sonya chat
```

The default command (`sonya`) behaves the same as `chat`.

Configure API keys:

```bash
sonya auth
sonya auth anthropic
sonya auth openai
sonya auth google
```

Run the gateway server standalone:

```bash
sonya gateway start --host 127.0.0.1 --port 8340
```

To run from the package directory:

```bash
uv run sonya chat
```

## Structure

```text
src/sonya/cli/
├── client/
│   ├── cli.py                # Cyclopts entrypoint
│   ├── app.py                # SonyaTUI app + gateway subprocess
│   └── gateway_client.py     # sonya-gateway REST/SSE client
└── utils/
    ├── auth.py               # API key lookup/save (.env)
    ├── chat_screen.py        # main screen logic (session/stream/keys)
    ├── settings_panel.py     # model/system prompt/session reset
    └── chat_panel.py         # log/input/thinking indicator
```

## Environment Variables

The app loads `.env` on startup via `python-dotenv`.
You can save keys into `.env` with `sonya auth`.

- Anthropic: `ANTHROPIC_API_KEY`
- OpenAI: `OPENAI_API_KEY`
- Gemini: `GOOGLE_API_KEY`

## Shortcuts

- `Ctrl+C`: Quit
- `Ctrl+D`: Toggle dark/light theme
- `Ctrl+B`: Focus settings panel
- `Ctrl+N`: Focus chat input
- `Ctrl+Y`: Copy last assistant response
