# Permission-Based Desktop Automation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add config-based permission system with risk-level gating and desktop automation tools to sonya-core, with TUI permission management in sonya-cli.

**Architecture:** Decorator-based approach — `@tool` gets a `risk_level` parameter, `Tool` dataclass stores it, `ToolRegistry` checks `PermissionConfig` before execution. Desktop tools are organized by category under `sonya/core/tools/desktop/`. TUI gets a permission section in SettingsPanel.

**Tech Stack:** Python 3.11+, pyautogui, Pillow, Textual

---

### Task 1: Add `risk_level` to Tool dataclass

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/models/tool.py:9-23`
- Test: `packages/sonya-core/tests/test_permission.py`

**Step 1: Write the failing test**

```python
# packages/sonya-core/tests/test_permission.py
"""Tests for permission system."""

from __future__ import annotations

import pytest

from sonya.core.models.tool import Tool


def test_tool_default_risk_level() -> None:
    t = Tool(
        name='test',
        description='test',
        fn=lambda: None,
    )
    assert t.risk_level == 'low'


def test_tool_custom_risk_level() -> None:
    t = Tool(
        name='test',
        description='test',
        fn=lambda: None,
        risk_level='high',
    )
    assert t.risk_level == 'high'


def test_tool_invalid_risk_level() -> None:
    with pytest.raises(ValueError):
        Tool(
            name='test',
            description='test',
            fn=lambda: None,
            risk_level='invalid',
        )
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_permission.py -v`
Expected: FAIL — `risk_level` field does not exist

**Step 3: Write minimal implementation**

In `packages/sonya-core/src/sonya/core/models/tool.py`, add `risk_level` field to `Tool`:

```python
RISK_LEVELS = ('low', 'medium', 'high')


@dataclass(slots=True)
class Tool:
    """Describes a callable tool with its JSON Schema.

    Args:
        name: Unique tool identifier.
        description: Human-readable description for the LLM.
        fn: The async callable to execute.
        schema: JSON Schema for the function parameters.
        risk_level: Risk level ('low', 'medium', 'high').
    """

    name: str
    description: str
    fn: Callable[..., Any]
    schema: dict[str, Any] = field(default_factory=dict)
    risk_level: str = 'low'

    def __post_init__(self) -> None:
        if self.risk_level not in RISK_LEVELS:
            raise ValueError(
                f"Invalid risk_level: '{self.risk_level}'. "
                f"Choose from: {RISK_LEVELS}"
            )
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_permission.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/models/tool.py packages/sonya-core/tests/test_permission.py
git commit -m "feat(sonya-core): add risk_level field to Tool dataclass"
```

---

### Task 2: Add `risk_level` to `@tool` decorator

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/utils/decorator.py:14-71`
- Test: `packages/sonya-core/tests/test_permission.py` (append)

**Step 1: Write the failing test**

Append to `packages/sonya-core/tests/test_permission.py`:

```python
from sonya.core.utils.decorator import tool


def test_decorator_default_risk_level() -> None:
    @tool(description='Test')
    def my_tool(x: int) -> int:
        return x

    assert my_tool.risk_level == 'low'


def test_decorator_custom_risk_level() -> None:
    @tool(description='Dangerous', risk_level='high')
    def danger(x: int) -> int:
        return x

    assert danger.risk_level == 'high'
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_permission.py::test_decorator_custom_risk_level -v`
Expected: FAIL — `tool()` does not accept `risk_level`

**Step 3: Write minimal implementation**

In `packages/sonya-core/src/sonya/core/utils/decorator.py`, add `risk_level` parameter:

```python
def tool(
    name: str | None = None,
    description: str | None = None,
    risk_level: str = 'low',
) -> Callable[..., Tool]:
```

And pass it to the `Tool` constructor at the end of `_decorator`:

```python
        return Tool(
            name=_name,
            description=_description,
            fn=_fn,
            schema=_schema,
            risk_level=risk_level,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_permission.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/utils/decorator.py packages/sonya-core/tests/test_permission.py
git commit -m "feat(sonya-core): add risk_level parameter to @tool decorator"
```

