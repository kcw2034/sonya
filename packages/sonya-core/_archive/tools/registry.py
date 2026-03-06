"""
Tool Registry
- Tool 인스턴스를 이름 기반으로 관리
- YAML 설정에서 동적으로 Tool 로드
- LLM 스키마 일괄 추출
- 라이프사이클 관리 (startup/shutdown)
- async with 패턴 지원
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

from .base import BaseTool
from .context import ToolContext
from .models import ToolResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Tool 인스턴스를 관리하는 레지스트리

    사용법:
        registry = ToolRegistry()
        registry.register(WebSearchTool())
        registry.register(WriteReportTool())

        schemas = registry.schemas()  # LLM에 넘길 스키마 목록
        result = await registry.execute("web_search", {...}, "tool_use_id")

    라이프사이클 관리:
        async with registry:
            # setup() 호출됨
            agent = AgentRuntime(client, registry)
            await agent.run("질문")
        # shutdown() 호출됨
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> ToolRegistry:
        """Tool 인스턴스 등록. 체이닝 가능."""
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' is already registered. Overwriting.")
        self._tools[tool.name] = tool
        logger.debug(f"Tool registered: '{tool.name}'")
        return self

    def unregister(self, name: str) -> None:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        del self._tools[name]

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found. Available: {list(self._tools.keys())}")
        return self._tools[name]

    def schemas(self, provider: str = "anthropic") -> list[dict]:
        """등록된 모든 Tool의 LLM 스키마 반환"""
        return [tool.to_llm_schema(provider=provider) for tool in self._tools.values()]

    async def startup(self) -> None:
        """등록된 모든 Tool의 setup() 호출"""
        for tool in self._tools.values():
            logger.debug(f"Setting up tool: '{tool.name}'")
            await tool.setup()

    async def shutdown(self) -> None:
        """등록된 모든 Tool의 teardown()을 역순으로 호출"""
        for tool in reversed(list(self._tools.values())):
            logger.debug(f"Tearing down tool: '{tool.name}'")
            try:
                await tool.teardown()
            except Exception:
                logger.exception(f"Error during teardown of '{tool.name}'")

    async def __aenter__(self) -> ToolRegistry:
        await self.startup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    async def execute(
        self,
        tool_name: str,
        raw_input: dict,
        tool_use_id: str,
        ctx: ToolContext | None = None,
    ) -> ToolResult:
        """이름으로 Tool 찾아서 실행"""
        tool = self.get(tool_name)
        return await tool.safe_execute(raw_input, tool_use_id, ctx=ctx)

    async def execute_many(
        self,
        tool_calls: list[dict],
        ctx: ToolContext | None = None,
    ) -> list[ToolResult]:
        """
        여러 Tool 병렬 실행
        tool_calls: Anthropic API의 tool_use content block 리스트
        """
        import asyncio

        tasks = [
            self.execute(
                tool_name=call["name"],
                raw_input=call["input"],
                tool_use_id=call["id"],
                ctx=ctx,
            )
            for call in tool_calls
        ]
        return await asyncio.gather(*tasks, return_exceptions=False)

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={list(self._tools.keys())})"


def load_registry_from_config(tool_configs: list[dict]) -> ToolRegistry:
    """
    agent.yaml의 tools 섹션을 읽어서 ToolRegistry 생성

    tool_configs 예시:
        - name: web_search
          module: tools.examples.web_search
          class: WebSearchTool
    """
    registry = ToolRegistry()

    for cfg in tool_configs:
        module_path = cfg.get("module")
        class_name = cfg.get("class")

        if not module_path or not class_name:
            raise ValueError(f"Tool config must have 'module' and 'class': {cfg}")

        try:
            module = importlib.import_module(module_path)
            tool_class = getattr(module, class_name)
            tool_instance = tool_class()
            registry.register(tool_instance)
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Failed to load tool '{class_name}' from '{module_path}': {e}")

    return registry
