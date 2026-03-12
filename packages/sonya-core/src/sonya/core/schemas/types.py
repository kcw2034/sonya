"""Interceptor protocol and shared type definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Interceptor(Protocol):
    """Protocol for intercepting API calls before and after execution.

    Implement only the methods you need: before_request and/or after_response.
    """

    async def before_request(
        self,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Transform messages and kwargs before the request is sent."""
        ...

    async def after_response(self, response: Any) -> Any:
        """Transform or log the response after it is received."""
        ...


@runtime_checkable
class AgentCallback(Protocol):
    """Protocol for agent-level lifecycle callbacks.

    Implement only the methods you need. The runtime checks
    with ``hasattr`` before calling each hook.
    """

    async def on_iteration_start(
        self,
        agent_name: str,
        iteration: int,
    ) -> None:
        """Called at the start of each LLM loop iteration."""
        ...

    async def on_iteration_end(
        self,
        agent_name: str,
        iteration: int,
    ) -> None:
        """Called at the end of each LLM loop iteration."""
        ...

    async def on_tool_start(
        self,
        agent_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        """Called before a tool is executed."""
        ...

    async def on_tool_end(
        self,
        agent_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        output: str | None,
        error: str | None,
        success: bool,
    ) -> None:
        """Called after a tool finishes execution."""
        ...

    async def on_handoff(
        self,
        from_agent: str,
        to_agent: str,
    ) -> None:
        """Called when the agent signals a handoff."""
        ...

    async def on_approval_request(
        self,
        agent_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        """Called before executing a tool that requires approval.

        Return True to approve execution, False to deny it.
        When denied, the runtime feeds an error result back to
        the LLM instead of executing the tool.

        Args:
            agent_name: Name of the agent requesting approval.
            tool_name: Name of the tool to be executed.
            arguments: Arguments the LLM passed to the tool.

        Returns:
            True to allow execution, False to deny.
        """
        ...

    async def on_tool_register(
        self,
        agent_name: str,
        tool_name: str,
    ) -> None:
        """Called when a tool is dynamically registered at runtime."""
        ...

    async def on_tool_unregister(
        self,
        agent_name: str,
        tool_name: str,
    ) -> None:
        """Called when a tool is dynamically unregistered at runtime."""
        ...

    async def on_llm_start(
        self,
        agent_name: str,
        iteration: int,
        message_count: int,
    ) -> None:
        """Called immediately before each LLM generate() call.

        Args:
            agent_name: Name of the executing agent.
            iteration: Zero-based loop iteration index.
            message_count: Number of messages sent to the LLM.
        """
        ...

    async def on_llm_end(
        self,
        agent_name: str,
        iteration: int,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
    ) -> None:
        """Called immediately after each LLM generate() call.

        Args:
            agent_name: Name of the executing agent.
            iteration: Zero-based loop iteration index.
            input_tokens: Input tokens consumed in this call.
            output_tokens: Output tokens produced in this call.
            latency_ms: Round-trip time for the LLM call in ms.
        """
        ...


@dataclass(frozen=True, slots=True)
class GuardrailConfig:
    """Guardrail limits for an agent's tool execution loop.

    All fields default to ``None``, meaning no limit is enforced.
    Set a field to a positive value to activate that guardrail.

    Args:
        max_tool_calls: Maximum total tool calls across all iterations.
            Exceeding this raises :class:`GuardrailError`.
        max_tool_time: Maximum cumulative seconds spent executing tools.
            Checked after each :meth:`ToolRegistry.execute_many` batch.
            Exceeding this raises :class:`GuardrailError`.
    """

    max_tool_calls: int | None = None
    max_tool_time: float | None = None
    max_concurrent_tools: int | None = None


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Retry and exponential-backoff settings for provider calls.

    Args:
        max_retries: Maximum number of retries after the initial attempt.
            Set to 0 to disable retries entirely.
        base_delay: Seconds to wait before the first retry.
        max_delay: Upper bound on the computed backoff delay (seconds).
        backoff_factor: Multiplier applied after each failed attempt.
            Delay for attempt n = min(base_delay * backoff_factor**n,
            max_delay).
        retryable_exceptions: Tuple of exception types that trigger a
            retry.  Defaults to ``(OSError,)`` which covers network-level
            errors (``ConnectionError``, ``TimeoutError``, etc.).
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    retryable_exceptions: tuple[type[Exception], ...] = (OSError,)


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """Common configuration for all provider clients."""

    model: str
    api_key: str | None = None
    interceptors: list[Interceptor] = field(default_factory=list)
    retry: RetryConfig = field(default_factory=RetryConfig)


@dataclass(frozen=True, slots=True)
class UsageSummary:
    """Aggregated usage metrics from a single agent run.

    Collected automatically by AgentRuntime and stored in
    ``AgentResult.metadata['usage']`` after every run.

    Args:
        total_input_tokens: Sum of input tokens across all LLM calls.
        total_output_tokens: Sum of output tokens across all LLM calls.
        llm_calls: Number of LLM generate() invocations.
        iterations: Number of agent loop iterations executed.
        total_tool_calls: Total tool executions across all iterations.
        total_tool_time_ms: Cumulative tool execution time (ms).
        total_latency_ms: Cumulative LLM round-trip latency (ms).
    """

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    llm_calls: int = 0
    iterations: int = 0
    total_tool_calls: int = 0
    total_tool_time_ms: float = 0.0
    total_latency_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class CacheConfig:
    """Input configuration for cache creation.

    Args:
        model: Target LLM model identifier.
        display_name: Human-readable cache label.
        system_instruction: System prompt to cache.
        contents: Message dicts to cache.
        tools: Tool definitions to cache.
        ttl: Time-to-live string (e.g. '3600s', '5m').
    """

    model: str
    display_name: str | None = None
    system_instruction: str | None = None
    contents: list[dict[str, Any]] = field(
        default_factory=list
    )
    tools: list[dict[str, Any]] = field(
        default_factory=list
    )
    ttl: str | None = None


@dataclass(frozen=True, slots=True)
class CachedContent:
    """Unified cache resource returned by create/get.

    Args:
        name: Provider-specific cache identifier.
        model: Model this cache is bound to.
        display_name: Human-readable label.
        create_time: ISO 8601 creation timestamp.
        expire_time: ISO 8601 expiration timestamp.
        token_count: Total cached token count.
        provider: Provider name (anthropic/gemini/openai).
    """

    name: str
    model: str
    display_name: str | None = None
    create_time: str | None = None
    expire_time: str | None = None
    token_count: int | None = None
    provider: str = ''


@dataclass(frozen=True, slots=True)
class CacheUsage:
    """Cache token usage extracted from a response.

    Args:
        cached_tokens: Tokens served from cache.
        cache_creation_tokens: Tokens written to cache.
        total_input_tokens: Total input tokens consumed.
    """

    cached_tokens: int = 0
    cache_creation_tokens: int = 0
    total_input_tokens: int = 0
