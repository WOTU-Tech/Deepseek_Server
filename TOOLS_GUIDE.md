# Tool/Skill System Guide

## Overview

The chatbot now supports a **tool/skill system** that allows the model to use external tools to enhance capabilities. The system uses an **agent loop** pattern where:

1. User sends a message to the model
2. Model determines if it needs a tool to answer
3. If yes, model requests the tool with specific arguments
4. Tool is executed and result is sent back to the model
5. Model uses the result to form a final answer

## Available Tools

### 1. Web Search
**Name:** `web_search`

Search the internet using DuckDuckGo API (no API key required).

**Parameters:**
- `query` (string, required): What to search for
- `max_results` (integer, optional): Number of results to return (default: 5)

**Example Usage:**
```python
response = chat_bot.chat_with_tools("What are the latest developments in AI?")
# Model will automatically use web_search to find current information
```

### 2. Calculator
**Name:** `calculator`

Perform mathematical calculations safely.

**Parameters:**
- `expression` (string, required): Mathematical expression (e.g., "2 + 2 * 3")

**Example Usage:**
```python
response = chat_bot.chat_with_tools("What's 123 * 456 + 789?")
# Model will use calculator for precise math
```

## API Endpoints

### Standard Chat (Without Tools)
```
POST /v1/api/chat
Content-Type: application/json

{
  "message": "Hello, how are you?"
}

Response:
{
  "message": "I'm doing well, thank you for asking!",
  "role": "assistant"
}
```

### Chat with Tools (Agent Loop)
```
POST /v1/api/chat/with-tools
Content-Type: application/json

{
  "message": "What's the current Bitcoin price? And what's 2024 divided by 4?"
}

Response:
{
  "message": "Based on my web search... and calculating 2024 / 4 = 506...",
  "role": "assistant"
}
```

The model will:
1. Use `web_search` to look up Bitcoin price
2. Use `calculator` for the division
3. Combine results into a complete answer

### Get Available Tools
```
GET /v1/api/tools

Response:
{
  "tools": ["web_search", "calculator"],
  "count": 2
}
```

## Python Usage Examples

### Basic Chat
```python
from utils.conversation import OllamaChat

chat_bot = OllamaChat()

# Standard chat without tools
response = chat_bot.chat("Hello!")
print(response['message']['content'])
```

### Chat with Tools
```python
from utils.conversation import OllamaChat

chat_bot = OllamaChat()

# Chat with tool support - model can use tools automatically
response = chat_bot.chat_with_tools("What's the weather in New York?")
print(response['message']['content'])
```

### Register Custom Tools
```python
from utils.conversation import OllamaChat, SkillManager

chat_bot = OllamaChat()

# Create a custom tool
class WeatherTool:
    @staticmethod
    def get_weather(city: str) -> str:
        # Your weather implementation here
        return f"Weather in {city}: 72°F, Sunny"
    
    @staticmethod
    def get_definition():
        return {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name"}
                    },
                    "required": ["city"]
                }
            }
        }

# Register the tool
chat_bot.skills.register_tool("get_weather", WeatherTool)

# Now use it
response = chat_bot.chat_with_tools("What's the weather in New York?")
```

## How to Add Your Own Tools

1. Create a tool class in `utils/tools.py`:

```python
class MyCustomTool:
    @staticmethod
    def my_function(param1: str, param2: int) -> str:
        """Your tool implementation"""
        return f"Result: {param1} {param2}"
    
    @staticmethod
    def get_definition():
        """Required: Define tool for the model"""
        return {
            "type": "function",
            "function": {
                "name": "my_custom_tool",
                "description": "Description of what this tool does",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param1": {
                            "type": "string",
                            "description": "First parameter"
                        },
                        "param2": {
                            "type": "integer",
                            "description": "Second parameter"
                        }
                    },
                    "required": ["param1", "param2"]
                }
            }
        }
```

2. Add it to the `TOOLS` registry in `tools.py`:

```python
TOOLS = {
    "web_search": WebSearchTool,
    "calculator": CalculatorTool,
    "my_custom_tool": MyCustomTool  # Add your tool here
}
```

3. Update the `SkillManager.execute_tool` method to handle your tool:

```python
def execute_tool(self, tool_name: str, args: dict):
    """..."""
    # ... existing code ...
    elif tool_name == "my_custom_tool":
        return tool_class.my_function(**args)
```

## Configuration

The agent loop has a maximum of 10 iterations to prevent infinite loops. To change this:

```python
response = chat_bot.chat_with_tools(
    prompt="Your question",
    stream=False,
    max_iterations=5  # Change max iterations
)
```

## Limitations

- Web search requires internet connection
- Calculator only supports safe math operations (no code execution)
- Tools have timeout limits
- Model must support function calling (check your model capabilities)

## Debugging

To see which tools are being called:

```python
response = chat_bot.chat_with_tools("Search for latest AI news")
# Check console for: [Tool Call] web_search({'query': 'latest AI news', 'max_results': 5})
```

