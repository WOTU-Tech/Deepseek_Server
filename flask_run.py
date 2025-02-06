from flask import Flask, render_template, request
from conversation import OllamaChat


class ChatBot:
    def __init__(self):
        self.chat_bot = OllamaChat()
        self.app= Flask(self.__class__.__name__, template_folder='templates')
        self._setup_routes()


    def _setup_routes(self):
        @self.app.route("/", methods=["GET", "POST"])
        def home():
            response = ""
            if request.method == "POST":
                user_query = request.form.get("query")
                chat_response = self.chat_bot.chat(user_query)
                # print("Chat Response:", chat_response['message']["content"])
                response = f"'{chat_response['message']['content']}'"
            return render_template("base.html", response=response)

    def run(self):
        self.app.run(debug=True)


if __name__ == "__main__":
    chat_bot = ChatBot()
    chat_bot.run()