---

### Task 3: Create PermissionConfig

**Files:**
- Create: `packages/sonya-core/src/sonya/core/schemas/permission.py`
- Test: `packages/sonya-core/tests/test_permission.py` (append)

**Step 1: Write the failing test**

Append to `packages/sonya-core/tests/test_permission.py`:

```python
import json
import os

from sonya.core.schemas.permission import PermissionConfig


def test_permission_config_defaults() -> None:
    config = PermissionConfig()
    assert config.permission_level == 'medium'
    assert config.denied_tools == []
    assert config.allowed_tools == []


def test_permission_config_level_value() -> None:
    assert PermissionConfig._level_value('low') == 1
    assert PermissionConfig._level_value('medium') == 2
    assert PermissionConfig._level_value('high') == 3


def test_is_allowed_by_level() -> None:
    config = PermissionConfig(permission_level='medium')
    assert config.is_allowed('screenshot', 'low') is True
    assert config.is_allowed('mouse_click', 'medium') is True
    assert config.is_allowed('shell_execute', 'high') is False


def test_denied_tools_override() -> None:
    config = PermissionConfig(
        permission_level='high',
        denied_tools=['shell_execute'],
    )
    assert config.is_allowed('shell_execute', 'high') is False
    assert config.is_allowed('file_delete', 'high') is True


def test_allowed_tools_override() -> None:
    config = PermissionConfig(
        permission_level='low',
        allowed_tools=['shell_execute'],
    )
    assert config.is_allowed('shell_execute', 'high') is True
    assert config.is_allowed('mouse_click', 'medium') is False


def test_save_and_load(tmp_path) -> None:
    path = tmp_path / '.sonya' / 'permissions.json'
    config = PermissionConfig(
        permission_level='high',
        denied_tools=['shell_execute'],
    )
    config.save(str(path))
    loaded = PermissionConfig.load(str(path))
    assert loaded.permission_level == 'high'
    assert loaded.denied_tools == ['shell_execute']


def test_load_missing_file_returns_default() -> None:
    config = PermissionConfig.load('/nonexistent/path.json')
    assert config.permission_level == 'medium'
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_permission.py::test_permission_config_defaults -v`
Expected: FAIL — module does not exist

**Step 3: Write minimal implementation**

```python
# packages/sonya-core/src/sonya/core/schemas/permission.py
"""Permission configuration for tool risk-level gating."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


_LEVEL_MAP = {'low': 1, 'medium': 2, 'high': 3}


@dataclass(slots=True)
class PermissionConfig:
    """Config-based permission for tool execution.

    Args:
        permission_level: Global allowed risk level.
        denied_tools: Tools blocked regardless of level.
        allowed_tools: Tools allowed regardless of level.
    """

    permission_level: str = 'medium'
    denied_tools: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)

    @staticmethod
    def _level_value(level: str) -> int:
        """Return numeric value for a risk level."""
        return _LEVEL_MAP.get(level, 0)

    def is_allowed(
        self, tool_name: str, risk_level: str
    ) -> bool:
        """Check if a tool is allowed to execute.

        Args:
            tool_name: Name of the tool.
            risk_level: Risk level of the tool.

        Returns:
            True if the tool is allowed, False otherwise.
        """
        if tool_name in self.denied_tools:
            return False
        if tool_name in self.allowed_tools:
            return True
        return (
            self._level_value(risk_level)
            <= self._level_value(self.permission_level)
        )

    def save(self, path: str) -> None:
        """Save config to a JSON file.

        Args:
            path: File path to save to.
        """
        os.makedirs(
            os.path.dirname(path), exist_ok=True
        )
        data = {
            'permission_level': self.permission_level,
            'denied_tools': self.denied_tools,
            'allowed_tools': self.allowed_tools,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    @classmethod
    def load(cls, path: str) -> PermissionConfig:
        """Load config from a JSON file.

        Args:
            path: File path to load from.

        Returns:
            PermissionConfig instance.
        """
        if not os.path.exists(path):
            return cls()
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(
            permission_level=data.get(
                'permission_level', 'medium'
            ),
            denied_tools=data.get('denied_tools', []),
            allowed_tools=data.get('allowed_tools', []),
        )
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_permission.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/schemas/permission.py packages/sonya-core/tests/test_permission.py
git commit -m "feat(sonya-core): add PermissionConfig with JSON load/save"
```

