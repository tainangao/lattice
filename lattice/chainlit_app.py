from __future__ import annotations

import chainlit as cl

from lattice.prototype.config import load_config
from lattice.prototype.service import PrototypeService


@cl.on_chat_start
async def on_chat_start() -> None:
    await cl.Message(
        content=(
            "Phase 1 prototype is ready. Ask about project timelines, dependencies, "
            "or ownership links across document and graph context."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    service = PrototypeService(load_config())

    route_step = cl.Step(name="Router Agent", type="tool")
    await route_step.send()
    result = await service.run_query(message.content)
    route_step.output = f"{result.route.mode.value}: {result.route.reason}"
    await route_step.update()

    snippet_lines = [
        f"- [{item.source_type}] {item.source_id} (score={item.score:.2f})"
        for item in result.snippets
    ]
    snippets_block = (
        "\n".join(snippet_lines) if snippet_lines else "- no retrieval snippets"
    )
    await cl.Message(content=f"{result.answer}\n\nSources:\n{snippets_block}").send()
