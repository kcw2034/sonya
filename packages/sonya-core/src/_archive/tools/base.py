"""
Tool 베이스 레이어
- 모든 Tool은 BaseTool을 상속
- Pydantic으로 Input/Output 스키마 자동 생성
- LLM에 넘길 JSON Schema도 여기서 추출
- sync execute() 자동 래핑 (asyncio.to_thread)
- setup()/teardown() 리소스 라이프사이클
- ToolContext 주입 (선택적)
"""

import asyncio
import functools
import inspect
import logging
from abc import ABC, abstractmethod
from typing import Generic, Type, TypeVar, get_type_hints

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

from .context import ToolContext
from .models import ToolResult
from .error import ToolError

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseTool(ABC, Generic[InputT, OutputT]):
    """
    모든 Tool의 베이스 클래스

    사용법:
        class MyTool(BaseTool[MyInput, MyOutput]):
            name = "my_tool"
            description = "무언가를 한다"

            async def execute(self, input: MyInput) -> MyOutput:
                ...

    sync execute도 가능 (자동으로 asyncio.to_thread 래핑):
        class CpuTool(BaseTool[MyInput, MyOutput]):
            name = "cpu_tool"
            description = "CPU 바운드 작업"

            def execute(self, input: MyInput) -> MyOutput:
                ...

    리소스 라이프사이클:
        async def setup(self) -> None:    # 초기화 (모델 로드 등)
        async def teardown(self) -> None: # 정리 (메모리 해제 등)

    ToolContext 주입:
        def execute(self, input: MyInput, *, ctx: ToolContext) -> MyOutput:
            ctx.set("key", value, source=self.name)
    """
    name: str
    description: str

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # name, description 필수 검증
        if not inspect.isabstract(cls):
            if not hasattr(cls, "name") or not cls.name:
                raise TypeError(f"{cls.__name__} must define 'name'")
            if not hasattr(cls, "description") or not cls.description:
                raise TypeError(f"{cls.__name__} must define 'description'")

        # sync execute 자동 래핑: def execute()이면 asyncio.to_thread로 감싸기
        if "execute" in cls.__dict__:
            original = cls.__dict__["execute"]
            if callable(original) and not asyncio.iscoroutinefunction(original):
                @functools.wraps(original)
                async def _async_wrapper(self, *args, **kwargs):
                    return await asyncio.to_thread(original, self, *args, **kwargs)

                # 원본 타입 힌트 복사 → get_input_type() 동작 보장
                if hasattr(original, "__annotations__"):
                    _async_wrapper.__annotations__ = original.__annotations__.copy()
                _async_wrapper.__wrapped__ = original

                cls.execute = _async_wrapper

    @abstractmethod
    async def execute(self, input: InputT) -> OutputT:
        """Tool의 실제 실행 로직"""
        ...

    async def setup(self) -> None:
        """리소스 초기화. 선택적 오버라이드."""
        pass

    async def teardown(self) -> None:
        """리소스 정리. 선택적 오버라이드."""
        pass

    def get_input_type(self) -> Type[InputT]:
        """Generic 타입에서 InputT 추출"""
        hints = get_type_hints(self.execute)
        return hints.get("input")

    def get_output_type(self) -> Type[OutputT]:
        """Generic 타입에서 OutputT 추출"""
        hints = get_type_hints(self.execute)
        return hints.get("return")

    def to_llm_schema(self, provider: str = "anthropic") -> dict:
        """
        LLM Provider별 Tool 스키마 포맷으로 변환
        Pydantic 모델에서 JSON Schema 자동 추출

        Args:
            provider: 'anthropic' 또는 'openai'

        Anthropic: {"name", "description", "input_schema"}
        OpenAI:    {"type": "function", "function": {"name", "description", "parameters"}}
        """
        input_type = self.get_input_type()
        if input_type is None:
            raise TypeError(f"Tool '{self.name}' execute() must have type hint for 'input'")

        schema = input_type.model_json_schema()
        # Pydantic이 붙이는 title 제거 (LLM에 불필요)
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)

        if provider == "openai":
            return {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": schema,
                },
            }

        # 기본: Anthropic 포맷
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": schema,
        }

    def _execute_wants_ctx(self) -> bool:
        """execute() 시그니처에 ctx 파라미터가 있는지 판별"""
        try:
            hints = get_type_hints(self.execute)
            return "ctx" in hints
        except Exception:
            # get_type_hints 실패 시 (forward ref 등) inspect로 폴백
            sig = inspect.signature(self.execute)
            return "ctx" in sig.parameters

    async def safe_execute(
        self,
        raw_input: dict,
        tool_use_id: str,
        ctx: ToolContext | None = None,
    ) -> ToolResult:
        """
        검증 + 실행 + 에러 핸들링을 한 번에
        Runtime에서 이걸 호출함

        Args:
            raw_input: LLM이 생성한 raw input dict
            tool_use_id: Anthropic API tool_use 식별자
            ctx: Tool 간 공유 컨텍스트 (None이면 주입하지 않음)
        """
        try:
            input_type = self.get_input_type()
            parsed_input = input_type.model_validate(raw_input)

            logger.debug(f"[{self.name}] 실행 시작: {list(raw_input.keys())}")

            # execute 시그니처에 ctx가 있으면 주입
            if ctx is not None and self._execute_wants_ctx():
                output = await self.execute(parsed_input, ctx=ctx)
            else:
                output = await self.execute(parsed_input)

            # execute가 ToolResult를 직접 반환하는 경우
            if isinstance(output, ToolResult):
                output.tool_use_id = tool_use_id
                logger.debug(f"[{self.name}] 실행 완료 (ToolResult 직접 반환)")
                return output

            # output 스키마 검증
            output_type = self.get_output_type()
            if output_type and isinstance(output, BaseModel):
                try:
                    output_type.model_validate(output.model_dump())
                except ValidationError as ve:
                    logger.error(f"[{self.name}] output validation 실패: {ve}")
                    return ToolResult(
                        tool_name=self.name,
                        tool_use_id=tool_use_id,
                        success=False,
                        error=f"Output validation failed: {ve}",
                    )

            logger.debug(f"[{self.name}] 실행 완료")

            return ToolResult(
                tool_name=self.name,
                tool_use_id=tool_use_id,
                success=True,
                output=output.model_dump() if isinstance(output, BaseModel) else output,
            )
        except ToolError as e:
            logger.warning(f"[{self.name}] ToolError: {e.message}")
            return ToolResult(
                tool_name=self.name,
                tool_use_id=tool_use_id,
                success=False,
                error=str(e.message),
            )
        except Exception as e:
            logger.error(f"[{self.name}] 예상치 못한 에러: {type(e).__name__}: {e}")
            return ToolResult(
                tool_name=self.name,
                tool_use_id=tool_use_id,
                success=False,
                error=f"Unexpected error: {type(e).__name__}: {e}",
            )
