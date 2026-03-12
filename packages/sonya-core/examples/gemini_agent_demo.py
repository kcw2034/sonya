"""Live demo: Gemini-based agent with tool use and handoff."""

import asyncio
import os
import sys

# Load .env from project root
_env_path = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..', '.env'
)
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip())

from sonya.core import (  # noqa: E402
    Agent,
    AgentRuntime,
    GeminiClient,
    ClientConfig,
    Runner,
    RunnerConfig,
    tool,
)


# ---- Tools ----

@tool(description='Get the current weather for a city.')
def get_weather(city: str) -> str:
    """Return fake weather data for demo purposes."""
    weather_data = {
        'Seoul': 'Sunny, 8°C',
        'Tokyo': 'Cloudy, 12°C',
        'New York': 'Rainy, 5°C',
    }
    return weather_data.get(city, f'No data for {city}')


@tool(description='Convert temperature between Celsius and Fahrenheit.')
def convert_temp(value: float, to_unit: str) -> str:
    """Convert temperature. to_unit: 'F' or 'fahrenheit' to convert to Fahrenheit, 'C' or 'celsius' to convert to Celsius."""
    unit = to_unit.upper().strip()
    if unit in ('F', 'FAHRENHEIT'):
        result = value * 9 / 5 + 32
        return f'{value}°C = {result:.1f}°F'
    elif unit in ('C', 'CELSIUS'):
        result = (value - 32) * 5 / 9
        return f'{value}°F = {result:.1f}°C'
    return f'Unknown unit: {to_unit}'


# ---- Test 1: Single Agent with Tools ----

async def test_single_agent() -> None:
    print('=' * 60)
    print('Test 1: Single Gemini Agent with Tools')
    print('=' * 60)

    config = ClientConfig(model='gemini-2.0-flash')
    client = GeminiClient(config)

    agent = Agent(
        name='weather_bot',
        client=client,
        instructions=(
            'You are a helpful weather assistant. '
            'Use the get_weather tool to look up weather, '
            'and convert_temp to convert temperatures. '
            'Always respond concisely.'
        ),
        tools=[get_weather, convert_temp],
        max_iterations=5,
    )

    runtime = AgentRuntime(agent)
    result = await runtime.run([
        {
            'role': 'user',
            'parts': [
                {
                    'text': (
                        'What is the weather in Seoul? '
                        'Also convert the temperature to Fahrenheit.'
                    )
                }
            ],
        }
    ])

    print(f'\nAgent: {result.agent_name}')
    print(f'Response: {result.text}')
    print(f'History length: {len(result.history)}')
    print(f'Handoff: {result.handoff_to}')
    print()


# ---- Test 2: Handoff between two agents ----

async def test_handoff() -> None:
    print('=' * 60)
    print('Test 2: Handoff Chain (Triage -> Specialist)')
    print('=' * 60)

    config = ClientConfig(model='gemini-2.0-flash')

    specialist_client = GeminiClient(config)
    specialist = Agent(
        name='weather_specialist',
        client=specialist_client,
        instructions=(
            'You are a weather specialist. '
            'Use get_weather to look up weather data. '
            'Give a detailed weather report.'
        ),
        tools=[get_weather],
        max_iterations=5,
    )

    triage_client = GeminiClient(config)
    triage = Agent(
        name='triage',
        client=triage_client,
        instructions=(
            'You are a triage agent. '
            'For weather-related questions, you MUST use the '
            '__handoff_to_weather_specialist tool to delegate. '
            'For other questions, answer directly.'
        ),
        handoffs=[specialist],
        max_iterations=3,
    )

    runner_config = RunnerConfig(
        agents=[triage, specialist],
        max_handoffs=3,
    )
    runner = Runner(runner_config)
    result = await runner.run(
        [
            {
                'role': 'user',
                'parts': [
                    {'text': 'What is the weather like in Tokyo?'}
                ],
            }
        ],
        start_agent='triage',
    )

    print(f'\nFinal Agent: {result.agent_name}')
    print(f'Response: {result.text}')
    print(f'History length: {len(result.history)}')
    print()


async def main() -> None:
    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        print('ERROR: GOOGLE_API_KEY not found in environment.')
        sys.exit(1)

    print('API Key loaded: [REDACTED]\n')

    await test_single_agent()
    await test_handoff()

    print('All tests completed successfully!')


if __name__ == '__main__':
    asyncio.run(main())
