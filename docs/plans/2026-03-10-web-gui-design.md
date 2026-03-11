# Web GUI for Sonya Gateway — Design

## Overview

Server-side rendered web chat GUI integrated into sonya-gateway,
deployable on Cloud Run. Jinja2 templates + vanilla JS for minimal
loading time. Supports multi-session chat with model selection,
tone presets, and extensible tool buttons.

## Architecture

- Integrate directly into sonya-gateway FastAPI app
- `GET /` serves Jinja2-rendered chat page
- Existing REST + SSE endpoints reused as-is
- API keys from server environment variables (no user input)
- No authentication initially (internal use), extensible later

## Project Structure

```
packages/sonya-gateway/src/sonya/gateway/
    server.py          # existing API + new HTML route
    session.py         # existing, no changes
    schemas.py         # existing, minor additions
    templates/
        base.html      # common layout
        chat.html      # chat GUI page
    static/
        css/
            style.css  # lightweight CSS, no framework
        js/
            app.js     # SSE streaming + multi-session logic

deploy/
    cloud-run/
        Dockerfile
        .dockerignore
```

## Route Structure

- `GET /` → Chat GUI (Jinja2)
- `POST /sessions` → Create session (existing)
- `DELETE /sessions/{id}` → Delete session (existing)
- `PATCH /sessions/{id}` → Update session (existing)
- `POST /sessions/{id}/chat` → SSE streaming (existing)

## UI Layout

```
┌─────────────────────────────────────────────────┐
│ ☰  Sonya                                       │
├──────────┬──────────────────────────────────────┤
│ [+ New]  │                                      │
│ ──────── │  User:                               │
│ Chat 3 ◀ │  How does Python GIL work?           │
│ Chat 2   │                                      │
│ Chat 1   │  Sonya:                               │
│          │  The GIL is a mutex that protects...  │
│          │                                      │
│          ├──────────────────────────────────────┤
│          │  ┌──────────────────────────────┐    │
│          │  │ Message...                   │    │
│          │  └──────────────────────────────┘    │
│          │  [tone][research]  [model ▼] [send]  │
└──────────┴──────────────────────────────────────┘
```

### Input Bar (left to right)

- **Left tool buttons**: Tone preset (popover), Deep Research (future)
- **Right**: Model selector dropdown + Send button

### Sidebar

- Top: [+ New Chat] button
- Below: Session list (newest first), click to switch
- Session delete on hover/swipe

### Tone Presets

Button click shows popover with presets:
- Default, Friendly, Formal, Concise
- Selection updates system_prompt via PATCH /sessions/{id}

### Responsive

- Mobile: sidebar toggles via hamburger menu (☰)
- Input area fixed to bottom

## Data Flow

```
Browser GET /
    → Jinja2 renders chat.html
    → app.js loaded

User clicks [+ New Chat]
    → JS: POST /sessions {model, api_key from server env}
    → New session tab appears in sidebar

User sends message
    → JS: POST /sessions/{id}/chat (SSE)
    → EventSource receives chunks
    → Real-time rendering in chat area

User changes tone
    → JS: PATCH /sessions/{id} {system_prompt updated}
    → Applies from next message

User changes model
    → JS: DELETE old session + POST /sessions with new model
    → Preserves chat display, new session underneath
```

## API Key Management

- Server reads from environment: ANTHROPIC_API_KEY,
  OPENAI_API_KEY, GOOGLE_API_KEY
- Session creation auto-injects key based on model prefix
- No key input UI in the web GUI

## Cloud Run Deployment

```
deploy/
    cloud-run/
        Dockerfile      # Python 3.11 slim, installs core + gateway
        .dockerignore
```

- Build context: project root
- Dockerfile installs sonya-core and sonya-gateway
- Entrypoint: uvicorn on PORT env var (Cloud Run provides)
- Secrets: API keys via Cloud Run secret manager

## Dependencies Added

- `jinja2` — FastAPI template rendering

## Future Extensions

- Authentication / user accounts
- Deep Research tool button
- Conversation persistence (DB)
- File upload support
