from langchain_ollama import OllamaEmbeddings

_embedder = OllamaEmbeddings(
    model="nomic-embed-text"
)