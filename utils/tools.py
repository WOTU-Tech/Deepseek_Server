"""
Tool/Skill implementations for the chatbot
"""
import ast
import math
import requests
import json
import re


class WebSearchTool:
    """Web search tool using DuckDuckGo API"""

    @staticmethod
    def search(query: str, max_results: int = 5) -> str:
        """
        Perform a web search using DuckDuckGo's API (no key required)

        :param query: Search query
        :param max_results: Maximum number of results to return
        :return: Formatted search results
        """
        try:
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_redirect": 1
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = []

            # Add abstract if available
            if data.get("AbstractText"):
                results.append(f"Summary: {data['AbstractText']}")

            # Add related topics
            if data.get("Results"):
                for i, result in enumerate(data["Results"][:max_results], 1):
                    title = result.get("Text", "No title")
                    url = result.get("FirstURL", "No URL")
                    results.append(f"{i}. {title}\n   URL: {url}")

            # Add heading for context
            if data.get("Heading"):
                results.insert(0, f"Topic: {data['Heading']}")

            if results:
                return "\n".join(results)
            else:
                return (
                    f"No results found for '{query}'. "
                    f"DuckDuckGo API does not have specific information about this topic. "
                    f"You may not have real-time knowledge about this subject."
                )

        except Exception as e:
            return f"Web search failed: {str(e)}"

    @staticmethod
    def get_definition():
        """Return tool definition for function calling"""
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for information using DuckDuckGo",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        }


class CalculatorTool:
    """Simple calculator tool for math operations"""

    # Whitelist of allowed AST node types (only math operations)
    _ALLOWED_AST = {
        ast.Constant, ast.UnaryOp, ast.BinOp, ast.Call, ast.Add, ast.Sub,
        ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.Name,
    }

    # Whitelist of allowed built-in math functions
    _SAFE_MATH = {
        "abs": abs, "round": round, "floor": math.floor,
        "ceil": math.ceil, "sqrt": math.sqrt, "sin": math.sin,
        "cos": math.cos, "tan": math.tan, "pi": math.pi,
        "e": math.e, "log": math.log, "log10": math.log10,
        "exp": math.exp, "degrees": math.degrees, "radians": math.radians,
    }

    @classmethod
    def _validate_ast(cls, node: ast.AST) -> bool:
        """Recursively validate that an AST node contains only safe math operations."""
        if type(node) not in cls._ALLOWED_AST:
            # Allow UnaryOp to have a Minus operand
            if type(node) == ast.UnaryOp:
                return cls._validate_ast(node.operand)
            return False
        for child in ast.iter_child_nodes(node):
            if not cls._validate_ast(child):
                return False
        return True

    @classmethod
    def _evaluate(cls, node: ast.AST) -> float:
        """Safely evaluate a validated AST node."""
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise ValueError("Non-numeric constant")
            return float(node.value)

        if isinstance(node, ast.UnaryOp):
            operand = cls._evaluate(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return operand
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

        if isinstance(node, ast.BinOp):
            return cls._parse_binop(node)

        if isinstance(node, ast.Call):
            return cls._parse_function_call(node)

        raise ValueError(f"Unexpected AST node: {type(node).__name__}")

    @classmethod
    def _parse_function_call(cls, node: ast.Call) -> float:
        """Safely evaluate a function call like sqrt(16)."""
        if not isinstance(node.func, ast.Name):
            raise ValueError("Invalid function call")
        name = node.func.id
        if name not in cls._SAFE_MATH:
            raise ValueError(f"Function '{name}' not allowed")
        func = cls._SAFE_MATH[name]
        if not node.args:
            raise ValueError(f"No arguments for {name}")
        args = [cls._evaluate(a) for a in node.args]
        return func(*args)

    @classmethod
    def _parse_binop(cls, node: ast.BinOp) -> float:
        """Safely evaluate a binary operation."""
        left = cls._evaluate(node.left)
        right = cls._evaluate(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return left / right
        if isinstance(node.op, ast.Pow):
            return left ** right
        if isinstance(node.op, ast.Mod):
            if right == 0:
                raise ZeroDivisionError("Modulo by zero")
            return left % right
        raise ValueError(f"Unsupported operator: {type(node.op).__name__}")

    @classmethod
    def calculate(cls, expression: str) -> str:
        """
        Safely evaluate a math expression using AST analysis.

        :param expression: Math expression (e.g., "2 + 2 * 3", "sqrt(16)", "sin(pi/2)")
        :return: Result of the calculation
        """
        expression = expression.strip()
        if not expression:
            return "Calculation failed: empty expression"
        # Reject anything that looks like it could be code injection
        suspicious = re.search(
            r'(?i)(?:import |__|eval\(|exec\(|compile\(|open\(|lambda |assert |\bdef\b|\bclass\b)',
            expression,
        )
        if suspicious:
            return "Calculation failed: expression contains disallowed constructs"
        try:
            tree = ast.parse(expression, mode="eval")
            if not cls._validate_ast(tree.body):
                return "Calculation failed: expression contains disallowed operations"
            result = cls._evaluate(tree.body)
            # Format: drop trailing .0 for integers
            if isinstance(result, float) and result.is_integer() and not (result == float("inf") or result == float("-inf")):
                return str(int(result))
            return str(result)
        except SyntaxError as e:
            return f"Calculation failed: invalid syntax ({e})"
        except (ValueError, ZeroDivisionError) as e:
            return f"Calculation failed: {e}"
        except Exception as e:
            return f"Calculation failed: unexpected error ({e})"

    @staticmethod
    def get_definition():
        """Return tool definition for function calling"""
        return {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "Perform mathematical calculations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to evaluate (e.g., '2 + 2', 'sqrt(16)')"
                        }
                    },
                    "required": ["expression"]
                }
            }
        }


class DocumentReadTool:
    """Tool for reading and searching uploaded documents"""

    # This will be set by the conversation module
    document_store = None

    @staticmethod
    def read_document(document_id: str, section: str = None) -> str:
        """
        Read content from an uploaded document

        :param document_id: ID of the document to read
        :param section: Optional search query within the document
        :return: Document content or relevant sections
        """
        if not DocumentReadTool.document_store:
            return "No documents uploaded or document store not initialized"

        doc = DocumentReadTool.document_store.get_document(document_id)
        if not doc:
            return f"Document '{document_id}' not found"

        # If section is specified, search for relevant content
        if section:
            chunks = DocumentReadTool.document_store.search_document(document_id, section)
            if chunks:
                return f"Relevant sections from '{doc['filename']}':\n\n" + "\n\n---\n\n".join(chunks)
            else:
                return f"No sections found matching '{section}' in document"

        # Return full content summary (limit to first 3000 chars for context)
        content = doc["content"][:3000]
        if len(doc["content"]) > 3000:
            content += f"\n\n... (Document has {len(doc['content'])} total characters)"

        return f"Content from '{doc['filename']}':\n\n{content}"

    @staticmethod
    def get_definition():
        """Return tool definition for function calling"""
        return {
            "type": "function",
            "function": {
                "name": "read_document",
                "description": "Read content from an uploaded document, optionally search for specific sections",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "string",
                            "description": "ID of the document to read (e.g., 'doc_1', 'doc_2')"
                        },
                        "section": {
                            "type": "string",
                            "description": "Optional: keyword or phrase to search for within the document"
                        }
                    },
                    "required": ["document_id"]
                }
            }
        }


# Tool registry
TOOLS = {
    "web_search": WebSearchTool,
    "calculator": CalculatorTool,
    "read_document": DocumentReadTool
}



