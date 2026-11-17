"""Test doubles that stand in for networked services."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedChatModel(BaseChatModel):
    """A chat model that replays a fixed list of responses, one per call.

    ``bind_tools`` returns the model itself, so a graph can bind tools exactly
    as it would with ChatOpenAI. Every call's input messages are recorded in
    ``calls`` for assertions about what the model was shown.
    """

    responses: list[AIMessage]
    calls: list[list[BaseMessage]] = []

    def __init__(self, responses: list[AIMessage], **kwargs: Any):
        super().__init__(responses=list(responses), calls=[], **kwargs)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
        return self

    def _generate(self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        self.calls.append(list(messages))
        if not self.responses:
            raise RuntimeError("ScriptedChatModel ran out of scripted responses")
        return ChatResult(generations=[ChatGeneration(message=self.responses.pop(0))])
