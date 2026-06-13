import hashlib
import re

from docx import Document
from PyPDF2 import PdfReader


EMAIL_PATTERN = (
    r'[a-zA-Z0-9._%+-]+@'
    r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
)

PHONE_PATTERN = (
    r'\b(?:\+?\d{1,3}[-.\s]?)?'
    r'\(?\d{3}\)?[-.\s]?'
    r'\d{3}[-.\s]?\d{4}\b'
)


class ResumeParser:

    @staticmethod
    def generate_hash(file_obj):

        file_obj.seek(0)

        digest = hashlib.sha256(
            file_obj.read()
        ).hexdigest()

        file_obj.seek(0)

        return digest

    @staticmethod
    def scrub_pii(text):

        text = re.sub(
            EMAIL_PATTERN,
            "[EMAIL MASKED]",
            text
        )

        text = re.sub(
            PHONE_PATTERN,
            "[PHONE MASKED]",
            text
        )

        return text

    @staticmethod
    def extract_pdf(file_obj):

        reader = PdfReader(file_obj)

        pages = []

        for page in reader.pages:

            txt = page.extract_text()

            if txt:
                pages.append(txt)

        return "\n".join(pages)

    @staticmethod
    def extract_docx(file_obj):

        doc = Document(file_obj)

        paragraphs = []

        for para in doc.paragraphs:

            if para.text.strip():

                paragraphs.append(
                    para.text.strip()
                )

        return "\n".join(paragraphs)

    @classmethod
    def extract_text(
        cls,
        file_obj,
        filename
    ):

        filename = filename.lower()

        if filename.endswith(".pdf"):

            return cls.extract_pdf(
                file_obj
            )

        elif filename.endswith(".docx"):

            return cls.extract_docx(
                file_obj
            )

        raise ValueError(
            f"Unsupported file type: {filename}"
        )

    @classmethod
    def process_resume(
        cls,
        file_obj,
        filename
    ):

        raw_text = cls.extract_text(
            file_obj,
            filename
        )

        clean_text = cls.scrub_pii(
            raw_text
        )

        file_hash = cls.generate_hash(
            file_obj
        )

        return {
            "file_name": filename,
            "file_hash": file_hash,
            "resume_text": clean_text
        }