from flask import Flask, render_template, request
from conversation import OllamaChat

app = Flask(__name__, template_folder='templates')

chat_bot = OllamaChat()

# Define route for homepage
@app.route("/", methods=["GET", "POST"])
def home():
    response = ""
    if request.method == "POST":
        user_query = request.form.get("query")
        chat_response = chat_bot.chat(user_query)
        print("Chat Response:", chat_response['message']["content"])
        response = f"Response: '{chat_response}'"
    return render_template("base.html", response=response)


if __name__ == "__main__":
    app.run(debug=True)