---

### Task 4: Integrate permission check into ToolRegistry

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/models/tool_registry.py:12-102`
- Test: `packages/sonya-core/tests/test_permission.py` (append)

**Step 1: Write the failing test**

Append to `packages/sonya-core/tests/test_permission.py`:

```python
from sonya.core.models.tool_registry import ToolRegistry


@pytest.mark.asyncio
async def test_registry_blocks_high_risk_tool() -> None:
    config = PermissionConfig(permission_level='medium')
    registry = ToolRegistry(permission_config=config)

    @tool(description='Dangerous', risk_level='high')
    def danger(x: int) -> int:
        return x

    registry.register(danger)
    result = await registry.execute(
        'danger', 'call-1', {'x': 1}
    )
    assert result.success is False
    assert 'Permission denied' in (result.output or '')


@pytest.mark.asyncio
async def test_registry_allows_low_risk_tool() -> None:
    config = PermissionConfig(permission_level='medium')
    registry = ToolRegistry(permission_config=config)

    @tool(description='Safe', risk_level='low')
    def safe(x: int) -> int:
        return x

    registry.register(safe)
    result = await registry.execute(
        'safe', 'call-1', {'x': 42}
    )
    assert result.success is True
    assert result.output == '42'


@pytest.mark.asyncio
async def test_registry_no_config_allows_all() -> None:
    registry = ToolRegistry()

    @tool(description='Dangerous', risk_level='high')
    def danger(x: int) -> int:
        return x

    registry.register(danger)
    result = await registry.execute(
        'danger', 'call-1', {'x': 1}
    )
    assert result.success is True
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_permission.py::test_registry_blocks_high_risk_tool -v`
Expected: FAIL — `ToolRegistry` does not accept `permission_config`

**Step 3: Write minimal implementation**

In `packages/sonya-core/src/sonya/core/models/tool_registry.py`:

Add import at top:

```python
from sonya.core.schemas.permission import PermissionConfig
```

Modify `__init__`:

```python
    def __init__(
        self,
        permission_config: PermissionConfig | None = None,
    ) -> None:
        self._tools: dict[str, Tool] = {}
        self._permission_config = permission_config
```

Add permission check at the beginning of `execute()`, after the unknown tool check (after line 63), before JSON parsing:

```python
        # Permission check
        if self._permission_config is not None:
            if not self._permission_config.is_allowed(
                tool.name, tool.risk_level
            ):
                return ToolResult(
                    call_id=call_id,
                    name=name,
                    success=False,
                    output=(
                        f"Permission denied: '{name}' "
                        f"requires '{tool.risk_level}' "
                        f"level"
                    ),
                )
```

Add a setter property for runtime config updates:

```python
    @property
    def permission_config(self) -> PermissionConfig | None:
        """Return current permission config."""
        return self._permission_config

    @permission_config.setter
    def permission_config(
        self, config: PermissionConfig | None
    ) -> None:
        """Update permission config at runtime."""
        self._permission_config = config
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_permission.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/models/tool_registry.py packages/sonya-core/tests/test_permission.py
git commit -m "feat(sonya-core): integrate permission check into ToolRegistry"
```

---

### Task 5: Create desktop tools — screen module

**Files:**
- Create: `packages/sonya-core/src/sonya/core/tools/__init__.py`
- Create: `packages/sonya-core/src/sonya/core/tools/desktop/__init__.py`
- Create: `packages/sonya-core/src/sonya/core/tools/desktop/_screen.py`
- Test: `packages/sonya-core/tests/test_desktop_tools.py`

**Step 1: Write the failing test**

```python
# packages/sonya-core/tests/test_desktop_tools.py
"""Tests for desktop tools."""

