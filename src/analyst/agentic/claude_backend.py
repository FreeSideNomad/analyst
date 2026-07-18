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

    # The CLI occasionally dies with "Reached maximum number of turns (1)"
    # on a perfectly ordinary single-turn request — observed in recording
    # sessions and live curation (defect 2026-07-18). One retry absorbs it.
    _TRANSIENT = "maximum number of turns"

    def complete(self, request: LLMRequest) -> str:
        try:
            return asyncio.run(self._acomplete(request))
        except Exception as exc:  # noqa: BLE001 - retry only the known transient
            if self._TRANSIENT not in str(exc):
                raise
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
            # 2x the original single-turn budget (owner request 2026-07-18):
            # the CLI sometimes needs a second turn to emit its final text.
            max_turns=2,
            system_prompt=request.system_prompt,
        )
        parts: list[str] = []
        async for message in query(prompt=request.prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        parts.append(block.text)
        return "".join(parts).strip()
