# src/ingestion/chunker.py
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from config.settings import get_settings

settings = get_settings()


def chunk_documents(docs: list[Document]) -> list[Document]:
    """
    Your original chunking — now reads chunk_size and overlap
    from settings so staging/prod can use different values.
    
    Your notebook values: chunk_size=700, chunk_overlap=120
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
        is_separator_regex=False,
    )
    chunks = splitter.split_documents(docs)
    print(f"[chunker] {len(docs)} docs → {len(chunks)} chunks")
    return chunks