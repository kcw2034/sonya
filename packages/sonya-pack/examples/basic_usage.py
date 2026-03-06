#!/usr/bin/env python3
"""basic_usage.py — BinContext engine basic usage example

This script demonstrates:
  1. Engine initialization (temporary directory)
  2. Adding messages to multiple sessions (Append-Only Binary Log)
  3. Restoring full/last N turn context via JIT Context Builder
  4. Querying session metadata
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from sonya.pack import BinContextEngine


def main() -> None:
    # -- 1) Engine initialization ----------------------------------
    # Use a temporary directory for automatic cleanup after example
    with tempfile.TemporaryDirectory(prefix='binctx_') as tmp:
        data_dir = Path(tmp) / 'store'
        engine = BinContextEngine(data_dir)

        print('=' * 60)
        print('  BinContext Engine — Basic Usage Example')
        print('=' * 60)

        # -- 2) Add messages ---------------------------------------
        session_id = 'chat-001'

        engine.add_message(
            session_id, 'system',
            'You are a friendly AI assistant.'
        )
        engine.add_message(
            session_id, 'user',
            'Hello! Tell me about Python.'
        )
        engine.add_message(
            session_id,
            'assistant',
            'Hello! Python is an easy-to-learn and powerful '
            'programming language. It is used in data science, '
            'web development, AI, and many other fields.',
        )
        engine.add_message(
            session_id, 'user',
            'What are the most popular libraries?'
        )
        engine.add_message(
            session_id,
            'assistant',
            'Popular Python libraries include NumPy, Pandas, '
            'TensorFlow, FastAPI, and more.',
        )

        bin_size = (data_dir / 'context.bin').stat().st_size
        print(f'\nData directory: {data_dir}')
        print(f'.bin file size: {bin_size} bytes')

        # -- 3) Full context restoration (JIT) ---------------------
        print('\n-- Full conversation context --')
        full_context = engine.build_context(session_id)
        for msg in full_context:
            role_label = msg['role']
            print(
                f'  [{role_label:>9}] '
                f'{msg["content"][:60]}...'
            )

        # -- 4) Last 2 turns only ----------------------------------
        print('\n-- Last 2 turns (last_n_turns=2) --')
        recent = engine.build_context(
            session_id, last_n_turns=2
        )
        for msg in recent:
            role_label = msg['role']
            print(f'  [{role_label:>9}] {msg["content"]}')

        # -- 5) Session metadata -----------------------------------
        print('\n-- Session metadata --')
        session = engine.get_session(session_id)
        print(f'  Session ID : {session.session_id}')
        print(f'  Messages   : {len(session.messages)}')
        for i, meta in enumerate(session.messages):
            print(
                f'    [{i}] role={meta.role:>9}  '
                f'offset={meta.offset:>4}  '
                f'length={meta.length:>4}  '
                f'id={meta.message_id[:8]}...'
            )

        # -- 6) Persistence verification --------------------------
        print('\n-- Metadata persistence check --')
        engine2 = BinContextEngine(data_dir)
        restored = engine2.build_context(
            session_id, last_n_turns=1
        )
        print(
            f'  Restored last message: '
            f'{restored[0]["content"]}'
        )

        print('\nAll examples completed successfully!')


if __name__ == '__main__':
    main()
