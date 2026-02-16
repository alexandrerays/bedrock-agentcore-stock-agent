"""Vector store and retrieval for knowledge base."""

import os
import pickle
from pathlib import Path
from typing import Any, List, Optional

from langchain_core.documents import Document
from langchain_community.embeddings import BedrockEmbeddings, HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from .loader import prepare_knowledge_base


class KnowledgeBaseRetriever:
    """Manages vector store and document retrieval."""

    def __init__(
        self,
        vector_store_path: str = ".vector_store",
        use_bedrock: bool = False,
        region: str = "us-east-1"
    ):
        """
        Initialize knowledge base retriever.

        Args:
            vector_store_path: Path to store/load vector store
            use_bedrock: Whether to use Bedrock embeddings (requires AWS)
            region: AWS region for Bedrock
        """
        self.vector_store_path = Path(vector_store_path)
        self.use_bedrock = use_bedrock
        self.region = region
        self.vector_store: Optional[FAISS] = None
        self._init_embeddings()

    def _init_embeddings(self) -> Any:
        """Initialize embeddings model."""
        if self.use_bedrock:
            try:
                self.embeddings = BedrockEmbeddings(
                    region_name=self.region,
                    model_id="amazon.titan-embed-text-v1"
                )
                print("Using Bedrock embeddings")
            except Exception as e:
                print(f"Bedrock embeddings failed: {e}, falling back to sentence-transformers")
                self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        else:
            self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            print("Using sentence-transformer embeddings (local)")

    def build_vector_store(self, data_dir: str = "data", force_rebuild: bool = False) -> FAISS:
        """
        Build or load vector store from documents.

        Args:
            data_dir: Directory containing PDF files
            force_rebuild: Force rebuild even if vector store exists

        Returns:
            FAISS vector store
        """
        # Try to load existing vector store
        if not force_rebuild and self.vector_store_path.exists():
            print(f"Loading existing vector store from {self.vector_store_path}...")
            try:
                self.vector_store = FAISS.load_local(
                    str(self.vector_store_path),
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                print("Vector store loaded successfully")
                return self.vector_store
            except Exception as e:
                print(f"Failed to load vector store: {e}. Rebuilding...")

        # Build new vector store
        print("Building new vector store...")
        documents = prepare_knowledge_base(data_dir)

        if not documents:
            raise ValueError("No documents to index")

        print(f"Creating embeddings for {len(documents)} documents...")
        self.vector_store = FAISS.from_documents(documents, self.embeddings)

        # Save vector store
        self.vector_store_path.mkdir(parents=True, exist_ok=True)
        print(f"Saving vector store to {self.vector_store_path}...")
        self.vector_store.save_local(str(self.vector_store_path))

        print("Vector store created and saved")
        return self.vector_store

    def retrieve_documents(
        self,
        query: str,
        k: int = 5,
        score_threshold: float = 0.0
    ) -> List[Document]:
        """
        Retrieve documents relevant to query.

        Args:
            query: Search query
            k: Number of documents to retrieve
            score_threshold: Minimum similarity score

        Returns:
            List of relevant Document objects
        """
        if self.vector_store is None:
            raise ValueError("Vector store not initialized. Call build_vector_store first.")

        # Use similarity_search_with_score to get relevance scores
        results = self.vector_store.similarity_search_with_score(query, k=k)

        # Filter by score threshold if specified
        relevant_docs = [
            doc for doc, score in results
            if score >= score_threshold
        ]

        return relevant_docs

    def retrieve_documents_by_source(
        self,
        query: str,
        source_file: str,
        k: int = 5
    ) -> List[Document]:
        """
        Retrieve documents from a specific source file.

        Args:
            query: Search query
            source_file: Source file to filter by
            k: Number of documents to retrieve

        Returns:
            List of relevant Document objects from the source
        """
        if self.vector_store is None:
            raise ValueError("Vector store not initialized")

        # Search with metadata filter
        results = self.vector_store.similarity_search(
            query,
            k=k * 2  # Get more to account for filtering
        )

        # Filter by source
        filtered = [
            doc for doc in results
            if doc.metadata.get("source_file") == source_file
        ]

        return filtered[:k]

    def search_with_context(
        self,
        query: str,
        k: int = 5,
        context_window: int = 2
    ) -> List[dict]:
        """
        Retrieve documents with additional context information.

        Args:
            query: Search query
            k: Number of documents to retrieve
            context_window: Additional context lines

        Returns:
            List of documents with metadata and context
        """
        if self.vector_store is None:
            raise ValueError("Vector store not initialized")

        docs = self.retrieve_documents(query, k=k)

        results = []
        for doc in docs:
            results.append({
                "content": doc.page_content,
                "source": doc.metadata.get("source_file", "unknown"),
                "page": doc.metadata.get("page", 0),
                "relevance": "high"  # Could compute actual score if needed
            })

        return results

    def get_stats(self) -> dict:
        """Get statistics about the vector store."""
        if self.vector_store is None:
            return {"status": "not initialized"}

        return {
            "status": "initialized",
            "vector_store_path": str(self.vector_store_path),
            "embeddings_model": "all-MiniLM-L6-v2" if not self.use_bedrock else "amazon.titan-embed-text-v1"
        }
