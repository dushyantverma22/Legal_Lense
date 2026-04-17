# src/ingestion/loader.py
import fitz
import base64
from openai import OpenAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from config.settings import get_settings

settings = get_settings()


def _is_text_empty(docs: list[Document]) -> bool:
    """Your original helper — unchanged."""
    total_text = " ".join([doc.page_content.strip() for doc in docs])
    return len(total_text) < 50


def _ocr_with_vision(pdf_path: str) -> list[Document]:
    """
    Your original OCR fallback — refactored so OpenAI client
    is created locally (stateless, safe for concurrent workers).
    """
    client = OpenAI(api_key=settings.openai_api_key)
    doc = fitz.open(pdf_path)
    ocr_texts = []

    for page in doc:
        pix = page.get_pixmap()
        img_bytes = pix.tobytes("png")
        img_base64 = base64.b64encode(img_bytes).decode()

        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all text clearly. Preserve sections and clauses."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                ]
            }],
            max_tokens=settings.llm_max_tokens
        )
        ocr_texts.append(response.choices[0].message.content)

    return [Document(page_content=t) for t in ocr_texts]


def load_pdf_smart(pdf_path: str) -> list[Document]:
    """
    Stateless PDF loader.
    
    PRODUCTION CHANGE from your notebook:
    - No global state, safe for 100 concurrent Lambda invocations
    - Logs which path was taken (text vs OCR) for CloudWatch metrics
    """
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()

    if _is_text_empty(docs):
        print(f"[loader] OCR fallback triggered for: {pdf_path}")
        docs = _ocr_with_vision(pdf_path)
    else:
        print(f"[loader] Text extraction succeeded for: {pdf_path}")

    return docs