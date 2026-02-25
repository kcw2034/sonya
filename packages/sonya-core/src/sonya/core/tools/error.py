"""
Tool 에러 정의
- Tool 실행 중 발생하는 에러를 구조화
- recoverable 플래그로 LLM 재시도 가능 여부 전달
"""


class ToolError(Exception):
    """
    Tool 실행 중 발생하는 에러

    Tool.execute() 내부에서 raise하면
    BaseTool.safe_execute()가 잡아서 ToolResult(success=False)로 변환한다.

    Args:
        tool_name: 에러가 발생한 Tool 이름
        message: 에러 메시지 (LLM에게 전달됨)
        recoverable: True면 LLM이 입력을 바꿔 재시도 가능
    """
    def __init__(self, tool_name: str, message: str, recoverable: bool = True):
        self.tool_name = tool_name
        self.message = message
        self.recoverable = recoverable
        super().__init__(f"[{tool_name}] {message}")