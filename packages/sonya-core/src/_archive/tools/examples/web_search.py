"""
내장 Tool: 웹 검색
- 웹에서 정보를 검색하고 결과를 반환
- TODO: 실제 검색 API (Serper, Tavily 등) 연동 필요
"""

from pydantic import BaseModel, Field

from ..base import BaseTool
from ..error import ToolError


class WebSearchInput(BaseModel):
    """웹 검색 입력 스키마"""
    query: str = Field(description="검색할 쿼리 문자열")
    max_results: int = Field(default=5, ge=1, le=20, description="반환할 최대 결과 수")


class SearchResult(BaseModel):
    """개별 검색 결과"""
    title: str
    url: str
    snippet: str


class WebSearchOutput(BaseModel):
    """웹 검색 출력 스키마"""
    results: list[SearchResult]
    total_found: int


class WebSearchTool(BaseTool[WebSearchInput, WebSearchOutput]):
    """
    웹 검색 Tool

    LLM이 최신 정보나 사실 확인이 필요할 때 호출한다.
    현재는 mock 데이터를 반환하며, 실제 검색 API 연동이 필요하다.
    """
    name = "web_search"
    description = "웹에서 정보를 검색하고 관련 결과를 반환한다. 최신 정보나 특정 사실 확인이 필요할 때 사용."

    async def execute(self, input: WebSearchInput) -> WebSearchOutput:
        # TODO: 실제 검색 API (Serper, Tavily 등) 연동
        try:
            mock_results = [
                SearchResult(
                    title=f"결과 {i+1}: {input.query}에 관한 문서",
                    url=f"https://example.com/result-{i+1}",
                    snippet=f"'{input.query}'와 관련된 내용입니다. 자세한 정보는 링크를 참조하세요.",
                )
                for i in range(min(input.max_results, 3))
            ]
            return WebSearchOutput(results=mock_results, total_found=len(mock_results))
        except Exception as e:
            raise ToolError(self.name, f"검색 실패: {e}", recoverable=True)