from __future__ import annotations

import pytest

from sonya.core.tools.desktop._screen import (
    screenshot,
    get_screen_size,
)
from sonya.core.models.tool import Tool


def test_screenshot_is_tool() -> None:
    assert isinstance(screenshot, Tool)
    assert screenshot.name == 'screenshot'
    assert screenshot.risk_level == 'low'


def test_get_screen_size_is_tool() -> None:
    assert isinstance(get_screen_size, Tool)
    assert get_screen_size.name == 'get_screen_size'
    assert get_screen_size.risk_level == 'low'
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_desktop_tools.py -v`
Expected: FAIL — module does not exist

**Step 3: Write minimal implementation**

```python
# packages/sonya-core/src/sonya/core/tools/__init__.py
"""Built-in tool collections."""
```

```python
# packages/sonya-core/src/sonya/core/tools/desktop/__init__.py
"""Desktop automation tools."""

from sonya.core.tools.desktop._screen import (
    screenshot,
    get_screen_size,
)
from sonya.core.tools.desktop._mouse import (
    mouse_click,
    mouse_move,
    mouse_drag,
)
from sonya.core.tools.desktop._keyboard import (
    keyboard_type,
    keyboard_hotkey,
)
from sonya.core.tools.desktop._file import (
    file_read,
    file_write,
    file_delete,
    list_files,
)
from sonya.core.tools.desktop._app import app_launch
from sonya.core.tools.desktop._shell import shell_execute

ALL_DESKTOP_TOOLS = [
    screenshot,
    get_screen_size,
    mouse_click,
    mouse_move,
    mouse_drag,
    keyboard_type,
    keyboard_hotkey,
    file_read,
    file_write,
    file_delete,
    list_files,
    app_launch,
    shell_execute,
]

__all__ = [
    'screenshot',
    'get_screen_size',
    'mouse_click',
    'mouse_move',
    'mouse_drag',
    'keyboard_type',
    'keyboard_hotkey',
    'file_read',
    'file_write',
    'file_delete',
    'list_files',
    'app_launch',
    'shell_execute',
    'ALL_DESKTOP_TOOLS',
]
```

```python
# packages/sonya-core/src/sonya/core/tools/desktop/_screen.py
"""Screen capture and info tools."""

from __future__ import annotations

import base64
import io

from sonya.core.utils.decorator import tool


@tool(description='Capture a screenshot and return as base64 PNG', risk_level='low')
def screenshot() -> str:
    """Capture the entire screen."""
    import pyautogui
    img = pyautogui.screenshot()
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(
        buffer.getvalue()
    ).decode('utf-8')


@tool(description='Get screen resolution as width x height', risk_level='low')
def get_screen_size() -> str:
    """Return screen dimensions."""
    import pyautogui
    w, h = pyautogui.size()
    return f'{w}x{h}'
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_desktop_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/tools/ packages/sonya-core/tests/test_desktop_tools.py
git commit -m "feat(sonya-core): add screen desktop tools (screenshot, get_screen_size)"
```

---

### Task 6: Create desktop tools — mouse module

**Files:**
- Create: `packages/sonya-core/src/sonya/core/tools/desktop/_mouse.py`
- Test: `packages/sonya-core/tests/test_desktop_tools.py` (append)

**Step 1: Write the failing test**

Append to `packages/sonya-core/tests/test_desktop_tools.py`:

```python
from sonya.core.tools.desktop._mouse import (
    mouse_click,
    mouse_move,
    mouse_drag,
)


def test_mouse_click_is_tool() -> None:
    assert isinstance(mouse_click, Tool)
    assert mouse_click.risk_level == 'medium'


def test_mouse_move_is_tool() -> None:
    assert isinstance(mouse_move, Tool)
    assert mouse_move.risk_level == 'medium'


