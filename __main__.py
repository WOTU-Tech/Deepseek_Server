from typing import Union, Tuple
from flask import Flask, render_template, request, jsonify
from utils.conversation import OllamaChat
from utils.document_handler import DocumentParser
from utils.config import AppConfig
from utils.errors import register_error_handlers
from routes.api_chat import api_chat_bp
from werkzeug.utils import secure_filename
import markdown
import os
import uuid
import base64
import logging

CACHE_CLEAR_MESSAGE = "Previous conversation history is cleared, let's start a new conversation!"
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx", "md"}
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}


class ChatBot:
    def __init__(self, config: AppConfig):
        self.config = config
        self.chat_bot = OllamaChat(base_url=config.ollama_base_url, model=config.model)
        self.app = Flask(self.__class__.__name__, template_folder="templates")
        self.app.config["MAX_CONTENT_LENGTH"] = config.max_content_length
        self.logger = logging.getLogger(__name__)
        register_error_handlers(self.app)
        self.app.register_blueprint(api_chat_bp)
        self._setup_routes()

    @staticmethod
    def allowed_file(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

    @staticmethod
    def allowed_image(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

    def _process_chat_response(self, chat_response):
        """Process and format chat response for display."""
        if chat_response is None:
            return CACHE_CLEAR_MESSAGE, "Cache cleared"
        
        raw_response = chat_response['message']['content']
        raw_response = self._clean_response(raw_response)
        
        if not raw_response:
            return "Model returned empty response. Try again.", "Empty response"
        
        markdown_response = markdown.markdown(raw_response, extensions=["fenced_code"])
        return markdown_response.strip(), f"Response generated ({len(markdown_response)} chars)"

    @staticmethod
    def _clean_response(raw_response: str) -> str:
        """Remove tool tags and thinking markers from response."""
        import re
        raw_response = re.sub(r'<\|.*?\|>', '', raw_response)
        raw_response = raw_response.replace('<|im_end|>', '').replace('<|endoftext|>', '')
        if raw_response.startswith('</think>'):
            raw_response = raw_response[len('</think>'):].lstrip()
        return raw_response.strip()

    def _validate_upload(self, file) -> Tuple[bool, str]:
        """Validate uploaded file. Returns (is_valid, error_message)."""
        if not file:
            return False, "No file provided"
        if file.filename == "":
            return False, "No file selected"
        return True, ""

    def _handle_document_upload(self, file) -> Tuple[bool, Union[dict, str]]:
        """Handle document upload validation and storage. Returns (success, result)."""
        is_valid, error = self._validate_upload(file)
        if not is_valid:
            return False, error
        
        if not self.allowed_file(file.filename):
            return False, f"File type not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}"
        
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, f"{doc_id}_{filename}")
        
        file.save(filepath)
        success, content = DocumentParser.parse_file(filepath)
        
        if not success:
            os.remove(filepath)
            return False, content
        
        file_type = filename.rsplit(".", 1)[1].lower()
        self.chat_bot.document_store.add_document(doc_id, filename, content, file_type)
        
        return True, {
            "document_id": doc_id,
            "filename": filename,
            "size": len(content),
            "message": f"Document uploaded successfully. Use document ID '{doc_id}' in your questions."
        }

    def _handle_image_upload(self, file) -> Tuple[bool, Union[dict, str]]:
        """Handle image upload validation and storage. Returns (success, result)."""
        is_valid, error = self._validate_upload(file)
        if not is_valid:
            return False, error
        
        if not self.allowed_image(file.filename):
            return False, f"Image type not allowed. Supported: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        
        file_content = file.read()
        base64_image = base64.b64encode(file_content).decode("utf-8")
        filename = secure_filename(file.filename)
        image_info = self.chat_bot.add_image(base64_image, filename)
        
        return True, {
            "image_id": image_info["id"],
            "filename": image_info["filename"],
            "message": "Image uploaded successfully. Ask questions about your images."
        }

    def _home_post(self):
        """Handle POST request to home page."""
        try:
            user_query = request.form.get("query")
            use_tools = request.form.get("use_tools") == "on"
            self.logger.info(f"Processing query: {user_query[:50]}... (tools={'enabled' if use_tools else 'disabled'})")

            chat_response = self.chat_bot.chat_with_tools(user_query) if use_tools else self.chat_bot.chat(user_query)
            response_to_display, log_msg = self._process_chat_response(chat_response)
            self.logger.info(log_msg)
            return response_to_display
        except Exception as e:
            self.logger.error(f"Error in home() route: {str(e)}", exc_info=True)
            return f"Error processing request: {str(e)}"

    def _setup_routes(self):
        @self.app.route("/", methods=["GET", "POST"])
        def home():
            response = self._home_post() if request.method == "POST" else ""
            return render_template("base.html", response=response)

        @self.app.route("/v1/api/tools", methods=["GET"])
        def api_tools():
            tools_list = list(self.chat_bot.skills.tools.keys())
            return jsonify({"tools": tools_list, "count": len(tools_list)}), 200

        @self.app.route("/v1/api/documents/upload", methods=["POST"])
        def upload_document():
            return self._upload_document_handler()

        @self.app.route("/v1/api/documents/list", methods=["GET"])
        def list_documents():
            documents = self.chat_bot.document_store.list_documents()
            return jsonify({"documents": documents, "count": len(documents)}), 200

        @self.app.route("/v1/api/documents/<doc_id>/delete", methods=["DELETE"])
        def delete_document(doc_id):
            try:
                self.chat_bot.document_store.delete_document(doc_id)
                return jsonify_success(message=f"Document '{doc_id}' deleted")
            except Exception as e:
                return jsonify_error(str(e), 500)

        @self.app.route("/v1/api/documents/clear", methods=["POST"])
        def clear_documents():
            try:
                self.chat_bot.document_store.clear()
                return jsonify_success(message="All documents cleared")
            except Exception as e:
                return jsonify_error(str(e), 500)

        @self.app.route("/v1/api/images/upload", methods=["POST"])
        def upload_image():
            return self._upload_image_handler()

        @self.app.route("/v1/api/images/list", methods=["GET"])
        def list_images():
            images = self.chat_bot.list_images()
            return jsonify({"images": images, "count": len(images)}), 200

        @self.app.route("/v1/api/images/<image_id>/delete", methods=["DELETE"])
        def delete_image(image_id):
            try:
                self.chat_bot.delete_image(image_id)
                return jsonify_success(message=f"Image '{image_id}' deleted")
            except Exception as e:
                return jsonify_error(str(e), 500)

        @self.app.route("/v1/api/images/clear", methods=["POST"])
        def clear_images():
            try:
                self.chat_bot.clear_images()
                return jsonify_success(message="All images cleared")
            except Exception as e:
                return jsonify_error(str(e), 500)

    def _upload_document_handler(self):
        """Handle document upload request."""
        try:
            file = request.files.get("file")
            success, result = self._handle_document_upload(file)
            if not success:
                return jsonify_error(str(result), 400)
            return jsonify_success(**result)
        except Exception as e:
            return jsonify_error(str(e), 500)

    def _upload_image_handler(self):
        """Handle image upload request."""
        try:
            file = request.files.get("file")
            success, result = self._handle_image_upload(file)
            if not success:
                return jsonify_error(str(result), 400)
            return jsonify_success(**result)
        except Exception as e:
            return jsonify_error(str(e), 500)


    def run(self):
        self.app.run(
            debug=True,
            host=self.config.flask_host,
            port=self.config.flask_port,
        )


def jsonify_error(message: str, status: int = 400):
    resp = jsonify({"error": message})
    resp.status_code = status
    return resp


def jsonify_success(message: str = "", **kwargs):
    data = {"success": True, "message": message}
    data.update(kwargs)
    return jsonify(data), 200


def setup_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


if __name__ == "__main__":
    config = AppConfig.from_env_and_file()
    setup_logging(config.log_level)
    chat_bot = ChatBot(config)
    chat_bot.run()
