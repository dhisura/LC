"""Base agent role definition."""
from typing import List, Dict, Any, Optional
from lc.engine.llm import LLMClient
from lc.ui.console import LCConsole


class BaseRole:
    """Base class for all LC company subagents."""

    def __init__(
        self,
        name: str,
        title: str,
        system_prompt: str,
        llm: LLMClient,
        console: Optional[LCConsole] = None
    ):
        self.name = name
        self.title = title
        self.system_prompt = system_prompt
        self.llm = llm
        self.console = console or LCConsole()

    def generate(
        self,
        user_prompt: str,
        extra_system_context: str = "",
        temperature: float = 0.2
    ) -> str:
        """Call LLM with system prompt and user prompt."""
        full_system = self.system_prompt
        if extra_system_context:
            full_system += f"\n\n{extra_system_context}"

        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_prompt}
        ]
        return self.llm.chat(messages, temperature=temperature)
