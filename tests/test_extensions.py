"""
코어 확장 포인트 테스트
- ToolContext: set/get/expected_type/default/summary
- ToolResult 확장: _raw, llm_summary, from_output
- sync execute 자동 래핑
- 라이프사이클 (setup/teardown)
- ToolContext 주입
- E2E 파이프라인 (mock embed → mock vector_search)

python -m pytest tests/test_extensions.py -v
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, Field

from sonya.core.tools.base import BaseTool
from sonya.core.tools.context import ToolContext
from sonya.core.tools.error import ToolError
from sonya.core.tools.models import ToolResult
from sonya.core.tools.registry import ToolRegistry


# ── ToolContext 테스트 ─────────────────────────────────────────

class TestToolContext:
    def test_set_and_get(self):
        ctx = ToolContext()
        ctx.set("key1", [1, 2, 3], source="test_tool")
        assert ctx.get("key1") == [1, 2, 3]

    def test_get_with_expected_type(self):
        ctx = ToolContext()
        ctx.set("nums", [1, 2, 3])
        result = ctx.get("nums", expected_type=list)
        assert result == [1, 2, 3]

    def test_get_expected_type_mismatch(self):
        ctx = ToolContext()
        ctx.set("nums", [1, 2, 3])
        with pytest.raises(TypeError, match="list.*str"):
            ctx.get("nums", expected_type=str)

    def test_get_missing_key_raises(self):
        ctx = ToolContext()
        with pytest.raises(KeyError, match="존재하지 않는키"):
            ctx.get("존재하지 않는키")

    def test_get_with_default(self):
        ctx = ToolContext()
        result = ctx.get("missing", default=42)
        assert result == 42

    def test_get_default_none(self):
        """default=None도 유효한 기본값"""
        ctx = ToolContext()
        result = ctx.get("missing", default=None)
        assert result is None

    def test_has(self):
        ctx = ToolContext()
        assert ctx.has("key") is False
        ctx.set("key", "value")
        assert ctx.has("key") is True

    def test_keys(self):
        ctx = ToolContext()
        ctx.set("a", 1)
        ctx.set("b", 2)
        assert sorted(ctx.keys()) == ["a", "b"]

    def test_summary(self):
        ctx = ToolContext()
        ctx.set("vector", [0.1, 0.2], source="embed_tool")
        ctx.set("count", 42)
        summary = ctx.summary()
        assert "type=list" in summary["vector"]
        assert "source=embed_tool" in summary["vector"]
        assert "type=int" in summary["count"]

    def test_clear(self):
        ctx = ToolContext()
        ctx.set("a", 1)
        ctx.clear()
        assert ctx.keys() == []
        assert ctx.has("a") is False


# ── ToolResult 확장 테스트 ─────────────────────────────────────

class TestToolResultExtension:
    def test_raw_not_in_llm_format(self):
        """_raw는 to_llm_format()에 포함되지 않음"""
        result = ToolResult.from_output(
            tool_name="test",
            tool_use_id="id-1",
            output={"dimension": 384},
            raw=[0.1, 0.2, 0.3],
        )
        fmt = result.to_llm_format()
        assert "0.1" not in fmt["content"]
        assert "384" in fmt["content"]

    def test_llm_summary_overrides_output(self):
        """llm_summary가 있으면 output 대신 사용"""
        result = ToolResult.from_output(
            tool_name="test",
            tool_use_id="id-2",
            output={"dimension": 384, "data": "huge"},
            llm_summary="384차원 벡터 생성 완료",
        )
        fmt = result.to_llm_format()
        assert fmt["content"] == "384차원 벡터 생성 완료"

    def test_llm_summary_none_falls_back_to_output(self):
        """llm_summary가 None이면 기존 output 직렬화 동작"""
        result = ToolResult(
            tool_name="test",
            tool_use_id="id-3",
            success=True,
            output={"key": "value"},
        )
        fmt = result.to_llm_format()
        assert "value" in fmt["content"]

    def test_from_output_factory(self):
        result = ToolResult.from_output(
            tool_name="embed",
            tool_use_id="tu-1",
            output={"dimension": 384},
            raw="raw_vector_data",
            llm_summary="임베딩 완료",
        )
        assert result.success is True
        assert result.output == {"dimension": 384}
        assert result._raw == "raw_vector_data"
        assert result.llm_summary == "임베딩 완료"

    def test_error_result_unchanged(self):
        """에러 결과의 to_llm_format()은 기존과 동일"""
        result = ToolResult(
            tool_name="test",
            tool_use_id="id-err",
            success=False,
            error="something went wrong",
        )
        fmt = result.to_llm_format()
        assert fmt["content"] == "Error: something went wrong"


# ── sync execute 자동 래핑 테스트 ──────────────────────────────

class SyncInput(BaseModel):
    value: int = Field(description="입력값")

class SyncOutput(BaseModel):
    result: int

class SyncTool(BaseTool[SyncInput, SyncOutput]):
    name = "sync_tool"
    description = "sync로 구현된 Tool"

    def execute(self, input: SyncInput) -> SyncOutput:
        # CPU 바운드 시뮬레이션
        return SyncOutput(result=input.value * 2)


class AsyncInput(BaseModel):
    value: int = Field(description="입력값")

class AsyncOutput(BaseModel):
    result: int

class AsyncTool(BaseTool[AsyncInput, AsyncOutput]):
    name = "async_tool"
    description = "async로 구현된 Tool"

    async def execute(self, input: AsyncInput) -> AsyncOutput:
        return AsyncOutput(result=input.value * 3)


class TestSyncExecuteWrapping:
    @pytest.mark.asyncio
    async def test_sync_tool_works(self):
        """sync execute가 자동으로 async 래핑되어 동작"""
        tool = SyncTool()
        result = await tool.safe_execute({"value": 5}, "sync-1")
        assert result.success is True
        assert result.output["result"] == 10

    @pytest.mark.asyncio
    async def test_sync_tool_schema(self):
        """sync Tool도 스키마 생성이 정상 동작"""
        tool = SyncTool()
        schema = tool.to_llm_schema()
        assert schema["name"] == "sync_tool"
        assert "value" in schema["input_schema"]["properties"]

    @pytest.mark.asyncio
    async def test_async_tool_still_works(self):
        """기존 async Tool은 그대로 동작"""
        tool = AsyncTool()
        result = await tool.safe_execute({"value": 5}, "async-1")
        assert result.success is True
        assert result.output["result"] == 15

    @pytest.mark.asyncio
    async def test_sync_tool_does_not_block_event_loop(self):
        """sync Tool이 이벤트 루프를 블로킹하지 않는지 간접 검증"""
        class SlowSyncTool(BaseTool[SyncInput, SyncOutput]):
            name = "slow_sync"
            description = "느린 sync Tool"

            def execute(self, input: SyncInput) -> SyncOutput:
                time.sleep(0.1)
                return SyncOutput(result=input.value)

        tool = SlowSyncTool()
        # 병렬로 3개 실행 — to_thread 덕에 이벤트 루프가 살아있어야 함
        tasks = [tool.safe_execute({"value": i}, f"id-{i}") for i in range(3)]
        results = await asyncio.gather(*tasks)
        assert all(r.success for r in results)


# ── 라이프사이클 테스트 ────────────────────────────────────────

class LifecycleInput(BaseModel):
    dummy: str = Field(default="x", description="더미")

class LifecycleOutput(BaseModel):
    loaded: bool

class LifecycleTool(BaseTool[LifecycleInput, LifecycleOutput]):
    name = "lifecycle"
    description = "라이프사이클 테스트용"

    def __init__(self):
        self.setup_called = False
        self.teardown_called = False
        self.model_loaded = False

    async def setup(self) -> None:
        self.setup_called = True
        self.model_loaded = True

    async def teardown(self) -> None:
        self.teardown_called = True
        self.model_loaded = False

    async def execute(self, input: LifecycleInput) -> LifecycleOutput:
        return LifecycleOutput(loaded=self.model_loaded)


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_setup_teardown_via_registry(self):
        """async with registry:로 setup/teardown 호출"""
        tool = LifecycleTool()
        registry = ToolRegistry()
        registry.register(tool)

        async with registry:
            assert tool.setup_called is True
            assert tool.model_loaded is True
            result = await registry.execute("lifecycle", {}, "lc-1")
            assert result.output["loaded"] is True

        assert tool.teardown_called is True
        assert tool.model_loaded is False

    @pytest.mark.asyncio
    async def test_teardown_order_is_reversed(self):
        """teardown은 등록 역순으로 호출"""
        order = []

        class FirstTool(BaseTool[LifecycleInput, LifecycleOutput]):
            name = "first"
            description = "첫 번째"
            async def setup(self): order.append("setup:first")
            async def teardown(self): order.append("teardown:first")
            async def execute(self, input): return LifecycleOutput(loaded=True)

        class SecondTool(BaseTool[LifecycleInput, LifecycleOutput]):
            name = "second"
            description = "두 번째"
            async def setup(self): order.append("setup:second")
            async def teardown(self): order.append("teardown:second")
            async def execute(self, input): return LifecycleOutput(loaded=True)

        registry = ToolRegistry()
        registry.register(FirstTool())
        registry.register(SecondTool())

        async with registry:
            pass

        assert order == [
            "setup:first", "setup:second",
            "teardown:second", "teardown:first",
        ]

    @pytest.mark.asyncio
    async def test_no_lifecycle_methods_is_fine(self):
        """setup/teardown을 오버라이드하지 않아도 정상 동작"""
        class SimpleTool(BaseTool[SyncInput, SyncOutput]):
            name = "simple"
            description = "단순 Tool"
            async def execute(self, input: SyncInput) -> SyncOutput:
                return SyncOutput(result=0)

        registry = ToolRegistry()
        registry.register(SimpleTool())

        async with registry:
            result = await registry.execute("simple", {"value": 1}, "s-1")
            assert result.success is True


# ── ToolContext 주입 테스트 ─────────────────────────────────────

class CtxInput(BaseModel):
    text: str = Field(description="입력 텍스트")

class CtxOutput(BaseModel):
    stored: bool

class CtxWriterTool(BaseTool[CtxInput, CtxOutput]):
    """ctx에 데이터를 저장하는 Tool"""
    name = "ctx_writer"
    description = "컨텍스트에 데이터를 저장"

    async def execute(self, input: CtxInput, *, ctx: ToolContext) -> CtxOutput:
        ctx.set("data", input.text, source=self.name)
        return CtxOutput(stored=True)


class CtxReaderInput(BaseModel):
    key: str = Field(description="읽을 키")

class CtxReaderOutput(BaseModel):
    value: str

class CtxReaderTool(BaseTool[CtxReaderInput, CtxReaderOutput]):
    """ctx에서 데이터를 읽는 Tool"""
    name = "ctx_reader"
    description = "컨텍스트에서 데이터를 읽음"

    async def execute(self, input: CtxReaderInput, *, ctx: ToolContext) -> CtxReaderOutput:
        value = ctx.get(input.key, expected_type=str)
        return CtxReaderOutput(value=value)


class NoCtxInput(BaseModel):
    msg: str = Field(description="메시지")

class NoCtxOutput(BaseModel):
    echoed: str

class NoCtxTool(BaseTool[NoCtxInput, NoCtxOutput]):
    """ctx를 받지 않는 기존 스타일 Tool"""
    name = "no_ctx"
    description = "컨텍스트 없이 동작"

    async def execute(self, input: NoCtxInput) -> NoCtxOutput:
        return NoCtxOutput(echoed=input.msg)


class TestToolContextInjection:
    @pytest.mark.asyncio
    async def test_ctx_injected_when_declared(self):
        """execute에 ctx가 선언되면 주입됨"""
        tool = CtxWriterTool()
        ctx = ToolContext()
        result = await tool.safe_execute({"text": "hello"}, "ctx-1", ctx=ctx)
        assert result.success is True
        assert ctx.get("data") == "hello"

    @pytest.mark.asyncio
    async def test_ctx_not_injected_when_not_declared(self):
        """execute에 ctx가 없으면 주입하지 않음"""
        tool = NoCtxTool()
        ctx = ToolContext()
        result = await tool.safe_execute({"msg": "world"}, "ctx-2", ctx=ctx)
        assert result.success is True
        assert result.output["echoed"] == "world"

    @pytest.mark.asyncio
    async def test_ctx_none_works_for_old_tools(self):
        """ctx=None이면 기존 Tool과 동일하게 동작"""
        tool = NoCtxTool()
        result = await tool.safe_execute({"msg": "test"}, "ctx-3")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_sync_tool_with_ctx(self):
        """sync Tool에서도 ctx 주입이 동작"""
        class SyncCtxTool(BaseTool[CtxInput, CtxOutput]):
            name = "sync_ctx"
            description = "sync + ctx"

            def execute(self, input: CtxInput, *, ctx: ToolContext) -> CtxOutput:
                ctx.set("sync_data", input.text, source=self.name)
                return CtxOutput(stored=True)

        tool = SyncCtxTool()
        ctx = ToolContext()
        result = await tool.safe_execute({"text": "sync hello"}, "sctx-1", ctx=ctx)
        assert result.success is True
        assert ctx.get("sync_data") == "sync hello"


# ── E2E 파이프라인 테스트 ──────────────────────────────────────

class EmbedInput(BaseModel):
    text: str = Field(description="임베딩할 텍스트")

class EmbedOutput(BaseModel):
    dimension: int

class MockEmbedTool(BaseTool[EmbedInput, EmbedOutput]):
    """mock 임베딩 Tool — 텍스트를 가짜 벡터로 변환"""
    name = "embed_text"
    description = "텍스트를 벡터로 변환"

    def __init__(self):
        self.model_loaded = False

    async def setup(self):
        self.model_loaded = True

    async def teardown(self):
        self.model_loaded = False

    def execute(self, input: EmbedInput, *, ctx: ToolContext) -> EmbedOutput:
        # 가짜 벡터 (리스트로 표현)
        vector = [float(ord(c)) for c in input.text[:5]]
        ctx.set("query_vector", vector, source=self.name)
        return EmbedOutput(dimension=len(vector))


class SearchInput(BaseModel):
    top_k: int = Field(default=3, description="반환할 결과 수")
    vector_key: str = Field(default="query_vector", description="ToolContext 키")

class SearchOutput(BaseModel):
    results: list[str]

class MockVectorSearchTool(BaseTool[SearchInput, SearchOutput]):
    """mock 벡터 검색 Tool — ctx에서 벡터를 가져와 검색"""
    name = "vector_search"
    description = "벡터 유사도 검색"

    def execute(self, input: SearchInput, *, ctx: ToolContext) -> SearchOutput:
        vector = ctx.get(input.vector_key, expected_type=list)
        # 가짜 검색 결과
        results = [f"doc_{i}_dim{len(vector)}" for i in range(input.top_k)]
        return SearchOutput(results=results)


class TestE2EPipeline:
    @pytest.mark.asyncio
    async def test_embed_then_search_via_context(self):
        """embed → ToolContext → vector_search 파이프라인"""
        registry = ToolRegistry()
        registry.register(MockEmbedTool())
        registry.register(MockVectorSearchTool())

        async with registry:
            ctx = ToolContext()

            # 1. embed
            embed_result = await registry.execute(
                "embed_text", {"text": "hello"}, "e-1", ctx=ctx
            )
            assert embed_result.success is True
            assert embed_result.output["dimension"] == 5
            assert ctx.has("query_vector")

            # 2. vector search (ctx 경유로 벡터 전달)
            search_result = await registry.execute(
                "vector_search", {"top_k": 2}, "s-1", ctx=ctx
            )
            assert search_result.success is True
            assert len(search_result.output["results"]) == 2
            assert "dim5" in search_result.output["results"][0]

    @pytest.mark.asyncio
    async def test_pipeline_via_execute_many(self):
        """execute_many로 ctx가 공유되는지 검증"""
        registry = ToolRegistry()
        registry.register(MockEmbedTool())
        registry.register(MockVectorSearchTool())

        async with registry:
            ctx = ToolContext()

            # embed 먼저 실행
            await registry.execute("embed_text", {"text": "test"}, "e-2", ctx=ctx)

            # vector_search를 execute_many로 실행
            results = await registry.execute_many(
                [{"name": "vector_search", "input": {"top_k": 3}, "id": "s-2"}],
                ctx=ctx,
            )
            assert len(results) == 1
            assert results[0].success is True
            assert len(results[0].output["results"]) == 3


# ── 하위 호환성 테스트 ─────────────────────────────────────────

class TestBackwardCompatibility:
    @pytest.mark.asyncio
    async def test_existing_tool_works_without_ctx(self):
        """기존 Tool (ctx 없음)이 변경 없이 동작"""

        class OldInput(BaseModel):
            x: int = Field(description="입력")

        class OldOutput(BaseModel):
            y: int

        class OldTool(BaseTool[OldInput, OldOutput]):
            name = "old_tool"
            description = "기존 스타일 Tool"

            async def execute(self, input: OldInput) -> OldOutput:
                return OldOutput(y=input.x + 1)

        tool = OldTool()
        # ctx 없이 호출 (기존 시그니처)
        result = await tool.safe_execute({"x": 10}, "old-1")
        assert result.success is True
        assert result.output["y"] == 11

    @pytest.mark.asyncio
    async def test_registry_execute_without_ctx(self):
        """registry.execute()가 ctx 없이 기존대로 동작"""

        class EchoInput(BaseModel):
            msg: str = Field(description="메시지")

        class EchoOutput(BaseModel):
            echoed: str

        class EchoTool(BaseTool[EchoInput, EchoOutput]):
            name = "echo_compat"
            description = "에코"

            async def execute(self, input: EchoInput) -> EchoOutput:
                return EchoOutput(echoed=input.msg)

        registry = ToolRegistry()
        registry.register(EchoTool())

        # ctx 파라미터 없이 기존 시그니처로 호출
        result = await registry.execute("echo_compat", {"msg": "hi"}, "e-1")
        assert result.success is True

    def test_tool_result_backward_compat(self):
        """기존 ToolResult 생성 방식이 그대로 동작"""
        result = ToolResult(
            tool_name="test",
            tool_use_id="bc-1",
            success=True,
            output={"key": "value"},
        )
        fmt = result.to_llm_format()
        assert "value" in fmt["content"]
        assert result._raw is None
        assert result.llm_summary is None
