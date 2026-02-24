"""
Tool 레이어 동작 검증 테스트
python -m pytest tests/test_tools.py -v
"""

import pytest
from pydantic import BaseModel, Field

from sonya_core.tools.base import BaseTool, ToolError, ToolResult
from sonya_core.tools.examples.web_search import WebSearchTool
from sonya_core.tools.examples.write_file import WriteFileTool
from sonya_core.tools.registry import ToolRegistry


# ── 테스트용 더미 Tool ─────────────────────────────────────────

class EchoInput(BaseModel):
    message: str = Field(description="에코할 메시지")

class EchoOutput(BaseModel):
    echoed: str

class EchoTool(BaseTool[EchoInput, EchoOutput]):
    name = "echo"
    description = "입력 메시지를 그대로 반환하는 테스트용 Tool"

    async def execute(self, input: EchoInput) -> EchoOutput:
        return EchoOutput(echoed=input.message)


class AlwaysFailInput(BaseModel):
    reason: str = Field(description="실패 이유")

class AlwaysFailOutput(BaseModel):
    pass

class AlwaysFailTool(BaseTool[AlwaysFailInput, AlwaysFailOutput]):
    name = "always_fail"
    description = "항상 실패하는 테스트용 Tool"

    async def execute(self, input: AlwaysFailInput) -> AlwaysFailOutput:
        raise ToolError(self.name, f"의도적 실패: {input.reason}", recoverable=True)


# ── BaseTool 테스트 ────────────────────────────────────────────

class TestBaseTool:
    @pytest.mark.asyncio
    async def test_execute_returns_output(self):
        tool = EchoTool()
        result = await tool.safe_execute({"message": "hello"}, "test-id-1")
        assert result.success is True
        assert result.output["echoed"] == "hello"

    @pytest.mark.asyncio
    async def test_tool_error_is_caught(self):
        tool = AlwaysFailTool()
        result = await tool.safe_execute({"reason": "테스트 실패"}, "test-id-2")
        assert result.success is False
        assert "의도적 실패" in result.error

    @pytest.mark.asyncio
    async def test_invalid_input_is_caught(self):
        tool = EchoTool()
        # 필수 필드 누락
        result = await tool.safe_execute({}, "test-id-3")
        assert result.success is False

    def test_schema_generation(self):
        tool = EchoTool()
        schema = tool.to_llm_schema()
        assert schema["name"] == "echo"
        assert schema["description"] == tool.description
        assert "input_schema" in schema
        assert "message" in schema["input_schema"]["properties"]

    def test_tool_result_to_llm_format(self):
        result = ToolResult(
            tool_name="echo",
            tool_use_id="abc-123",
            success=True,
            output={"echoed": "hi"},
        )
        fmt = result.to_llm_format()
        assert fmt["type"] == "tool_result"
        assert fmt["tool_use_id"] == "abc-123"
        assert "hi" in fmt["content"]

    def test_missing_name_raises(self):
        with pytest.raises(TypeError):
            class BadTool(BaseTool[EchoInput, EchoOutput]):
                # name 누락
                description = "bad"
                async def execute(self, input): pass


# ── ToolRegistry 테스트 ────────────────────────────────────────

class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        tool = registry.get("echo")
        assert tool.name == "echo"

    def test_get_nonexistent_raises(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_schemas_returns_all(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        registry.register(AlwaysFailTool())
        schemas = registry.schemas()
        names = [s["name"] for s in schemas]
        assert "echo" in names
        assert "always_fail" in names

    @pytest.mark.asyncio
    async def test_execute_via_registry(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        result = await registry.execute("echo", {"message": "registry test"}, "id-1")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_many_parallel(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        tool_calls = [
            {"name": "echo", "input": {"message": f"msg-{i}"}, "id": f"id-{i}"}
            for i in range(5)
        ]
        results = await registry.execute_many(tool_calls)
        assert len(results) == 5
        assert all(r.success for r in results)

    def test_chaining(self):
        registry = (
            ToolRegistry()
            .register(EchoTool())
            .register(AlwaysFailTool())
        )
        assert len(registry) == 2


# ── 실제 Tool 동작 테스트 ──────────────────────────────────────

class TestWebSearchTool:
    @pytest.mark.asyncio
    async def test_basic_search(self):
        tool = WebSearchTool()
        result = await tool.safe_execute(
            {"query": "Python asyncio", "max_results": 3}, "ws-1"
        )
        assert result.success is True
        assert len(result.output["results"]) <= 3

    def test_schema_has_correct_fields(self):
        schema = WebSearchTool().to_llm_schema()
        props = schema["input_schema"]["properties"]
        assert "query" in props
        assert "max_results" in props


class TestWriteFileTool:
    @pytest.mark.asyncio
    async def test_write_and_verify(self, tmp_path):
        tool = WriteFileTool(output_dir=str(tmp_path))
        result = await tool.safe_execute(
            {"filename": "test.md", "content": "# Hello\n테스트 내용", "overwrite": False},
            "wf-1",
        )
        assert result.success is True
        assert (tmp_path / "test.md").read_text() == "# Hello\n테스트 내용"

    @pytest.mark.asyncio
    async def test_no_overwrite_raises(self, tmp_path):
        tool = WriteFileTool(output_dir=str(tmp_path))
        await tool.safe_execute(
            {"filename": "dup.md", "content": "first", "overwrite": False}, "wf-2"
        )
        result = await tool.safe_execute(
            {"filename": "dup.md", "content": "second", "overwrite": False}, "wf-3"
        )
        assert result.success is False
        assert "overwrite" in result.error

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tmp_path):
        tool = WriteFileTool(output_dir=str(tmp_path))
        # ../../../etc/passwd 같은 경로는 파일명만 추출됨
        result = await tool.safe_execute(
            {"filename": "../../../evil.txt", "content": "pwned", "overwrite": False},
            "wf-4",
        )
        # evil.txt로만 저장되어야 함 (상위 디렉토리 접근 불가)
        if result.success:
            assert "evil.txt" in result.output["filepath"]
            assert str(tmp_path) in result.output["filepath"]