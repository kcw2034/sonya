"""sonya.core — lightweight LLM client framework with multi-agent support."""

from sonya.core.types import (
    AgentCallback,
    CacheConfig,
    CachedContent,
    CacheUsage,
    ClientConfig,
    Interceptor,
)
from sonya.core.context.cache import (
    AnthropicCache,
    BaseCache,
    GeminiCache,
    OpenAICache,
)
from sonya.core.client.base import BaseClient
from sonya.core.client.anthropic import AnthropicClient
from sonya.core.client.google import GeminiClient
from sonya.core.client.openai import OpenAIClient
from sonya.core.errors import AgentError, ToolError
from sonya.core.tool import Tool, ToolContext, ToolRegistry, ToolResult, tool
from sonya.core.agent import Agent, AgentResult, AgentRuntime
from sonya.core.orchestration import (
    Runner,
    RunnerCallback,
    RunnerConfig,
    SupervisorConfig,
    SupervisorRuntime,
)
from sonya.core.context import (
    ContextRouter,
    MemoryPipeline,
    NormalizedMessage,
)
from sonya.core.logging import DebugCallback, LoggingInterceptor

__version__ = "0.0.1"

__all__ = [
    # Client
    "BaseClient",
    "AnthropicClient",
    "GeminiClient",
    "OpenAIClient",
    "AgentCallback",
    "ClientConfig",
    "Interceptor",
    # Errors
    "AgentError",
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
    "MemoryPipeline",
    "NormalizedMessage",
    # Logging
    "DebugCallback",
    "LoggingInterceptor",
    # Meta
    "__version__",
]
