"""
Tool/Skill implementations for the chatbot
"""
import requests
import json


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

            if results:
                return "\n".join(results)
            else:
                return "No results found for the query."

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

    @staticmethod
    def calculate(expression: str) -> str:
        """
        Safely evaluate a math expression

        :param expression: Math expression (e.g., "2 + 2 * 3")
        :return: Result of the calculation
        """
        try:
            # Only allow safe math operations
            allowed_names = {"__builtins__": {}}
            result = eval(expression, allowed_names)
            return str(result)
        except Exception as e:
            return f"Calculation failed: {str(e)}"

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



