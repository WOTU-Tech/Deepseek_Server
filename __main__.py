from flask import Flask, render_template, request
from utils.conversation import OllamaChat
import yaml


class ChatBot:
    def __init__(self, model: str = "deepseek-r1:7b"):
        self.chat_bot = OllamaChat(model=model)
        self.app = Flask(self.__class__.__name__, template_folder="templates")
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route("/", methods=["GET", "POST"])
        def home():
            response_to_display = ""
            if request.method == "POST":
                user_query = request.form.get("query")
                chat_response = self.chat_bot.chat(user_query)
                if chat_response is None:
                    response_to_display = "Previous conversation history is cleared, lets start a new conversation!"
                # print("Chat Response:", chat_response['message']["content"])
                else:
                    response = f"{chat_response['message']['content']}"
                    response_to_display = response.split("</think>")[-1]
            return render_template("base.html", response=response_to_display)

    def run(self):
        self.app.run(debug=True, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    # Load the YAML file
    with open("utils/parameter.yml", "r") as file:
        model_parameter = yaml.safe_load(file)

    chat_bot = ChatBot(model=model_parameter["model"])
    chat_bot.run()
