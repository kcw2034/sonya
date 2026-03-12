"""Tests for Human-in-the-Loop tool approval in AgentRuntime."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.models.agent import Agent, AgentResult
from sonya.core.client.base import BaseClient
from sonya.core.schemas.types import ClientConfig
from sonya.core.utils.decorator import tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _DummyClient(BaseClient):
    def __init__(self, responses: list[Any]) -> None:
        super().__init__(ClientConfig(model='dummy'))
        self._responses = list(responses)
        self._idx = 0

    async def _provider_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        resp = self._responses[self._idx]
        self._idx += 1
        return resp

    async def _provider_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        yield await self._provider_generate(messages, **kwargs)


def _text(t: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=t)],
        stop_reason='end_turn',
    )


def _tool_call(name: str, call_id: str, args: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        content=[
            SimpleNamespace(
                type='tool_use',
                id=call_id,
                name=name,
                input=args,
            )
        ],
        stop_reason='tool_use',
    )


def _tool_then_text(
    name: str, call_id: str, args: dict[str, Any], text: str
) -> tuple[SimpleNamespace, SimpleNamespace]:
    return _tool_call(name, call_id, args), _text(text)


# Approval callback that always approves
class _ApproveAll:
    def __init__(self) -> None:
        self.called_for: list[str] = []

    async def on_approval_request(
        self,
        agent_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        self.called_for.append(tool_name)
        return True


# Approval callback that always denies
class _DenyAll:
    def __init__(self) -> None:
        self.called_for: list[str] = []

    async def on_approval_request(
        self,
        agent_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        self.called_for.append(tool_name)
        return False


# Callback that denies a specific tool
class _DenyTool:
    def __init__(self, deny_name: str) -> None:
        self._deny = deny_name
        self.called_for: list[str] = []

    async def on_approval_request(
        self,
        agent_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        self.called_for.append(tool_name)
        return tool_name != self._deny


# ---------------------------------------------------------------------------
# Tool fixtures
# ---------------------------------------------------------------------------

@tool(description='Echo input back')
async def _echo(msg: str) -> str:
    return msg


@tool(description='Echo with approval required', requires_approval=True)
async def _echo_approval(msg: str) -> str:
    return msg


@tool(description='Second tool requiring approval', requires_approval=True)
async def _second_approval(x: int) -> int:
    return x * 2


# ---------------------------------------------------------------------------
# Tool.requires_approval field
# ---------------------------------------------------------------------------

def test_tool_requires_approval_default_false() -> None:
    """Tool.requires_approval defaults to False."""
    assert _echo.requires_approval is False


def test_tool_requires_approval_true_when_set() -> None:
    """Tool.requires_approval is True when set via decorator."""
    assert _echo_approval.requires_approval is True


# ---------------------------------------------------------------------------
# No requires_approval — callback never called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_approval_required_callback_not_called() -> None:
    """Tool without requires_approval runs without calling approval callback."""
    tool_resp, final = _tool_then_text(
        '_echo', 'c1', {'msg': 'hello'}, 'done'
    )
    client = _DummyClient([tool_resp, final])
    client.__class__.__name__ = 'AnthropicClient'
    callback = _ApproveAll()
    agent = Agent(
        name='a', client=client,
        tools=[_echo],
        callbacks=[callback],
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert result.text == 'done'
    assert callback.called_for == []  # never asked for approval


# ---------------------------------------------------------------------------
# requires_approval=True + callback approves → tool executes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approval_granted_tool_executes() -> None:
    """Tool with requires_approval=True runs when callback approves."""
    tool_resp, final = _tool_then_text(
        '_echo_approval', 'c1', {'msg': 'hello'}, 'done'
    )
    client = _DummyClient([tool_resp, final])
    client.__class__.__name__ = 'AnthropicClient'
    callback = _ApproveAll()
    agent = Agent(
        name='a', client=client,
        tools=[_echo_approval],
        callbacks=[callback],
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert result.text == 'done'
    assert '_echo_approval' in callback.called_for


# ---------------------------------------------------------------------------
# requires_approval=True + callback denies → tool NOT executed, error in history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approval_denied_tool_not_executed() -> None:
    """Tool with requires_approval=True is NOT run when callback denies."""
    tool_resp, final = _tool_then_text(
        '_echo_approval', 'c1', {'msg': 'hello'},
        'approval was denied'
    )
    client = _DummyClient([tool_resp, final])
    client.__class__.__name__ = 'AnthropicClient'
    callback = _DenyAll()
    agent = Agent(
        name='a', client=client,
        tools=[_echo_approval],
        callbacks=[callback],
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    # LLM got denial result, produced final text
    assert '_echo_approval' in callback.called_for
    # History should contain a tool result message with error
    tool_messages = [
        m for m in result.history
        if m.get('role') == 'user'
        and isinstance(m.get('content'), list)
        and any(
            b.get('type') == 'tool_result'
            for b in m['content']
            if isinstance(b, dict)
        )
    ]
    assert len(tool_messages) >= 1
    # The tool result block should mark the call as an error
    found_error = False
    for m in tool_messages:
        for block in m['content']:
            if (
                isinstance(block, dict)
                and block.get('type') == 'tool_result'
            ):
                # is_error=True signals denial to the LLM
                if block.get('is_error') is True:
                    found_error = True
    assert found_error, 'Expected at least one tool_result with is_error=True'


# ---------------------------------------------------------------------------
# requires_approval=True + no callback → default approve (silent)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approval_required_no_callback_defaults_approve() -> None:
    """Without an approval callback, requires_approval tools run normally."""
    tool_resp, final = _tool_then_text(
        '_echo_approval', 'c1', {'msg': 'hello'}, 'done'
    )
    client = _DummyClient([tool_resp, final])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a', client=client,
        tools=[_echo_approval],
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert result.text == 'done'


# ---------------------------------------------------------------------------
# Mixed tools: only requires_approval ones go through callback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mixed_tools_only_approval_ones_checked() -> None:
    """Only tools with requires_approval=True call the approval callback."""
    # First iteration: call _echo (no approval) + _echo_approval (needs approval)
    # We simulate two separate iterations for simplicity
    tool_resp1 = _tool_call('_echo', 'c1', {'msg': 'hi'})
    tool_resp2 = _tool_call('_echo_approval', 'c2', {'msg': 'world'})
    final = _text('done')
    client = _DummyClient([tool_resp1, tool_resp2, final])
    client.__class__.__name__ = 'AnthropicClient'
    callback = _ApproveAll()
    agent = Agent(
        name='a', client=client,
        tools=[_echo, _echo_approval],
        callbacks=[callback],
        max_iterations=10,
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert result.text == 'done'
    # Only _echo_approval requested approval; _echo did not
    assert '_echo_approval' in callback.called_for
    assert '_echo' not in callback.called_for


# ---------------------------------------------------------------------------
# run_stream: approval works correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_stream_approval_granted() -> None:
    """run_stream: approved tool executes normally."""
    tool_resp, final = _tool_then_text(
        '_echo_approval', 'c1', {'msg': 'hello'}, 'done'
    )
    client = _DummyClient([tool_resp, final])
    client.__class__.__name__ = 'AnthropicClient'
    callback = _ApproveAll()
    agent = Agent(
        name='a', client=client,
        tools=[_echo_approval],
        callbacks=[callback],
    )
    result: AgentResult | None = None
    async for item in AgentRuntime(agent).run_stream(
        [{'role': 'user', 'content': 'hi'}]
    ):
        if isinstance(item, AgentResult):
            result = item
    assert result is not None
    assert result.text == 'done'
    assert '_echo_approval' in callback.called_for


@pytest.mark.asyncio
async def test_run_stream_approval_denied() -> None:
    """run_stream: denied tool result is fed back to LLM."""
    tool_resp, final = _tool_then_text(
        '_echo_approval', 'c1', {'msg': 'hello'},
        'approval was denied'
    )
    client = _DummyClient([tool_resp, final])
    client.__class__.__name__ = 'AnthropicClient'
    callback = _DenyAll()
    agent = Agent(
        name='a', client=client,
        tools=[_echo_approval],
        callbacks=[callback],
    )
    result: AgentResult | None = None
    async for item in AgentRuntime(agent).run_stream(
        [{'role': 'user', 'content': 'hi'}]
    ):
        if isinstance(item, AgentResult):
            result = item
    assert result is not None
    assert '_echo_approval' in callback.called_for


# ---------------------------------------------------------------------------
# ToolApprovalDeniedError is importable
# ---------------------------------------------------------------------------

def test_tool_approval_denied_error_importable() -> None:
    """ToolApprovalDeniedError can be imported from sonya.core."""
    from sonya.core import ToolApprovalDeniedError as E
    err = E('my_agent', 'my_tool')
    assert 'my_tool' in str(err)
    assert err.tool_name == 'my_tool'
    assert err.agent_name == 'my_agent'
