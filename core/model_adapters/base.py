from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List


class ModelAdapter(ABC):
    """
    Thin abstraction over different LLM providers.

    Implementations:
      - OpenAIChatAdapter
      - AnthropicAdapter
      - GeminiAdapter
      - Internal models

    This lets the eval harness stay provider-agnostic.
    """

    name: str

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Synchronous single-prompt generation."""
        raise NotImplementedError

    def batched_generate(self, prompts: List[str], **kwargs: Any) -> List[str]:
        """
        Optional batch interface. Default = naive loop.
        Override if provider supports true batching.
        """
        return [self.generate(p, **kwargs) for p in prompts]
