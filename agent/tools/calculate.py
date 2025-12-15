import ast
import operator as op
from typing import Any, Dict
from langchain_core.tools import tool


# 一个“安全版四则运算”工具（避免直接 eval）
_ALLOWED_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.USub: op.neg,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
}

def _safe_eval(expr: str) -> float:
    def _eval(node):
        if isinstance(node, ast.Num):  # py<3.8
            return node.n
        if isinstance(node, ast.Constant):  # py>=3.8
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Only int/float constants are allowed")
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](_eval(node.operand))
        raise ValueError("Unsupported expression")

    tree = ast.parse(expr, mode="eval")
    return float(_eval(tree.body))


@tool
def calculator(expression: str) -> str:
    """做四则运算/乘方/取模等数学计算。输入例如：'2 + 3*4'、'(1+2)**3'。"""
    try:
        return str(_safe_eval(expression))
    except Exception as e:
        return f"计算失败：{e}"


@tool
def echo(text: str) -> str:
    """原样复述（用于演示工具调用）。"""
    return text