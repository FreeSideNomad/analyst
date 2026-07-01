"""ClaudeAgentBackend — real cataloguing calls via the Claude Agent SDK.

Uses the Claude Code subscription (no API key). Tools are disabled so the model
can only see the prompt we build — never the local filesystem or bulk data.
"""

from __future__ import annotations

import asyncio

from analyst.agentic.gateway import LLMRequest

MODEL = "claude-opus-4-8"


class ClaudeAgentBackend:
    """Live backend. Kept out of the default import path so tests don't need it."""

    def __init__(self, model: str = MODEL):
        self.model = model

    def complete(self, request: LLMRequest) -> str:
        return asyncio.run(self._acomplete(request))

    async def _acomplete(self, request: LLMRequest) -> str:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            TextBlock,
            query,
        )

        options = ClaudeAgentOptions(
            model=self.model,
            allowed_tools=[],  # governance: model sees only the prompt
            max_turns=1,
            system_prompt=request.system_prompt,
        )
        parts: list[str] = []
        async for message in query(prompt=request.prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        parts.append(block.text)
        return "".join(parts).strip()
