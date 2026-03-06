"""sonya.core — lightweight LLM client framework with multi-agent support."""

from sonya.core.schemas.types import (
    AgentCallback,
    CacheConfig,
    CachedContent,
    CacheUsage,
    ClientConfig,
    Interceptor,
)
from sonya.core.client.cache_base import BaseCache
from sonya.core.client.cache_anthropic import AnthropicCache
from sonya.core.client.cache_gemini import GeminiCache
from sonya.core.client.cache_openai import OpenAICache
from sonya.core.client.base import BaseClient
from sonya.core.client.anthropic import AnthropicClient
from sonya.core.client.google import GeminiClient
from sonya.core.client.openai import OpenAIClient
from sonya.core.exceptions.errors import AgentError, ToolError
from sonya.core.models.tool import Tool, ToolResult
from sonya.core.utils.tool_context import ToolContext
from sonya.core.models.tool_registry import ToolRegistry
from sonya.core.utils.decorator import tool
from sonya.core.models.agent import Agent, AgentResult
from sonya.core.models.agent_runtime import AgentRuntime
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
    MemoryPipeline,
    NormalizedMessage,
)
from sonya.core.utils.callback import DebugCallback
from sonya.core.client.interceptor import LoggingInterceptor

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
