from flask import Flask, render_template, request, jsonify
from utils.conversation import OllamaChat
from utils.document_handler import DocumentParser
from werkzeug.utils import secure_filename
import yaml
import markdown
import os
import uuid

CACHE_CLEAR_MESSAGE = "Previous conversation history is cleared, lets start a new conversation!"
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'md'}

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


class ChatBot:
    def __init__(self, model: str = "Qwen3.6-35B-A3B-UD-Q4_K_M"):
        self.chat_bot = OllamaChat(model=model)
        self.app = Flask(self.__class__.__name__, template_folder="templates")
        self.app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size
        self._setup_routes()
    
    @staticmethod
    def allowed_file(filename: str) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    def _setup_routes(self):
        @self.app.route("/", methods=["GET", "POST"])
        def home():
            response_to_display = ""
            if request.method == "POST":
                user_query = request.form.get("query")
                use_tools = request.form.get("use_tools") == "on"

                # Call appropriate chat method based on checkbox
                if use_tools:
                    chat_response = self.chat_bot.chat_with_tools(user_query)
                else:
                    chat_response = self.chat_bot.chat(user_query)

                if chat_response is None:
                    response_to_display = CACHE_CLEAR_MESSAGE
                # print("Chat Response:", chat_response['message']["content"])
                else:
                    raw_response = f"{chat_response['message']['content']}"
                    markdown_response = markdown.markdown(
                        raw_response, extensions=["fenced_code"]
                    )  # handle markdown text
                    markdown_response = markdown_response.replace(
                        "```", ""
                    )  # handle math symbols
                    response_to_display = markdown_response.split("</think>")[-1]
            return render_template("base.html", response=response_to_display)

        @self.app.route("/v1/api/chat", methods=["POST"])
        def api_chat():
            """Legacy API endpoint - without tool support"""
            try:
                data = request.get_json()
                if not data or "message" not in data:
                    return jsonify({"error": "Missing 'message' in request body"}), 400

                user_query = data.get("message")
                chat_response = self.chat_bot.chat(user_query)

                if chat_response is None:
                    return jsonify({
                        "message": CACHE_CLEAR_MESSAGE,
                        "role": "assistant"
                    }), 200

                response_content = chat_response['message']['content']
                return jsonify({
                    "message": response_content,
                    "role": "assistant"
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/v1/api/chat/with-tools", methods=["POST"])
        def api_chat_with_tools():
            """API endpoint with tool/skill support (agent loop)"""
            try:
                data = request.get_json()
                if not data or "message" not in data:
                    return jsonify({"error": "Missing 'message' in request body"}), 400

                user_query = data.get("message")
                chat_response = self.chat_bot.chat_with_tools(user_query)

                if chat_response is None:
                    return jsonify({
                        "message": CACHE_CLEAR_MESSAGE,
                        "role": "assistant"
                    }), 200

                response_content = chat_response['message']['content']
                return jsonify({
                    "message": response_content,
                    "role": "assistant"
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/v1/api/tools", methods=["GET"])
        def api_tools():
            """Get list of available tools/skills"""
            tools_list = list(self.chat_bot.skills.tools.keys())
            return jsonify({
                "tools": tools_list,
                "count": len(tools_list)
            }), 200

        @self.app.route("/v1/api/documents/upload", methods=["POST"])
        def upload_document():
            """Upload a document for the chatbot to read"""
            try:
                if 'file' not in request.files:
                    return jsonify({"error": "No file provided"}), 400
                
                file = request.files['file']
                
                if file.filename == '':
                    return jsonify({"error": "No file selected"}), 400
                
                if not self.allowed_file(file.filename):
                    return jsonify({
                        "error": f"File type not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}"
                    }), 400
                
                # Generate unique ID for document
                doc_id = f"doc_{uuid.uuid4().hex[:8]}"
                filename = secure_filename(file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, f"{doc_id}_{filename}")
                
                # Save file
                file.save(filepath)
                
                # Parse document
                success, content = DocumentParser.parse_file(filepath)
                
                if not success:
                    os.remove(filepath)
                    return jsonify({"error": content}), 400
                
                # Store in document store
                file_type = filename.rsplit('.', 1)[1].lower()
                self.chat_bot.document_store.add_document(doc_id, filename, content, file_type)
                
                return jsonify({
                    "success": True,
                    "document_id": doc_id,
                    "filename": filename,
                    "size": len(content),
                    "message": f"Document uploaded successfully. Use document ID '{doc_id}' in your questions."
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/v1/api/documents/list", methods=["GET"])
        def list_documents():
            """List all uploaded documents"""
            documents = self.chat_bot.document_store.list_documents()
            return jsonify({
                "documents": documents,
                "count": len(documents)
            }), 200

        @self.app.route("/v1/api/documents/<doc_id>/delete", methods=["DELETE"])
        def delete_document(doc_id):
            """Delete a document"""
            try:
                self.chat_bot.document_store.delete_document(doc_id)
                return jsonify({
                    "success": True,
                    "message": f"Document '{doc_id}' deleted"
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/v1/api/documents/clear", methods=["POST"])
        def clear_documents():
            """Clear all documents"""
            try:
                self.chat_bot.document_store.clear()
                return jsonify({
                    "success": True,
                    "message": "All documents cleared"
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500

    def run(self):
        self.app.run(debug=True, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    # Load the YAML file
    with open("utils/parameter.yml", "r") as file:
        model_parameter = yaml.safe_load(file)

    chat_bot = ChatBot(model=model_parameter["model"])
    chat_bot.run()
