import requests
import base64


def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        img = image_file.read()
        return img

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

class OllamaChat:
    def __init__(self, base_url="http://localhost:11434", model="deepseek-r1:7b"):
        """
        Initialize the OllamaChat API wrapper.

        :param base_url: The base URL of the Ollama API server.
        :param model: The model to use for chat (default is 'llama2').
        """
        self.base_url = base_url
        self.model = model

    def chat(self, prompt, stream=False):
        """
        Send a chat prompt to the Ollama API and get the response.

        :param prompt: The input prompt for the chat.
        :param stream: Whether to stream the response (default is False).
        :return: The response from the Ollama API.
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream
        }
        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()


    def generate(self, prompt, stream=False):
        """
        Generate a response from the Ollama API.

        :param prompt: The input prompt for generation.
        :param stream: Whether to stream the response (default is False).
        :return: The response from the Ollama API.
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream
        }
        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)

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
        print("Chat Response:", chat_response['message']["content"])
