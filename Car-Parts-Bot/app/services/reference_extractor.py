# app/services/reference_extractor.py

import os
import fitz  # PyMuPDF
from docx import Document


def extract_text_from_file(file_path: str) -> str:
    """
    Extract readable text from reference files.
    Supported formats:
    - .pdf
    - .txt
    - .docx

    Called ONLY at upload time.
    Extracted text is cached in DB.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError("Reference file not found")

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _extract_text_from_pdf(file_path)

    if ext == ".txt":
        return _extract_text_from_txt(file_path)

    if ext == ".docx":
        return _extract_text_from_docx(file_path)

    raise ValueError(f"Unsupported reference file type: {ext}")


# ---------------- HELPERS ---------------- #

def _extract_text_from_pdf(path: str) -> str:
    text_chunks = []
    doc = fitz.open(path)

    for i, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        if text:
            text_chunks.append(f"[Page {i}]\n{text}")

    doc.close()

    if not text_chunks:
        raise ValueError("No readable text found in PDF")

    return "\n\n".join(text_chunks)


def _extract_text_from_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read().strip()

    if not text:
        raise ValueError("TXT file is empty")

    return text


def _extract_text_from_docx(path: str) -> str:
    doc = Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    if not paragraphs:
        raise ValueError("DOCX contains no readable text")

    return "\n".join(paragraphs)
