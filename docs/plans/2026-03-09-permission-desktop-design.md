# Permission-Based Desktop Automation Design

## Overview

Config-based permission system with risk-level gating for desktop
automation tools in sonya sessions. Tools are assigned risk levels
(`low`, `medium`, `high`) and the permission config determines which
levels are allowed to execute.

## Permission Model

### Risk Levels

| Level    | Value | Scope                        | Examples                          |
|----------|-------|------------------------------|-----------------------------------|
| `low`    | 1     | Read-only, non-destructive   | screenshot, file_read, list_files |
| `medium` | 2     | Input control, limited write | mouse_click, keyboard_type, app_launch |
| `high`   | 3     | Destructive, system-level    | file_delete, shell_execute        |

### Config File

Location: `.sonya/permissions.json`

```json
{
    "permission_level": "medium",
    "denied_tools": [],
    "allowed_tools": []
}
```

- `permission_level`: Global allowed level (default: `medium`)
- `denied_tools`: Block specific tools regardless of level
- `allowed_tools`: Allow specific tools regardless of level

### Default Behavior

- Default permission level: `medium` (value <= 2 allowed)
- If config file is missing, defaults apply
- Denied/allowed lists override the level-based check

## Core Changes (sonya-core)

### Tool Dataclass

Add `risk_level: str = 'low'` field to `Tool`.

### @tool Decorator

Add `risk_level` parameter:

```python
@tool(description='Capture screenshot', risk_level='low')
def screenshot() -> str: ...
```

### PermissionConfig

New dataclass in `sonya/core/schemas/`:

```python
@dataclass(frozen=True)
class PermissionConfig:
    permission_level: str = 'medium'
    denied_tools: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
```

With `load()` and `save()` classmethods for JSON file I/O.

### ToolRegistry

- Accept optional `PermissionConfig`
- In `execute()`: check permission before running tool
- On denial: return `ToolResult` with skip message, do not raise

## Desktop Tools (sonya-core)

### Dependencies

- `pyautogui` - mouse/keyboard control
- `Pillow` - screenshot capture

### Tool List

| Category | Tool             | Risk   | Description              |
|----------|------------------|--------|--------------------------|
| Screen   | screenshot       | low    | Capture screen → base64  |
| Screen   | get_screen_size  | low    | Return screen resolution |
| Mouse    | mouse_click      | medium | Click at coordinates     |
| Mouse    | mouse_move       | medium | Move cursor              |
| Mouse    | mouse_drag       | medium | Drag from A to B         |
| Keyboard | keyboard_type    | medium | Type text                |
| Keyboard | keyboard_hotkey  | medium | Press key combination    |
| File     | file_read        | low    | Read file contents       |
| File     | file_write       | medium | Write to file            |
| File     | file_delete      | high   | Delete file              |
| File     | list_files       | low    | List directory contents  |
| App      | app_launch       | medium | Launch application       |
| Shell    | shell_execute    | high   | Execute shell command    |

### Module Structure

```
sonya/core/tools/
    __init__.py
    desktop/
        __init__.py
        _screen.py
        _mouse.py
        _keyboard.py
        _file.py
        _app.py
        _shell.py
```

## TUI Changes (sonya-cli)

### SettingsPanel Addition

Add Permission section to the existing SettingsPanel:

- Level dropdown: `low` / `medium` / `high`
- Display denied/allowed tool counts
- "Edit Config" button to open JSON in system editor
- Changes save to `.sonya/permissions.json` immediately

### Data Flow

```
TUI SettingsPanel
    -> PermissionConfig load/save (.sonya/permissions.json)
    -> ToolRegistry receives PermissionConfig
    -> LLM requests tool call
    -> ToolRegistry.execute()
        -> Permission check pass -> execute tool
        -> Permission check fail -> skip + return denial message
```

## Approach

Decorator-based: risk_level is declared at tool definition, checked
at execution time in ToolRegistry. Single point of enforcement.
