"""sonya.core — lightweight LLM client framework with multi-agent support."""

from sonya.core.schemas.types import (
    AgentCallback,
    CacheConfig,
    CachedContent,
    CacheUsage,
    ClientConfig,
    GuardrailConfig,
    Interceptor,
    RetryConfig,
    UsageSummary,
)
from sonya.core.cache.base import BaseCache
from sonya.core.cache.provider.anthropic import AnthropicCache
from sonya.core.cache.provider.gemini import GeminiCache
from sonya.core.cache.provider.openai import OpenAICache
from sonya.core.client.base import BaseClient
from sonya.core.client.provider.anthropic import AnthropicClient
from sonya.core.client.provider.google import GeminiClient
from sonya.core.client.provider.openai import OpenAIClient
from sonya.core.exceptions.errors import (
    AgentError,
    GuardrailError,
    MaxRetriesExceededError,
    ToolApprovalDeniedError,
    ToolError,
)
from sonya.core.models.tool import Tool, ToolResult
from sonya.core.utils.tool_context import ToolContext
from sonya.core.models.tool_registry import ToolRegistry
from sonya.core.utils.decorator import tool
from sonya.core.models.agent import Agent, AgentResult
from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.models.prompt import Example, Prompt
from sonya.core.models.runner import (
    Runner,
    RunnerCallback,
    RunnerConfig,
)
from sonya.core.models.supervisor import (
    SupervisorConfig,
    SupervisorRuntime,
)
from sonya.core.utils.router import ContextRouter
from sonya.core.schemas.memory import (
    MemoryEntry,
    MemoryPipeline,
    MemoryType,
    NormalizedMessage,
)
from sonya.core.utils.callback import DebugCallback
from sonya.core.parsers.adapter import register_adapter, get_adapter
from sonya.core.client.provider.interceptor import (
    LoggingInterceptor,
)
from sonya.core.models.session import Session, SessionStore
from sonya.core.stores.in_memory import InMemorySessionStore

__version__ = "0.0.1"

__all__ = [
    # Client
    "BaseClient",
    "AnthropicClient",
    "GeminiClient",
    "OpenAIClient",
    "AgentCallback",
    "ClientConfig",
    "GuardrailConfig",
    "Interceptor",
    "RetryConfig",
    "UsageSummary",
    # Errors
    "AgentError",
    "GuardrailError",
    "MaxRetriesExceededError",
    "ToolApprovalDeniedError",
    "ToolError",
    # Tool
    "Tool",
    "ToolResult",
    "ToolContext",
    "ToolRegistry",
    "tool",
    # Agent
    "Agent",
    "AgentResult",
    "AgentRuntime",
    # Prompt
    "Example",
    "Prompt",
    # Orchestration
    "Runner",
    "RunnerCallback",
    "RunnerConfig",
    "SupervisorConfig",
    "SupervisorRuntime",
    # Cache
    "BaseCache",
    "AnthropicCache",
    "GeminiCache",
    "OpenAICache",
    "CacheConfig",
    "CachedContent",
    "CacheUsage",
    # Context Routing
    "ContextRouter",
    "MemoryEntry",
    "MemoryPipeline",
    "MemoryType",
    "NormalizedMessage",
    # Adapter
    "register_adapter",
    "get_adapter",
    # Session
    "Session",
    "SessionStore",
    "InMemorySessionStore",
    # Logging
    "DebugCallback",
    "LoggingInterceptor",
    # Meta
    "__version__",
]
