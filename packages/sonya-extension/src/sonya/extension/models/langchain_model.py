"""SonyaChatModel — wraps a sonya BaseClient as LangChain ChatModel."""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional

from sonya.core.client.base import BaseClient
from sonya.core.parsers.adapter import get_adapter

from sonya.extension.schemas.types import (
    _check_langchain,
    langchain_to_sonya_messages,
)


def _build_sonya_chat_model_class() -> type:
    """Build SonyaChatModel class with LangChain imports.

    Returns:
        The SonyaChatModel class.

    Raises:
        ImportError: If langchain-core is not installed.
    """
    _check_langchain()

    from langchain_core.callbacks import (
        CallbackManagerForLLMRun,
    )
    from langchain_core.language_models.chat_models import (
        BaseChatModel,
    )
    from langchain_core.messages import (
        AIMessage,
        BaseMessage,
    )
    from langchain_core.outputs import (
        ChatGeneration,
        ChatResult,
    )

    class _SonyaChatModel(BaseChatModel):
        """Wraps a sonya BaseClient as a LangChain ChatModel.

        This allows using sonya's provider clients (Anthropic,
        OpenAI, Gemini) inside LangChain chains and agents.

        Args:
            sonya_client: A sonya BaseClient instance.
        """

        sonya_client: Any = None
        _adapter: Any = None

        model_config = {'arbitrary_types_allowed': True}

        def __init__(
            self,
            sonya_client: BaseClient,
            **kwargs: Any,
        ) -> None:
            super().__init__(
                sonya_client=sonya_client,
                **kwargs,
            )
            self._adapter = get_adapter(sonya_client)

        @property
        def _llm_type(self) -> str:
            """Return identifier for this LLM type."""
            return (
                f'sonya-{type(self.sonya_client).__name__}'
            )

        def _generate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[
                CallbackManagerForLLMRun
            ] = None,
            **kwargs: Any,
        ) -> ChatResult:
            """Generate a response synchronously.

            Args:
                messages: LangChain messages.
                stop: Stop sequences.
                run_manager: Callback manager.
                **kwargs: Provider-specific kwargs.

            Returns:
                LangChain ChatResult.
            """
            try:
                asyncio.get_running_loop()
                _loop_running = True
            except RuntimeError:
                _loop_running = False

            if _loop_running:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(
                ) as pool:
                    result = pool.submit(
                        asyncio.run,
                        self._agenerate(
                            messages, stop,
                            run_manager, **kwargs,
                        ),
                    ).result()
                return result

            return asyncio.run(
                self._agenerate(
                    messages, stop,
                    run_manager, **kwargs,
                )
            )

        async def _agenerate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[Any] = None,
            **kwargs: Any,
        ) -> ChatResult:
            """Generate a response asynchronously.

            Args:
                messages: LangChain messages.
                stop: Stop sequences.
                run_manager: Callback manager.
                **kwargs: Provider-specific kwargs.

            Returns:
                LangChain ChatResult.
            """
            sonya_msgs = langchain_to_sonya_messages(
                messages
            )

            if stop:
                kwargs['stop'] = stop

            response = await self.sonya_client.generate(
                sonya_msgs, **kwargs
            )

            parsed = self._adapter.parse(response)

            tool_calls = []
            for tc in parsed.tool_calls:
                tool_calls.append({
                    'name': tc.name,
                    'args': tc.arguments,
                    'id': tc.id,
                    'type': 'tool_call',
                })

            ai_msg = AIMessage(
                content=parsed.text,
                tool_calls=tool_calls if tool_calls
                else [],
            )

            return ChatResult(
                generations=[
                    ChatGeneration(message=ai_msg)
                ]
            )

    return _SonyaChatModel


class SonyaChatModel:
    """Proxy that lazily loads the real LangChain-based class.

    Calling ``SonyaChatModel(sonya_client=client)`` returns an
    instance of the internal ``_SonyaChatModel`` which extends
    ``BaseChatModel``.

    Args:
        sonya_client: A sonya BaseClient instance.
        **kwargs: Additional keyword arguments.
    """

    _cls: type | None = None

    def __new__(
        cls,
        sonya_client: BaseClient,
        **kwargs: Any,
    ) -> Any:
        """Create a new SonyaChatModel instance.

        Args:
            sonya_client: A sonya BaseClient instance.
            **kwargs: Additional keyword arguments.

        Returns:
            An instance of the internal _SonyaChatModel.
        """
        if cls._cls is None:
            cls._cls = _build_sonya_chat_model_class()
        return cls._cls(
            sonya_client=sonya_client, **kwargs
        )
