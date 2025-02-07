import requests
import base64


class OllamaChat:
    def __init__(self, base_url="http://localhost:11434", model="deepseek-r1:7b"):
        """
        Initialize the OllamaChat API wrapper.

        :param base_url: The base URL of the Ollama API server.
        :param model: The model to use for chat (default is 'llama2').
        """
        self.base_url = base_url
        self.model = model
        self.messages = []
        self.previous_answer = None

    def chat(self, prompt, stream=False):
        """
        Send a chat prompt to the Ollama API and get the response.

        :param prompt: The input prompt for the chat.
        :param stream: Whether to stream the response (default is False).
        :return: The response from the Ollama API.
        """
        if "###" in prompt:
            self.messages = []  # reset message when key word is found
            self.previous_answer = None  # clear the previous answer
            return None
        if self.previous_answer is not None:
            new_prompt = "I know" + self.previous_answer + ", new question:" + prompt
        else:
            new_prompt = prompt
        self.messages.insert(0, {"role": "user", "content": new_prompt})
        self.messages = self.messages[:2]  # only keep the last memory
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": self.messages,
            "stream": stream,
            "options": {
                "temperature": 0.5,  # Controls randomness (lower values make the output more deterministic).
                # "stop": ["\n", "###"],
            },
        }
        headers = {"Content-Type": "application/json"}

        response = requests.post(url, json=payload, headers=headers)

        try:
            if response.status_code == 200:
                self.previous_answer = response.json()["message"]["content"].split(
                    "</think>"
                )[-1]
                return response.json()
            else:
                response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            print(f"Encounter error: {err}, please clear the cache and try again.")
            pass

    def generate(self, prompt, stream=False):
        """
        Generate a response from the Ollama API.

        :param prompt: The input prompt for generation.
        :param stream: Whether to stream the response (default is False).
        :return: The response from the Ollama API.
        """
        url = f"{self.base_url}/api/chat"
        payload = {"model": self.model, "prompt": prompt, "stream": stream}
        headers = {"Content-Type": "application/json"}

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
        print("Chat Response:", chat_response["message"]["content"])
