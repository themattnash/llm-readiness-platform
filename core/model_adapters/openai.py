from __future__ import annotations

import os
from typing import Any, List

from openai import OpenAI

from .base import ModelAdapter


class OpenAIChatAdapter(ModelAdapter):
    """
    Simple wrapper around OpenAI chat completions.
    """

    def __init__(self, model: str = "gpt-4.1-mini", api_key: str | None = None):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed explicitly.")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.name = f"openai:{model}"

    def generate(self, prompt: str, **kwargs: Any) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        message = response.choices[0].message
        return message.content or ""

    def batched_generate(self, prompts: List[str], **kwargs: Any) -> List[str]:
        return [self.generate(p, **kwargs) for p in prompts]