def test_mouse_drag_is_tool() -> None:
    assert isinstance(mouse_drag, Tool)
    assert mouse_drag.risk_level == 'medium'
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_desktop_tools.py::test_mouse_click_is_tool -v`
Expected: FAIL — module does not exist

**Step 3: Write minimal implementation**

```python
# packages/sonya-core/src/sonya/core/tools/desktop/_mouse.py
"""Mouse control tools."""

from __future__ import annotations

from sonya.core.utils.decorator import tool


@tool(
    description='Click at screen coordinates (x, y) with optional button',
    risk_level='medium',
)
def mouse_click(
    x: int, y: int, button: str = 'left'
) -> str:
    """Click at the given coordinates."""
    import pyautogui
    pyautogui.click(x=x, y=y, button=button)
    return f'Clicked ({x}, {y}) with {button}'


@tool(
    description='Move mouse cursor to coordinates (x, y)',
    risk_level='medium',
)
def mouse_move(x: int, y: int) -> str:
    """Move the mouse cursor."""
    import pyautogui
    pyautogui.moveTo(x=x, y=y)
    return f'Moved to ({x}, {y})'


@tool(
    description='Drag from (start_x, start_y) to (end_x, end_y)',
    risk_level='medium',
)
def mouse_drag(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
) -> str:
    """Drag the mouse between two points."""
    import pyautogui
    pyautogui.moveTo(x=start_x, y=start_y)
    pyautogui.drag(
        xOffset=end_x - start_x,
        yOffset=end_y - start_y,
    )
    return (
        f'Dragged ({start_x}, {start_y}) '
        f'to ({end_x}, {end_y})'
    )
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_desktop_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/tools/desktop/_mouse.py packages/sonya-core/tests/test_desktop_tools.py
git commit -m "feat(sonya-core): add mouse desktop tools"
```

---

### Task 7: Create desktop tools — keyboard module

**Files:**
- Create: `packages/sonya-core/src/sonya/core/tools/desktop/_keyboard.py`
- Test: `packages/sonya-core/tests/test_desktop_tools.py` (append)

**Step 1: Write the failing test**

Append:

```python
from sonya.core.tools.desktop._keyboard import (
    keyboard_type,
    keyboard_hotkey,
)


def test_keyboard_type_is_tool() -> None:
    assert isinstance(keyboard_type, Tool)
    assert keyboard_type.risk_level == 'medium'


def test_keyboard_hotkey_is_tool() -> None:
    assert isinstance(keyboard_hotkey, Tool)
    assert keyboard_hotkey.risk_level == 'medium'
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_desktop_tools.py::test_keyboard_type_is_tool -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# packages/sonya-core/src/sonya/core/tools/desktop/_keyboard.py
"""Keyboard control tools."""

from __future__ import annotations

from sonya.core.utils.decorator import tool


@tool(
    description='Type text using the keyboard',
    risk_level='medium',
)
def keyboard_type(text: str) -> str:
    """Type the given text."""
    import pyautogui
    pyautogui.typewrite(text, interval=0.02)
    return f'Typed: {text}'


@tool(
    description='Press a keyboard hotkey combination (e.g. "ctrl", "c")',
    risk_level='medium',
)
def keyboard_hotkey(keys: str) -> str:
    """Press a hotkey combination.

    Args:
        keys: Comma-separated key names (e.g. 'ctrl,c').
    """
    import pyautogui
    key_list = [k.strip() for k in keys.split(',')]
    pyautogui.hotkey(*key_list)
    return f'Pressed: {"+".join(key_list)}'
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_desktop_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/tools/desktop/_keyboard.py packages/sonya-core/tests/test_desktop_tools.py
git commit -m "feat(sonya-core): add keyboard desktop tools"
```

---

### Task 8: Create desktop tools — file module

**Files:**
- Create: `packages/sonya-core/src/sonya/core/tools/desktop/_file.py`
- Test: `packages/sonya-core/tests/test_desktop_tools.py` (append)

**Step 1: Write the failing test**

Append:

```python
from sonya.core.tools.desktop._file import (
    file_read,
    file_write,
    file_delete,
    list_files,
)


