"""Document loading and processing for knowledge base."""

from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from typing import List


def load_documents(data_dir: str = "data") -> List[Document]:
    """
    Load all PDF documents from the data directory.

    Args:
        data_dir: Directory containing PDF files

    Returns:
        List of Document objects
    """
    documents = []
    data_path = Path(data_dir)

    if not data_path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_path}")

    # Find all PDF files
    pdf_files = list(data_path.glob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {data_path}")

    print(f"Found {len(pdf_files)} PDF files. Loading...")

    for pdf_file in pdf_files:
        print(f"  Loading: {pdf_file.name}...")
        loader = PyPDFLoader(str(pdf_file))
        docs = loader.load()

        # Add source metadata
        for doc in docs:
            doc.metadata["source_file"] = pdf_file.name

        documents.extend(docs)

    print(f"Total documents loaded: {len(documents)}")
    return documents


def chunk_documents(
    documents: List[Document],
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[Document]:
    """
    Split documents into smaller chunks for better retrieval.

    Args:
        documents: List of Document objects
        chunk_size: Size of each chunk
        chunk_overlap: Overlap between chunks

    Returns:
        List of chunked Document objects
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )

    chunked_documents = text_splitter.split_documents(documents)
    print(f"Documents chunked into {len(chunked_documents)} chunks")

    return chunked_documents


def prepare_knowledge_base(
    data_dir: str = "data",
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[Document]:
    """
    Load and prepare documents for knowledge base.

    Args:
        data_dir: Directory containing PDF files
        chunk_size: Size of chunks for splitting
        chunk_overlap: Overlap between chunks

    Returns:
        List of processed Document objects
    """
    documents = load_documents(data_dir)
    chunked_documents = chunk_documents(documents, chunk_size, chunk_overlap)
    return chunked_documents
