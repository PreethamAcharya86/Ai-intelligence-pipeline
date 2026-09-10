from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from .models import utc_now
from .storage import StateStore

_SUFFIXES = re.compile(r"\b(incorporated|inc|llc|ltd|limited|corp|corporation|technologies|technology)\b", re.I)
_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize_name(name: str) -> str:
    name = _SUFFIXES.sub("", name.lower())
    return _NON_WORD.sub("", name)


@dataclass(frozen=True)
class Resolution:
    raw_name: str
    canonical_name: str
    confidence: float
    method: str


class EntityResolver:
    def __init__(self, canonical_names: list[str], store: StateStore, threshold: float = 88.0) -> None:
        self.names = canonical_names
        self.normalized = {normalize_name(name): name for name in canonical_names}
        self.store = store
        self.threshold = threshold

    def resolve(self, raw_name: str) -> Resolution:
        key = normalize_name(raw_name)
        if key in self.normalized:
            result = Resolution(raw_name, self.normalized[key], 100.0, "normalized_exact")
        else:
            match = process.extractOne(key, self.normalized.keys(), scorer=fuzz.ratio)
            if match and match[1] >= self.threshold:
                result = Resolution(raw_name, self.normalized[match[0]], float(match[1]), "fuzzy_seed")
            else:
                result = Resolution(raw_name, raw_name.strip(), float(match[1]) if match else 0.0, "unresolved")
        self.store.save_mapping(result.raw_name, result.canonical_name, result.confidence, result.method, utc_now())
        return result


DEFAULT_CANONICAL_ENTITIES = [
    "OpenAI", "Anthropic", "Hugging Face", "Mistral AI", "Cohere", "Scale AI", "Perplexity",
    "Databricks", "NVIDIA", "Google DeepMind", "Microsoft", "Meta", "Amazon", "xAI", "Stability AI",
    "Midjourney", "Runway", "Pika", "ElevenLabs", "Synthesia", "Harvey", "Glean", "Writer",
    "Jasper", "Notion", "Canva", "Figma", "Cursor", "Replit", "Weights & Biases", "LangChain",
    "LlamaIndex", "Pinecone", "Weaviate", "Redis", "Modal", "Together AI", "Groq", "Cerebras",
    "SambaNova", "Anduril", "Palantir", "Figure AI", "Waymo", "Zoox", "Vercel", "Sierra", "Decagon",
    "Cognition", "Poolside",
]
