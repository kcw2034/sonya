"""Runner — top-level orchestrator for multi-agent handoff chains."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.models.agent import Agent, AgentResult
from sonya.core.exceptions.errors import AgentError
from sonya.core.utils.router import ContextRouter
from sonya.core.utils.tool_context import ToolContext

if TYPE_CHECKING:
    from sonya.core.models.session import SessionStore


@runtime_checkable
class RunnerCallback(Protocol):
    """Protocol for Runner lifecycle callbacks."""

    async def on_agent_start(
        self,
        agent_name: str,
        messages: list[dict[str, Any]],
    ) -> None:
        """Called when an agent begins execution."""
        ...

    async def on_agent_end(
        self, result: AgentResult
    ) -> None:
        """Called when an agent finishes execution."""
        ...

    async def on_handoff(
        self, from_agent: str, to_agent: str
    ) -> None:
        """Called when a handoff occurs between agents."""
        ...


@dataclass(slots=True)
class RunnerConfig:
    """Configuration for the Runner orchestrator.

    Args:
        agents: List of agents that can participate.
        max_handoffs: Maximum number of handoffs before stopping.
        callbacks: Optional lifecycle callbacks.
        context: Shared tool context across all agents.
        router: Optional context router for handoff routing.
        session_store: Optional store for persisting conversation
            sessions.  When set, the Runner automatically saves
            history after every run and restores it on resume.
    """

    agents: list[Agent] = field(default_factory=list)
    max_handoffs: int = 10
    callbacks: list[RunnerCallback] = field(
        default_factory=list
    )
    context: ToolContext | None = None
    router: ContextRouter | None = None
    session_store: 'SessionStore | None' = None


class Runner:
    """Top-level orchestrator that manages agent handoff chains.

    Builds an ``agent_map`` from the config, runs the first agent,
    and follows handoff signals until the chain completes or
    ``max_handoffs`` is reached.

    Args:
        config: :class:`RunnerConfig` with agents and settings.
    """

    def __init__(self, config: RunnerConfig) -> None:
        self._config = config
        self._context = config.context or ToolContext()
        self._router = config.router
        self._agent_map: dict[str, Agent] = {
            a.name: a for a in config.agents
        }

    async def run(
        self,
        messages: list[dict[str, Any]],
        start_agent: str | None = None,
        session_id: str | None = None,
    ) -> AgentResult:
        """Execute the handoff chain starting from *start_agent*.

        When a :class:`~sonya.core.models.session.SessionStore` is
        configured in :class:`RunnerConfig`, the Runner automatically:

        * Generates a ``session_id`` if one is not provided.
        * Restores prior history from the store (prepended before
          *messages*).
        * Saves the updated history after the run completes.
        * Records ``session_id`` in ``AgentResult.metadata``.

        Args:
            messages: New conversation messages for this turn.
            start_agent: Name of the first agent to run.
                Defaults to the first agent in the config list.
            session_id: Optional session identifier.  Required to
                resume a previous session; auto-generated when a
                ``session_store`` is set and this is omitted.

        Returns:
            :class:`AgentResult` from the final agent in the chain.

        Raises:
            AgentError: If max_handoffs is exceeded or agent not found.
        """
        if not self._agent_map:
            raise AgentError(
                'Runner', 'No agents configured'
            )

        store = self._config.session_store

        # Resolve session_id and load prior history.
        _session_id: str | None = None
        if store is not None:
            _session_id = session_id or uuid.uuid4().hex
            prior = store.load(_session_id)
            if prior is not None:
                # Prepend stored history before the new messages.
                messages = prior.history + list(messages)

        current_name = (
            start_agent or self._config.agents[0].name
        )
        history = list(messages)

        for _handoff_count in range(
            self._config.max_handoffs + 1
        ):
            agent = self._agent_map.get(current_name)
            if agent is None:
                raise AgentError(
                    'Runner',
                    f"Agent '{current_name}' "
                    f"not found in agent_map",
                )

            # Notify callbacks
            for cb in self._config.callbacks:
                if hasattr(cb, 'on_agent_start'):
                    await cb.on_agent_start(
                        current_name, history
                    )

            runtime = AgentRuntime(
                agent, context=self._context
            )
            result = await runtime.run(history)

            # Notify callbacks
            for cb in self._config.callbacks:
                if hasattr(cb, 'on_agent_end'):
                    await cb.on_agent_end(result)

            if result.handoff_to is None:
                # Persist session if a store is configured.
                if store is not None and _session_id is not None:
                    self._save_session(
                        store,
                        _session_id,
                        result,
                        agent.name,
                    )
                    result.metadata['session_id'] = _session_id
                return result

            # Handoff
            for cb in self._config.callbacks:
                if hasattr(cb, 'on_handoff'):
                    await cb.on_handoff(
                        current_name, result.handoff_to
                    )

            # Route context to the next agent
            if self._router is not None:
                history = await self._router.route(
                    source=agent,
                    target=self._agent_map[
                        result.handoff_to
                    ],
                    history=result.history,
                    context=self._context,
                )
            else:
                # Fallback: existing behavior
                history = [
                    m for m in messages
                    if m.get('role') in ('user', 'system')
                ]
            current_name = result.handoff_to

        raise AgentError(
            'Runner',
            f'Exceeded max_handoffs '
            f'({self._config.max_handoffs})',
        )

    def _save_session(
        self,
        store: 'SessionStore',
        session_id: str,
        result: AgentResult,
        agent_name: str,
    ) -> None:
        """Persist *result* history into *store* under *session_id*."""
        from sonya.core.models.session import Session

        existing = store.load(session_id)
        now = time.time()
        session = Session(
            session_id=session_id,
            history=result.history,
            agent_name=agent_name,
            metadata=dict(result.metadata),
            created_at=(
                existing.created_at if existing else now
            ),
            updated_at=now,
        )
        store.save(session)
