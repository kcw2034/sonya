"""sonya.core — lightweight LLM client framework with multi-agent support."""

from .schemas.types import (
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
from .cache.base import BaseCache
from sonya.core.cache.provider.anthropic import AnthropicCache
from sonya.core.cache.provider.gemini import GeminiCache
from sonya.core.cache.provider.openai import OpenAICache
from .client.base import BaseClient
from sonya.core.client.provider.anthropic import AnthropicClient
from sonya.core.client.provider.google import GeminiClient
from sonya.core.client.provider.openai import OpenAIClient
from .exceptions.errors import (
    AgentError,
    GuardrailError,
    MaxRetriesExceededError,
    ToolApprovalDeniedError,
    ToolError,
)
from .models.tool import Tool, ToolResult
from .utils.tool_context import ToolContext
from .models.tool_registry import ToolRegistry
from .utils.decorator import tool
from .models.agent import Agent, AgentResult
from .models.agent_runtime import AgentRuntime
from .models.prompt import Example, Prompt
from .models.runner import (
    Runner,
    RunnerCallback,
    RunnerConfig,
)
from .models.supervisor import (
    SupervisorConfig,
    SupervisorRuntime,
)
from .utils.router import ContextRouter
from .schemas.memory import (
    MemoryEntry,
    MemoryPipeline,
    MemoryType,
    NormalizedMessage,
)
from .utils.callback import DebugCallback
from .parsers.adapter import register_adapter, get_adapter
from sonya.core.client.provider.interceptor import (
    LoggingInterceptor,
)
from .models.session import Session, SessionStore
from .stores.in_memory import InMemorySessionStore

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
