import requests
import json
from utils.tools import TOOLS, DocumentReadTool
from utils.document_handler import DocumentStore

CONTENT_TYPE_JSON = {"Content-Type": "application/json"}


class SkillManager:
    """Manages available tools/skills for the chatbot"""

    def __init__(self):
        self.tools = {}

    def register_tool(self, tool_name: str, tool_class):
        """Register a tool class"""
        self.tools[tool_name] = tool_class

    def get_tool_definitions(self):
        """Get tool definitions for the model"""
        definitions = []
        for tool_class in self.tools.values():
            definitions.append(tool_class.get_definition())
        return definitions

    def execute_tool(self, tool_name: str, args: dict):
        """Execute a tool with the given arguments"""
        if tool_name not in self.tools:
            return f"Tool '{tool_name}' not found"

        tool_class = self.tools[tool_name]

        # Call the appropriate method based on tool name
        if tool_name == "web_search":
            return tool_class.search(**args)
        elif tool_name == "calculator":
            return tool_class.calculate(**args)
        elif tool_name == "read_document":
            return tool_class.read_document(**args)
        else:
            return f"Unknown tool: {tool_name}"


class OllamaChat:
    def __init__(self, base_url="http://localhost:8080/v1", model="Qwen3.6-35B-A3B-UD-Q4_K_M"):
        """
        Initialize the OllamaChat API wrapper.

        :param base_url: The base URL of the Ollama API server.
        :param model: The model to use for chat (default is 'llama2').
        """
        self.base_url = base_url
        self.model = model
        self.messages = []
        self.skills = SkillManager()
        self.document_store = DocumentStore()
        
        # Set document store reference for DocumentReadTool
        DocumentReadTool.document_store = self.document_store
        
        # Register default tools
        for tool_name, tool_class in TOOLS.items():
            self.skills.register_tool(tool_name, tool_class)

    def _build_messages(self, prompt):
        """Build messages with optional system context for document awareness."""
        if "###" in prompt:
            self.messages = []
            return None

        # Check for available documents and inject system context
        if self.document_store and self.document_store.documents:
            doc_list = "\n".join(
                f"- Document ID: '{doc_id}', Filename: {info['filename']}"
                for doc_id, info in self.document_store.documents.items()
            )
            system_msg = (
                "You have access to uploaded documents. Users may ask questions about them. "
                "To read a document, use the 'read_document' tool with a document_id. "
                "You can also search for specific content using the 'section' parameter. "
                f"Available documents:\n{doc_list}"
            )
            messages = [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}]
        else:
            messages = [{"role": "user", "content": prompt}]
        return messages

    def chat(self, prompt, stream=False):
        """
        Send a chat prompt to the Ollama API and get the response.

        :param prompt: The input prompt for the chat.
        :param stream: Whether to stream the response (default is False).
        :return: The response from the Ollama API.
        """
        messages = self._build_messages(prompt)
        if messages is None:
            return None
        messages = messages[-2:]  # only keep the last message(s)
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "temperature": 0.5,  # Controls randomness (lower values make the output more deterministic).
        }
        headers = CONTENT_TYPE_JSON
        # Include tools if documents are available
        if self.document_store and self.document_store.documents and self.skills.tools:
            payload["tools"] = self.skills.get_tool_definitions()
            payload["tool_choice"] = "auto"

        response = requests.post(url, json=payload, headers=headers)

        try:
            if response.status_code == 200:
                response_json = response.json()
                # Handle OpenAI-compatible format
                if "choices" in response_json:
                    content = response_json["choices"][0]["message"]["content"]
                else:
                    content = response_json["message"]["content"]


                # Return in consistent format
                return {
                    "message": {
                        "content": content
                    }
                }
            else:
                response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            print(f"Encounter error: {err}, please clear the cache and try again.")

    def _process_tool_call(self, tool_call):
        """Helper method to process a single tool call"""
        tool_name = tool_call["function"]["name"]
        tool_args = json.loads(tool_call["function"]["arguments"])

        print(f"[Tool Call] {tool_name}({tool_args})")

        # Execute the tool
        tool_result = self.skills.execute_tool(tool_name, tool_args)

        # Return tool result message
        return {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": tool_name,
            "content": tool_result
        }

    def _handle_model_response(self, response_json):
        """Helper method to extract message from model response"""
        if "choices" in response_json:
            choice = response_json["choices"][0]
            message = choice["message"]
        else:
            message = response_json["message"]
        return message

    def _call_model(self, stream=False):
        """Helper method to call the model with current messages"""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": self.messages,
            "stream": stream,
            "temperature": 0.5,
        }

        # Add tool definitions if any tools are registered
        if self.skills.tools:
            payload["tools"] = self.skills.get_tool_definitions()
            payload["tool_choice"] = "auto"

        response = requests.post(url, json=payload, headers=CONTENT_TYPE_JSON)
        return response

    def chat_with_tools(self, prompt, stream=False, max_iterations=10):
        """
        Chat with the model with tool support (agent loop).
        The model can request to use tools, which are executed and fed back.

        :param prompt: The input prompt for the chat.
        :param stream: Whether to stream the response (default is False).
        :param max_iterations: Maximum number of tool calls before stopping (prevents infinite loops).
        :return: The final response from the model.
        """
        if "###" in prompt:
            self.messages = []
            return None

        # Build messages with document context
        messages = self._build_messages(prompt)
        if messages is None:
            return None
        self.messages = messages[:4]  # Keep a bit more history for context

        # Agent loop
        for _ in range(max_iterations):
            try:
                response = self._call_model(stream)

                if response.status_code != 200:
                    response.raise_for_status()

                response_json = response.json()
                message = self._handle_model_response(response_json)
                self.messages.insert(0, message)

                # Check if model wants to call a tool
                if "tool_calls" in message and message["tool_calls"]:
                    # Process all tool calls
                    for tool_call in message["tool_calls"]:
                        tool_result = self._process_tool_call(tool_call)
                        self.messages.insert(0, tool_result)
                    continue

                # Model gave a final response (no tool calls)
                content = message.get("content", "")
                return {
                    "message": {
                        "content": content
                    }
                }
            except requests.exceptions.HTTPError as err:
                print(f"Encounter error: {err}, please clear the cache and try again.")
                return None

        # If we hit max iterations, return current response
        content = self.messages[0].get("content", "") if self.messages else "Max iterations reached"
        return {
            "message": {
                "content": content
            }
        }


    def generate(self, prompt, stream=False):
        """
        Generate a response from the Ollama API.

        :param prompt: The input prompt for generation.
        :param stream: Whether to stream the response (default is False).
        :return: The response from the Ollama API.
        """
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream
        }

        response = requests.post(url, json=payload, headers=CONTENT_TYPE_JSON)

        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()


# Example usage
if __name__ == "__main__":
    ollama = OllamaChat()
    # Chat example
    while True:
        prompt = input("> ")
        chat_response = ollama.chat(prompt)
        print("Chat Response:", chat_response["message"]["content"])
