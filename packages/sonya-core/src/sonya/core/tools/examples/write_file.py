"""
내장 Tool: 파일 작성
- 지정된 output_dir에 파일을 안전하게 생성
- 경로 순회 공격 차단 (파일명만 추출)
"""

from pathlib import Path

from pydantic import BaseModel, Field

from ..base import BaseTool
from ..error import ToolError


class WriteFileInput(BaseModel):
    """파일 작성 입력 스키마"""
    filename: str = Field(description="저장할 파일명")
    content: str = Field(description="파일에 쓸 내용")
    overwrite: bool = Field(default=False, description="기존 파일 덮어쓰기 허용 여부")


class WriteFileOutput(BaseModel):
    """파일 작성 출력 스키마"""
    filepath: str = Field(description="저장된 파일의 절대 경로")


class WriteFileTool(BaseTool[WriteFileInput, WriteFileOutput]):
    """
    파일 작성 Tool

    지정된 output_dir 내에 파일을 생성한다.
    경로 순회 공격을 차단하여 output_dir 외부에는 쓸 수 없다.
    """
    name = "write_file"
    description = "지정된 디렉토리에 파일을 생성한다. 파일명과 내용을 받아 저장하고 경로를 반환."

    def __init__(self, output_dir: str):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def execute(self, input: WriteFileInput) -> WriteFileOutput:
        # 경로 순회 차단: 파일명만 추출
        safe_name = Path(input.filename).name
        filepath = self._output_dir / safe_name

        if filepath.exists() and not input.overwrite:
            raise ToolError(
                self.name,
                f"파일이 이미 존재합니다: {safe_name}. overwrite=True로 설정하세요.",
                recoverable=True,
            )

        filepath.write_text(input.content, encoding="utf-8")
        return WriteFileOutput(filepath=str(filepath))
