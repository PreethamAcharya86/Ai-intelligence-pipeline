from __future__ import annotations

import asyncio
import json
import os
import random
from dataclasses import dataclass
from typing import Protocol


class Provider(Protocol):
    name: str
    async def extract(self, prompt: str) -> dict: ...


def semantic_chunks(text: str, max_chars: int = 12_000) -> list[str]:
    """Split on paragraphs/sentences before hard boundaries, avoiding 413-sized payloads."""
    clean = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    chunks, current = [], ""
    for paragraph in clean.split("\n"):
        if len(paragraph) > max_chars:
            sentences = paragraph.replace(". ", ".\n").split("\n")
        else:
            sentences = [paragraph]
        for sentence in sentences:
            if current and len(current) + len(sentence) + 1 > max_chars:
                chunks.append(current)
                current = ""
            current = f"{current}\n{sentence}".strip()
    if current:
        chunks.append(current)
    return chunks or [""]


@dataclass
class LlmOrchestrator:
    providers: list[Provider]
    attempts: int = 4

    async def extract(self, text: str, schema_hint: str) -> list[dict]:
        results = []
        for chunk in semantic_chunks(text):
            prompt = f"Extract only facts explicitly present in the source. Return valid JSON matching: {schema_hint}\nSOURCE:\n{chunk}"
            results.append(await self._call_with_fallback(prompt))
        return results

    async def _call_with_fallback(self, prompt: str) -> dict:
        errors = []
        for provider in self.providers:
            for attempt in range(self.attempts):
                try:
                    return await provider.extract(prompt)
                except Exception as error:  # provider SDKs expose incompatible exception classes
                    status = getattr(error, "status_code", None) or getattr(error, "status", None)
                    errors.append(f"{provider.name}: {error}")
                    if status not in (429, 413) or attempt == self.attempts - 1:
                        break
                    # 413 is handled upstream by semantic_chunks; retry only after a small jittered pause.
                    await asyncio.sleep(min(30, 2 ** attempt) + random.uniform(0, 0.5))
        raise RuntimeError("All LLM providers failed: " + " | ".join(errors))


def configured_provider_order() -> list[str]:
    """Documents the production fallback order without claiming a provider is configured."""
    return [name for name, env in [("gemini-flash", "GEMINI_API_KEY"), ("groq-llama", "GROQ_API_KEY"), ("deepseek", "DEEPSEEK_API_KEY")] if os.getenv(env)]