def test_file_read_is_tool() -> None:
    assert isinstance(file_read, Tool)
    assert file_read.risk_level == 'low'


def test_file_write_is_tool() -> None:
    assert isinstance(file_write, Tool)
    assert file_write.risk_level == 'medium'


def test_file_delete_is_tool() -> None:
    assert isinstance(file_delete, Tool)
    assert file_delete.risk_level == 'high'


def test_list_files_is_tool() -> None:
    assert isinstance(list_files, Tool)
    assert list_files.risk_level == 'low'


@pytest.mark.asyncio
async def test_file_read_write_roundtrip(
    tmp_path,
) -> None:
    path = str(tmp_path / 'test.txt')
    await file_write.fn(
        path=path, content='hello'
    )
    result = await file_read.fn(path=path)
    assert result == 'hello'


@pytest.mark.asyncio
async def test_file_delete_removes_file(
    tmp_path,
) -> None:
    path = str(tmp_path / 'delete_me.txt')
    await file_write.fn(
        path=path, content='bye'
    )
    result = await file_delete.fn(path=path)
    assert 'Deleted' in result
    import os
    assert not os.path.exists(path)


@pytest.mark.asyncio
async def test_list_files_returns_entries(
    tmp_path,
) -> None:
    (tmp_path / 'a.txt').write_text('a')
    (tmp_path / 'b.txt').write_text('b')
    result = await list_files.fn(
        path=str(tmp_path)
    )
    assert 'a.txt' in result
    assert 'b.txt' in result
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_desktop_tools.py::test_file_read_is_tool -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# packages/sonya-core/src/sonya/core/tools/desktop/_file.py
"""File system tools."""

from __future__ import annotations

import os

from sonya.core.utils.decorator import tool


