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
    def sanitize_unicode(text):
        """
        Strips lone Unicode surrogates and any other characters that
        can't round-trip through UTF-8. These commonly come from
        PyPDF2.extract_text() choking on broken icon-font / cmap
        glyphs in designed resume PDFs (phone/email/LinkedIn icons).

        Critical: pandas >=3.0 infers PyArrow-backed string columns
        by default, which strictly validates UTF-8 on DataFrame
        construction. Pre-3.0 pandas silently tolerated this garbage
        in object-dtype arrays; 3.0 raises UnicodeEncodeError on it.
        Sanitizing at extraction time stops it at the source.
        """
        if not isinstance(text, str):
            return text

        # Remove lone surrogates (U+D800-U+DFFF) directly — these are
        # valid in a Python str but cannot be encoded to UTF-8 at all.
        text = re.sub(r'[\ud800-\udfff]', '', text)

        # Belt-and-braces: drop anything else that fails UTF-8 encoding.
        text = text.encode('utf-8', errors='ignore').decode('utf-8')

        return text

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

            return cls.sanitize_unicode(
                cls.extract_pdf(file_obj)
            )

        elif filename.endswith(".docx"):

            return cls.sanitize_unicode(
                cls.extract_docx(file_obj)
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