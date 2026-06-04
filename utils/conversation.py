import requests
import json
import uuid
from utils.tools import TOOLS, DocumentReadTool
from utils.document_handler import DocumentStore

CONTENT_TYPE_JSON = {"Content-Type": "application/json"}


_current_instance: "OllamaChat | None" = None


def _is_coding_question(prompt: str) -> bool:
    """
    Detect if a prompt is asking about coding/programming.
    Coding questions are allowed unlimited tokens.
    Non-coding questions are limited to 1000 tokens.
    """
    coding_keywords = {
        "code", "coding", "program", "programming", "python", "javascript", "java", "c++",
        "function", "method", "class", "algorithm", "debug", "error", "exception",
        "write", "implement", "develop", "script", "api", "library", "framework",
        "bug", "fix", "optimize", "refactor", "compile", "execute", "run",
        "html", "css", "sql", "git", "docker", "kubernetes", "react", "django",
        "flask", "fastapi", "nodejs", "npm", "pip", "package", "module", "import",
        "variable", "loop", "condition", "regex", "json", "xml", "database",
        "server", "client", "request", "response", "endpoint", "route"
    }

    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in coding_keywords)


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
    @classmethod
    def _current(cls) -> "OllamaChat":
        """Return the most recently created OllamaChat instance."""
        if _current_instance is None:
            _current_instance = cls()
        return _current_instance

    def __init__(self, base_url="http://localhost:8080/v1", model="Qwen3.6-35B-A3B-UD-Q4_K_M"):
        """
        Initialize the OllamaChat API wrapper.

        :param base_url: The base URL of the Ollama API server.
        :param model: The model to use for chat (default is 'llama2').
        """
        self.base_url = base_url
        self.model = model
        self.messages = []
        self.images = []  # List of {"id": str, "data": str (base64), "filename": str}
        global _current_instance
        self.skills = SkillManager()
        self.document_store = DocumentStore()

        # Set document store reference for DocumentReadTool
        DocumentReadTool.document_store = self.document_store

        # Register default tools
        for tool_name, tool_class in TOOLS.items():
            self.skills.register_tool(tool_name, tool_class)

        _current_instance = self

    # Image management methods

    def add_image(self, base64_data: str, filename: str) -> dict:
        """Add an image to the list and return its info."""
        image_id = f"img_{uuid.uuid4().hex[:8]}"
        image_info = {"id": image_id, "data": base64_data, "filename": filename}
        self.images.append(image_info)
        return image_info

    def list_images(self) -> list:
        """Return list of image IDs and filenames (without base64 data)."""
        return [{"id": img["id"], "filename": img["filename"]} for img in self.images]

    def delete_image(self, image_id: str):
        """Remove an image by ID."""
        self.images = [img for img in self.images if img["id"] != image_id]

    def clear_images(self):
        """Clear all images."""
        self.images = []

    def _build_messages(self, prompt):
        """Build messages with optional system context for document awareness and image injection."""
        if "###" in prompt:
            self.messages = []
            return None

        # Build the user message content
        if self.images:
            # Vision mode: build a content array with images + text
            user_content = []
            for img in self.images:
                mime_type = "image/jpeg"
                if img["filename"].endswith(".png"):
                    mime_type = "image/png"
                elif img["filename"].endswith(".gif"):
                    mime_type = "image/gif"
                elif img["filename"].endswith(".webp"):
                    mime_type = "image/webp"
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{img['data']}"}
                })
            user_content.append({"type": "text", "text": prompt})
            user_message = {"role": "user", "content": user_content}
        else:
            user_message = {"role": "user", "content": prompt}

        # Build system message
        system_parts = [
            "You are a helpful assistant. Answer questions directly and concisely when you already know the answer. "
            "Only use web_search for questions that require real-time or current information (e.g., weather, news, sports scores, stock prices, events). "
            "Do NOT use web_search for general knowledge questions, math, coding, opinions, or factual questions you can answer from your training data. "
            "Use only ONE web_search call if needed. Do NOT search multiple times for the same question. "
            "After getting a search result, use it to answer immediately. Do NOT search again with a different query for the same question."
        ]

        # Check for available documents and inject document context
        if self.document_store and self.document_store.documents:
            doc_list = "\n".join(
                f"- Document ID: '{doc_id}', Filename: {info['filename']}"
                for doc_id, info in self.document_store.documents.items()
            )
            system_parts.append(
                "You have access to uploaded documents. Users may ask questions about them. "
                "To read a document, use the 'read_document' tool with a document_id. "
                "You can also search for specific content using the 'section' parameter. "
                f"Available documents:\n{doc_list}"
            )
            system_msg = " ".join(system_parts)
            messages = [{"role": "system", "content": system_msg}, user_message]
        else:
            system_msg = " ".join(system_parts)
            messages = [{"role": "system", "content": system_msg}, user_message]
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

        # Limit non-coding questions to 1000 tokens
        if not _is_coding_question(prompt):
            payload["max_tokens"] = 1000

        # Include tools when tools are available (not just when documents exist)
        if self.skills.tools:
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
        import logging
        logger = logging.getLogger(__name__)
        
        tool_name = tool_call["function"]["name"]
        tool_args = json.loads(tool_call["function"]["arguments"])

        logger.info(f"[Tool Call] {tool_name}({tool_args})")

        # Execute the tool
        tool_result = self.skills.execute_tool(tool_name, tool_args)
        
        logger.debug(f"Tool result: {str(tool_result)[:200]}")

        # Return tool result message
        return {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": tool_name,
            "content": str(tool_result)
        }

    def _handle_model_response(self, response_json):
        """Helper method to extract message from model response"""
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Raw response JSON: {str(response_json)[:500]}")
        
        if "choices" in response_json:
            choice = response_json["choices"][0]
            message = choice["message"]
        else:
            message = response_json["message"]
        
        logger.debug(f"Extracted message: {str(message)[:300]}")
        return message

    def _call_model(self, stream=False, disable_tools=False):
        """Helper method to call the model with current messages"""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": self.messages,
            "stream": stream,
            "temperature": 0.5,
        }

        # Check if the original prompt is a coding question (first user message)
        is_coding = False
        uses_tools = bool(self.skills.tools) and not disable_tools  # Only use tools if not disabled
        
        for msg in self.messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    is_coding = _is_coding_question(content)
                elif isinstance(content, list):
                    # Vision mode: extract text from content array
                    for part in content:
                        if part.get("type") == "text":
                            is_coding = _is_coding_question(part.get("text", ""))
                            break
                break

        # Limit non-coding questions to prevent overly long responses
        # BUT: if tools are enabled, use much higher limit since model is doing research
        if not is_coding:
            if uses_tools:
                payload["max_tokens"] = 8000  # Research/tool-based queries need more room
            else:
                payload["max_tokens"] = 1500  # Quick answers are typically shorter

        # Add tool definitions if any tools are registered and not disabled
        if self.skills.tools and not disable_tools:
            payload["tools"] = self.skills.get_tool_definitions()
            payload["tool_choice"] = "auto"

        response = requests.post(url, json=payload, headers=CONTENT_TYPE_JSON)
        return response

    def chat_with_tools(self, prompt, stream=False, max_iterations=8):
        """
        Chat with the model with tool support (agent loop).
        The model can request to use tools, which are executed and fed back.

        :param prompt: The input prompt for the chat.
        :param stream: Whether to stream the response (default is False).
        :param max_iterations: Maximum number of iterations (prevents infinite loops).
        :return: The final response from the model.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if "###" in prompt:
            self.messages = []
            return None

        # Build messages with document context
        messages = self._build_messages(prompt)
        if messages is None:
            return None
        self.messages = messages[:4]  # Keep a bit more history for context

        # Agent loop
        last_model_content = ""
        tool_call_count = 0
        max_tool_calls = 3  # Max tool calls before forcing a final answer

        for iteration in range(max_iterations):
            try:
                logger.debug(f"Agent loop iteration {iteration + 1}/{max_iterations}, messages so far: {len(self.messages)}")
                
                # Disable tools if we've reached the max tool call limit
                disable_tools = tool_call_count >= max_tool_calls
                response = self._call_model(stream, disable_tools=disable_tools)

                if response.status_code != 200:
                    logger.error(f"Model returned status {response.status_code}: {response.text[:200]}")
                    response.raise_for_status()

                response_json = response.json()
                message = self._handle_model_response(response_json)
                last_model_content = message.get("content", "")
                
                logger.debug(f"Iteration {iteration + 1}: content present = {bool(last_model_content)}, tool_calls = {'tool_calls' in message}")
                
                if not last_model_content:
                    logger.warning(f"Empty content from model in iteration {iteration + 1}, message keys: {list(message.keys())}")
                
                self.messages.insert(0, message)

                # Check if model wants to call a tool
                if "tool_calls" in message and message["tool_calls"]:
                    # Process all tool calls
                    tool_call_count += 1
                    logger.info(f"Model requested {len(message['tool_calls'])} tool call(s), total: {tool_call_count}")
                    
                    for tool_call in message["tool_calls"]:
                        tool_result = self._process_tool_call(tool_call)
                        self.messages.insert(0, tool_result)
                    
                    # If too many tool calls, stop and force a final answer
                    if tool_call_count >= max_tool_calls:
                        logger.info(f"Max tool calls ({max_tool_calls}) reached, forcing final answer (no more tools)")
                        # Add a system hint to stop searching and answer
                        self.messages.insert(0, {
                            "role": "system",
                            "content": "You have made enough tool calls to gather sufficient information. Now provide a comprehensive final answer based on all the information you have gathered. Do not make any more tool calls."
                        })
                    continue

                # Model gave a final response (no tool calls)
                # But check if content is empty - that's a problem
                if not last_model_content:
                    logger.warning(f"Model has no content at iteration {iteration + 1}, checking if we should continue...")
                    # If we have tool calls in previous messages, model might still be thinking
                    # Only log as error if this happens multiple times
                    if tool_call_count > 0 and iteration < max_iterations - 1:
                        logger.debug("Model provided tool calls but no content, continuing agent loop")
                        continue
                
                logger.info(f"Final response received after {iteration + 1} iteration(s), content length: {len(last_model_content)}")
                return {
                    "message": {
                        "content": last_model_content
                    }
                }
            except requests.exceptions.HTTPError as err:
                logger.error(f"HTTP error in agent loop: {err}")
                if last_model_content:
                    return {"message": {"content": last_model_content}}
                return None
            except Exception as err:
                logger.error(f"Unexpected error in agent loop: {err}", exc_info=True)
                if last_model_content:
                    return {"message": {"content": last_model_content}}
                return None

        # If we hit max iterations, return the model's last content (not the tool result at position 0)
        logger.warning(f"Max iterations ({max_iterations}) reached, last_model_content length: {len(last_model_content)}")
        if last_model_content:
            return {"message": {"content": last_model_content}}
        
        # Fallback response
        fallback = "The model did not provide a complete response. Please try rephrasing your question or try again."
        logger.error(f"No model content available, returning fallback message")
        return {"message": {"content": fallback}}


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
