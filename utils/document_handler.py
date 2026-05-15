"""
Document handling utilities for parsing various file formats
"""
import os
from pathlib import Path
from typing import Dict, List, Tuple


class DocumentParser:
    """Parse different document formats (TXT, PDF, DOCX, MD)"""

    SUPPORTED_FORMATS = {'.txt', '.pdf', '.docx', '.md'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    @staticmethod
    def parse_text_file(file_path: str) -> str:
        """Parse plain text files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading text file: {str(e)}"

    @staticmethod
    def parse_markdown_file(file_path: str) -> str:
        """Parse markdown files (same as text)"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading markdown file: {str(e)}"

    @staticmethod
    def parse_pdf_file(file_path: str) -> str:
        """Parse PDF files"""
        try:
            import PyPDF2
            content = []
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text.strip():
                        content.append(f"--- Page {page_num + 1} ---\n{text}")
            return "\n".join(content)
        except ImportError:
            return "Error: PyPDF2 not installed. Install with: pip install PyPDF2"
        except Exception as e:
            return f"Error reading PDF file: {str(e)}"

    @staticmethod
    def parse_docx_file(file_path: str) -> str:
        """Parse DOCX files"""
        try:
            from docx import Document
            doc = Document(file_path)
            content = []
            for para in doc.paragraphs:
                if para.text.strip():
                    content.append(para.text)
            return "\n".join(content)
        except ImportError:
            return "Error: python-docx not installed. Install with: pip install python-docx"
        except Exception as e:
            return f"Error reading DOCX file: {str(e)}"

    @staticmethod
    def parse_file(file_path: str) -> Tuple[bool, str]:
        """
        Parse a file based on its extension

        :param file_path: Path to the file
        :return: Tuple of (success: bool, content: str)
        """
        file_ext = Path(file_path).suffix.lower()

        if file_ext not in DocumentParser.SUPPORTED_FORMATS:
            return False, f"Unsupported file format: {file_ext}. Supported: {DocumentParser.SUPPORTED_FORMATS}"

        # Check file size
        try:
            file_size = os.path.getsize(file_path)
            if file_size > DocumentParser.MAX_FILE_SIZE:
                return False, f"File too large: {file_size / 1024 / 1024:.1f}MB (max: 10MB)"
        except Exception as e:
            return False, f"Error checking file size: {str(e)}"

        # Parse based on format
        if file_ext == '.pdf':
            content = DocumentParser.parse_pdf_file(file_path)
        elif file_ext == '.docx':
            content = DocumentParser.parse_docx_file(file_path)
        elif file_ext == '.md':
            content = DocumentParser.parse_markdown_file(file_path)
        else:  # .txt
            content = DocumentParser.parse_text_file(file_path)

        # Check if there was an error in parsing
        if content.startswith("Error"):
            return False, content

        if not content.strip():
            return False, "File is empty or no text could be extracted"

        return True, content

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> List[str]:
        """
        Split text into overlapping chunks for better context

        :param text: Text to chunk
        :param chunk_size: Size of each chunk in characters
        :param overlap: Overlap between chunks
        :return: List of text chunks
        """
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap

        return chunks


class DocumentStore:
    """Store and manage uploaded documents in session"""

    def __init__(self):
        self.documents: Dict[str, Dict] = {}

    def add_document(self, doc_id: str, filename: str, content: str, file_type: str):
        """Add a document to the store"""
        chunks = DocumentParser.chunk_text(content)
        self.documents[doc_id] = {
            "filename": filename,
            "file_type": file_type,
            "content": content,
            "chunks": chunks,
            "chunk_count": len(chunks)
        }

    def get_document(self, doc_id: str) -> dict:
        """Get a document by ID"""
        return self.documents.get(doc_id)

    def list_documents(self) -> List[Dict]:
        """List all documents in store"""
        return [
            {
                "id": doc_id,
                "filename": doc["filename"],
                "file_type": doc["file_type"],
                "chunk_count": doc["chunk_count"]
            }
            for doc_id, doc in self.documents.items()
        ]

    def search_document(self, doc_id: str, query: str) -> List[str]:
        """Search for relevant chunks in a document"""
        doc = self.get_document(doc_id)
        if not doc:
            return []

        # Simple keyword search - return chunks containing the query
        query_lower = query.lower()
        relevant_chunks = [
            chunk for chunk in doc["chunks"]
            if query_lower in chunk.lower()
        ]

        return relevant_chunks[:3]  # Return top 3 relevant chunks

    def delete_document(self, doc_id: str):
        """Delete a document from store"""
        if doc_id in self.documents:
            del self.documents[doc_id]

    def clear(self):
        """Clear all documents"""
        self.documents.clear()

