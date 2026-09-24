"""Real local LSA embeddings or configured OpenAI embeddings.

LSA learns TF-IDF + truncated SVD from this corpus. It is a lightweight latent
semantic baseline, not a pretrained neural model. Files contain arrays/JSON,
never executable pickle objects. Model identity prevents mixed embedding spaces.
"""

import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path

import httpx
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from src.config.settings import PROJECT_ROOT, get_settings


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per text."""

    def embed_text(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class LocalEmbeddings(EmbeddingProvider):
    def __init__(self, dimensions=128):
        self.dimensions = dimensions
        self.vectorizer = TfidfVectorizer(
            max_features=20000, stop_words="english", ngram_range=(1, 2), sublinear_tf=True
        )
        self.components = None
        self.space = ""

    def fit(self, texts):
        matrix = self.vectorizer.fit_transform(texts)
        n = min(self.dimensions, matrix.shape[0] - 1, matrix.shape[1] - 1)
        if n < 2:
            raise ValueError(
                "At least three nonempty documents with distinct vocabulary are required"
            )
        svd = TruncatedSVD(n_components=n, random_state=42, n_iter=5)
        svd.fit(matrix)
        self.components = svd.components_.astype(np.float32)
        digest = hashlib.sha256(
            self.components.tobytes() + self.vectorizer.idf_.tobytes()
        ).hexdigest()[:24]
        self.space = "lsa-" + digest
        return self

    def embed_documents(self, texts):
        if self.components is None:
            raise ValueError("Local embedding model is not fitted; run indexing first")
        vectors = self.vectorizer.transform(texts) @ self.components.T
        vectors = normalize(vectors).astype(np.float32)
        vectors = np.pad(vectors, ((0, 0), (0, self.dimensions - vectors.shape[1])))
        return vectors.tolist()

    def save(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (self.space + ".npz")
        np.savez_compressed(path, components=self.components, idf=self.vectorizer.idf_)
        path.with_suffix(".json").write_text(
            json.dumps(
                {
                    "vocabulary": {k: int(v) for k, v in self.vectorizer.vocabulary_.items()},
                    "dimensions": self.dimensions,
                    "space": self.space,
                }
            ),
            encoding="utf-8",
        )
        return path.name

    @classmethod
    def load(cls, filename):
        path = PROJECT_ROOT / "data/models" / Path(filename).name
        metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        arrays = np.load(path, allow_pickle=False)
        model = cls(metadata["dimensions"])
        model.vectorizer = TfidfVectorizer(
            vocabulary=metadata["vocabulary"],
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        model.vectorizer.idf_ = arrays["idf"]
        model.components = arrays["components"]
        model.space = metadata["space"]
        return model


class OpenAIEmbeddings(EmbeddingProvider):
    def __init__(self):
        self.settings = get_settings()
        self.dimensions = self.settings.embedding_dimensions
        self.space = f"openai-{self.settings.embedding_model}-{self.dimensions}"

    def embed_documents(self, texts):
        s = self.settings
        if not s.openai_api_key.get_secret_value():
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings")
        results = []
        with httpx.Client(timeout=90) as client:
            for offset in range(0, len(texts), s.embedding_batch_size):
                response = client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": "Bearer " + s.openai_api_key.get_secret_value()},
                    json={
                        "model": s.embedding_model,
                        "dimensions": self.dimensions,
                        "input": texts[offset : offset + s.embedding_batch_size],
                    },
                )
                response.raise_for_status()
                results.extend(
                    item["embedding"]
                    for item in sorted(response.json()["data"], key=lambda x: x["index"])
                )
        if len(results) != len(texts) or any(len(v) != self.dimensions for v in results):
            raise ValueError("Embedding provider returned incompatible vectors")
        return results


class BGEEmbeddings(EmbeddingProvider):
    """Local ONNX BGE-small sentence embeddings via FastEmbed; no API key."""

    model_name = "BAAI/bge-small-en-v1.5"
    dimensions = 384
    space = "fastembed-bge-small-en-v1.5-384"

    def __init__(self):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(
            model_name=self.model_name,
            cache_dir=str(PROJECT_ROOT / "data/models/fastembed"),
            threads=4,
        )

    def embed_documents(self, texts):
        vectors = np.asarray(list(self.model.embed(texts, batch_size=32)), dtype=np.float32)
        if vectors.shape != (len(texts), self.dimensions):
            raise ValueError("BGE returned incompatible vector dimensions")
        if not np.isfinite(vectors).all():
            raise ValueError("BGE returned a non-finite vector")
        return normalize(vectors).tolist()

    def embed_text(self, text):
        # BGE's retrieval instruction applies to queries, not document chunks.
        return self.embed_documents(
            ["Represent this sentence for searching relevant passages: " + text]
        )[0]