@tool(
    description='Read the contents of a file at the given path',
    risk_level='low',
)
def file_read(path: str) -> str:
    """Read a file and return its contents."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


@tool(
    description='Write content to a file at the given path',
    risk_level='medium',
)
def file_write(path: str, content: str) -> str:
    """Write content to a file."""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return f'Written to {path}'


@tool(
    description='Delete a file at the given path',
    risk_level='high',
)
def file_delete(path: str) -> str:
    """Delete a file."""
    os.remove(path)
    return f'Deleted {path}'


@tool(
    description='List files and directories at the given path',
    risk_level='low',
)
def list_files(path: str) -> str:
    """List directory contents."""
    entries = os.listdir(path)
    return '\n'.join(sorted(entries))
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_desktop_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/tools/desktop/_file.py packages/sonya-core/tests/test_desktop_tools.py
git commit -m "feat(sonya-core): add file desktop tools"
```

---

### Task 9: Create desktop tools — app and shell modules

**Files:**
- Create: `packages/sonya-core/src/sonya/core/tools/desktop/_app.py`
- Create: `packages/sonya-core/src/sonya/core/tools/desktop/_shell.py`
- Test: `packages/sonya-core/tests/test_desktop_tools.py` (append)

**Step 1: Write the failing test**

Append:

```python
from sonya.core.tools.desktop._app import app_launch
from sonya.core.tools.desktop._shell import (
    shell_execute,
)


def test_app_launch_is_tool() -> None:
    assert isinstance(app_launch, Tool)
    assert app_launch.risk_level == 'medium'


def test_shell_execute_is_tool() -> None:
    assert isinstance(shell_execute, Tool)
    assert shell_execute.risk_level == 'high'


@pytest.mark.asyncio
async def test_shell_execute_runs_command() -> None:
    result = await shell_execute.fn(command='echo hi')
    assert 'hi' in result
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_desktop_tools.py::test_app_launch_is_tool -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# packages/sonya-core/src/sonya/core/tools/desktop/_app.py
"""Application launch tools."""

from __future__ import annotations

import subprocess
import sys

from sonya.core.utils.decorator import tool


@tool(
    description='Launch an application by name or path',
    risk_level='medium',
)
def app_launch(app_name: str) -> str:
    """Launch a desktop application."""
    if sys.platform == 'darwin':
        subprocess.Popen(
            ['open', '-a', app_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    elif sys.platform == 'win32':
        subprocess.Popen(
            ['start', app_name],
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(
            [app_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return f'Launched {app_name}'
```

```python
# packages/sonya-core/src/sonya/core/tools/desktop/_shell.py
"""Shell command execution tool."""

from __future__ import annotations

import subprocess

from sonya.core.utils.decorator import tool


@tool(
    description='Execute a shell command and return output',
    risk_level='high',
)
def shell_execute(command: str) -> str:
    """Execute a shell command."""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = result.stdout
    if result.returncode != 0:
        output += f'\nSTDERR: {result.stderr}'
        output += (
            f'\nReturn code: {result.returncode}'
        )
    return output.strip()
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_desktop_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/tools/desktop/_app.py packages/sonya-core/src/sonya/core/tools/desktop/_shell.py packages/sonya-core/tests/test_desktop_tools.py
git commit -m "feat(sonya-core): add app_launch and shell_execute desktop tools"
```

---

### Task 10: Export permission and desktop tools from sonya-core

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/schemas/__init__.py`
- Modify: `packages/sonya-core/src/sonya/core/__init__.py`
- Modify: `packages/sonya-core/pyproject.toml`
- Test: `packages/sonya-core/tests/test_imports.py` (append)

**Step 1: Write the failing test**

Append to `packages/sonya-core/tests/test_imports.py`:

```python
def test_permission_config_importable() -> None:
    from sonya.core import PermissionConfig
    assert PermissionConfig is not None


def test_desktop_tools_importable() -> None:
    from sonya.core.tools.desktop import (
        ALL_DESKTOP_TOOLS,
    )
    assert len(ALL_DESKTOP_TOOLS) == 13
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_imports.py::test_permission_config_importable -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add to `packages/sonya-core/src/sonya/core/schemas/__init__.py`:

```python
from sonya.core.schemas.permission import PermissionConfig
```

And add `'PermissionConfig'` to the `__all__` list.

Add to `packages/sonya-core/src/sonya/core/__init__.py`:

```python
from sonya.core.schemas.permission import PermissionConfig
```

And add `'PermissionConfig'` to the `__all__` list.

Add `pyautogui` and `Pillow` as optional dependency in `packages/sonya-core/pyproject.toml`:

```toml
[project.optional-dependencies]
# ... existing ...
desktop = ["pyautogui>=0.9", "Pillow>=10.0"]
all = ["anthropic>=0.40", "openai>=1.50", "google-genai>=1.0", "pyautogui>=0.9", "Pillow>=10.0"]
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_imports.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/schemas/__init__.py packages/sonya-core/src/sonya/core/__init__.py packages/sonya-core/pyproject.toml
git commit -m "feat(sonya-core): export PermissionConfig and add desktop optional deps"
```

---

### Task 11: Add permission section to TUI SettingsPanel

**Files:**
- Modify: `packages/sonya-cli/src/sonya/cli/utils/settings_panel.py`
- Modify: `packages/sonya-cli/src/sonya/cli/utils/chat_screen.py`

**Step 1: Write the failing test**

No unit test for TUI widgets — verify manually via `sonya` command.

**Step 2: Modify SettingsPanel**

Replace `packages/sonya-cli/src/sonya/cli/utils/settings_panel.py` with:

```python
"""SettingsPanel widget for Sonya CLI TUI."""

import os

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import (
    Input, Select, TextArea, Label, Button, Rule
)

from sonya.core.schemas.permission import PermissionConfig

_CONFIG_PATH = os.path.join(
    '.sonya', 'permissions.json'
)


class SettingsPanel(Vertical):
    """The sidebar for agent settings."""

    CSS = """
    SettingsPanel {
        layout: vertical;
        padding: 1;
    }

    #setting-label {
        margin-top: 1;
        text-style: bold;
    }

    #model-select {
        margin-bottom: 1;
    }

    #system-prompt {
        height: 10;
        margin-bottom: 1;
    }

    #reset-btn {
        margin-top: 1;
        width: 100%;
    }

    #perm-label {
        margin-top: 1;
        text-style: bold;
    }

    #perm-select {
        margin-bottom: 1;
    }

    #perm-info {
        margin-bottom: 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._permission_config = PermissionConfig.load(
            _CONFIG_PATH
        )

    def compose(self) -> ComposeResult:
        yield Label(
            'Instant Agent Settings',
            classes='setting-label',
        )

        yield Label('Model:', id='label-model')
        yield Select(
            (
                (
                    'Claude 4.6 Sonnet',
                    'claude-sonnet-4-6',
                ),
                (
                    'Claude 4.5 Haiku',
                    'claude-haiku-4-5-20251001',
                ),
                ('GPT-4o', 'gpt-4o'),
                (
                    'GPT-4.1',
                    'gpt-4.1',
                ),
                (
                    'GPT-4.1 mini',
                    'gpt-4.1-mini',
                ),
                (
                    'Gemini 3 Flash Preview',
                    'gemini-3-flash-preview',
                ),
                (
                    'Gemini 3.1 Pro Preview',
                    'gemini-3.1-pro-preview',
                ),
            ),
            id='model-select',
            allow_blank=False,
            value='claude-sonnet-4-6',
        )

        yield Label(
            'System Prompt:', id='label-prompt'
        )
        yield TextArea(
            'You are a helpful assistant.',
            id='system-prompt',
        )

        yield Rule()

        yield Label(
            'Permissions', id='perm-label'
        )
        yield Label(
            'Level:', id='label-perm-level'
        )
        yield Select(
            (
                ('Low (read-only)', 'low'),
                ('Medium (default)', 'medium'),
                ('High (full access)', 'high'),
            ),
            id='perm-select',
            allow_blank=False,
            value=self._permission_config.permission_level,
        )

        denied = len(
            self._permission_config.denied_tools
        )
        allowed = len(
            self._permission_config.allowed_tools
        )
        yield Label(
            f'Denied: {denied}  Allowed: {allowed}',
            id='perm-info',
        )

        yield Button(
            'Reset Session', id='reset-btn'
        )

    def on_select_changed(
        self, event: Select.Changed
    ) -> None:
        """Handle permission level change."""
        if event.select.id == 'perm-select':
            self._permission_config = PermissionConfig(
                permission_level=str(event.value),
                denied_tools=(
                    self._permission_config.denied_tools
                ),
                allowed_tools=(
                    self._permission_config.allowed_tools
                ),
            )
            self._permission_config.save(_CONFIG_PATH)

    @property
    def permission_config(self) -> PermissionConfig:
        """Return current permission config."""
        return self._permission_config

    def focus_system_prompt(self) -> None:
        """Focus the system prompt area."""
        prompt = self.query_one(
            '#system-prompt', TextArea
        )
        prompt.focus()
```

**Step 3: Verify manually**

Run: `source .venv/bin/activate && sonya`
Expected: SettingsPanel shows "Permissions" section with level dropdown

**Step 4: Commit**

```bash
git add packages/sonya-cli/src/sonya/cli/utils/settings_panel.py
git commit -m "feat(sonya-cli): add permission level selector to TUI SettingsPanel"
```

---

### Task 12: Run all tests and verify

**Step 1: Run full test suite**

```bash
cd packages/sonya-core && python -m pytest tests/ -v
```

Expected: All tests pass

**Step 2: Run TUI manually**

```bash
source .venv/bin/activate && sonya
```

Expected: TUI loads with permission dropdown in settings panel

**Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix(sonya-core): resolve test/integration issues"
```
