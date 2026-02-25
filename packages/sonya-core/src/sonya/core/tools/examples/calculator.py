"""
내장 Tool: 계산기
- ast.literal_eval 기반 안전한 수식 평가
- exec/eval 사용 금지
"""

import ast
import operator

from pydantic import BaseModel, Field

from ..base import BaseTool
from ..error import ToolError

# 허용하는 연산자 매핑
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    """AST 노드를 재귀적으로 평가 (허용된 연산만)"""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _OPERATORS:
            raise ValueError(f"허용되지 않은 연산자: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _OPERATORS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _OPERATORS:
            raise ValueError(f"허용되지 않은 단항 연산자: {op_type.__name__}")
        operand = _safe_eval(node.operand)
        return _OPERATORS[op_type](operand)
    raise ValueError(f"허용되지 않은 표현식: {ast.dump(node)}")


class CalculatorInput(BaseModel):
    """계산기 입력 스키마"""
    expression: str = Field(description="평가할 수식 (예: '2 + 3 * 4')")


class CalculatorOutput(BaseModel):
    """계산기 출력 스키마"""
    result: float = Field(description="계산 결과")


class CalculatorTool(BaseTool[CalculatorInput, CalculatorOutput]):
    """
    계산기 Tool

    LLM이 수학 계산이 필요할 때 호출한다.
    ast 기반 안전한 수식 평가만 지원 (eval/exec 사용 안 함).
    """
    name = "calculator"
    description = "수학 수식을 안전하게 평가하고 결과를 반환한다."

    async def execute(self, input: CalculatorInput) -> CalculatorOutput:
        try:
            tree = ast.parse(input.expression, mode="eval")
            result = _safe_eval(tree)
            return CalculatorOutput(result=result)
        except (ValueError, SyntaxError, TypeError, ZeroDivisionError) as e:
            raise ToolError(self.name, f"수식 평가 실패: {e}", recoverable=True)
