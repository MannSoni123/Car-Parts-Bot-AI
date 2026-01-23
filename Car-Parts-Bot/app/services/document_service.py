
import os
import requests
import pdfplumber
import pandas as pd
import re
import io
import pypdfium2 as pdfium
from flask import current_app

def download_document(media_id: str, original_filename: str) -> str:
    """
    Download WhatsApp document to a temporary file.
    Returns the absolute path to the saved file.
    """
    token = current_app.config["META_ACCESS_TOKEN"]
    # 1. Get URL from Media ID
    url_req = requests.get(
        f"https://graph.facebook.com/v20.0/{media_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    url_req.raise_for_status()
    media_url = url_req.json().get("url")

    # 2. Download Content
    resp = requests.get(
        media_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    resp.raise_for_status()

    # 3. Save to /tmp or configured upload dir
    # Use original filename extension or default
    ext = os.path.splitext(original_filename)[1] or ".bin"
    file_path = f"/tmp/{media_id}{ext}"
    
    with open(file_path, "wb") as f:
        f.write(resp.content)
    
    return file_path


def extract_text_from_document(user_id: str, media_id: str, filename: str) -> str:
    """
    Extract text/content from a document (PDF/Excel) for the Unified Pipeline.
    Returns a string summarizing what was found.
    """
    try:
        file_path = download_document(media_id, filename)
        ext = os.path.splitext(filename)[1].lower()

        print(f"📄 Extracting document: {filename} ({ext})")

        extracted_text = ""
        if ext == ".pdf":
            extracted_text = extract_pdf_content(user_id, file_path)
        elif ext in [".xlsx", ".xls", ".csv"]:
            extracted_text = extract_excel_content(file_path, ext)
        else:
            extracted_text = "Unsupported file type."

        return f"[Document {filename} Content]:\n{extracted_text}"

    except Exception as e:
        print(f"❌ Document extraction error: {e}")
        return "Error reading document."
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

def extract_pdf_content(user_id: str, file_path: str) -> str:
    text_content = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            if len(pdf.pages) > 5:
                # Limit pages
                pass 
            for page in pdf.pages[:5]:
                text = page.extract_text()
                if text:
                    text_content += text + "\n"
    except Exception:
        pass
    
    # If text is empty or sparse, try OCR/Image conversion
    if len(text_content.strip()) < 10:
        return "Scanned PDF content (OCR needed but skipped for speed in V1)." 
    
    return text_content

def extract_excel_content(file_path: str, ext: str) -> str:
    try:
        if ext == ".csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        # Convert first few rows to string representation
        return df.to_string(index=False, max_rows=20)
    except Exception:
        return "Could not parse Excel content."
