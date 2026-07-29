"""Safe evaluator for arithmetic expressions typed into amount input fields."""

import ast
import re

from .formatting import parse_amount

_NUMBER_PATTERN = re.compile(r"[\d.,]+")

_ALLOWED_BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
_ALLOWED_UNARY_OPS = (ast.UAdd, ast.USub)


def evaluate_expression(raw: str) -> float:
    """Evaluates a `+`, `-`, `*`, `/` arithmetic expression typed into an amount field.

    Numbers use the app's display convention (`.` for thousands, `,` for decimals, see
    `:func:parse_amount`); a plain number with no operators is a valid (trivial) expression, so
    this is a drop-in replacement for `:func:parse_amount` at any amount-field call site.

    Args:
        raw (str): The raw text typed by the user, e.g. "10,0 + 2,3 - 5" or "1.234,56".

    Returns:
        float: The evaluated result.

    Raises:
        ValueError: If `raw` is not a well-formed expression using only numbers, `+`, `-`, `*`,
            `/`, and parentheses.
    """
    normalized = _NUMBER_PATTERN.sub(lambda match: repr(parse_amount(match.group())), raw)

    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"'{raw}' is not a valid number or expression.") from e

    try:
        return _eval_node(tree.body)
    except ZeroDivisionError as e:
        raise ValueError("Division by zero.") from e


def _eval_node(node: ast.expr) -> float:
    """Recursively evaluates a whitelisted subset of an arithmetic AST.

    Args:
        node (ast.expr): The AST node to evaluate.

    Returns:
        float: The node's value.

    Raises:
        ValueError: If the node (or one of its children) is not a number, a whitelisted binary
            operation, or a whitelisted unary operation.
    """
    if isinstance(node, ast.Constant) and (type(node.value) is int or type(node.value) is float):
        return node.value

    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BIN_OPS):
        left, right = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return left / right

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARY_OPS):
        value = _eval_node(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value

    raise ValueError("Expression contains something other than numbers, +, -, *, /, and parentheses.")
