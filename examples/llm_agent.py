#!/usr/bin/env python3
"""LLM-powered agent that observes Plato rooms and makes decisions.

Requires: pip install plato-agent[llm]
"""

import asyncio
import json
import os
import sys

from plato_agent.agent import PlatoAgent
from plato_agent.client import PlatoClient
from plato_agent.protocol import TickData
from plato_agent.summary import summarize_ticks


async def llm_decide(prompt: str) -> str:
    """Send a prompt to an LLM and get a decision.

    Uses OpenAI-compatible API. Set OPENAI_API_KEY and optionally OPENAI_BASE_URL.
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        return "Error: install openai package (pip install plato-agent[llm])"

    client = AsyncOpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        base_url=os.environ.get("OPENAI_BASE_URL"),
    )
    model = os.environ.get("PLATO_LLM_MODEL", "gpt-4o-mini")

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": (
                "You are a marine vessel monitoring AI. Analyze sensor data and alarms. "
                "Respond with a JSON object: {\"action\": \"...\", \"reasoning\": \"...\", \"urgency\": \"low|medium|high|critical\"}"
            )},
            {"role": "user", "content": prompt},
        ],
        max_tokens=300,
        temperature=0.3,
    )
    return response.choices[0].message.content or "No response"


async def run_llm_agent() -> None:
    """Run the LLM-powered agent demo."""
    agent = PlatoAgent()

    # Simulate some room data
    from plato_agent.protocol import AlarmNotification
    room = agent.add_room("engine", None)  # type: ignore

    # Simulate ticks
    for i in range(20):
        room.update_from_tick(TickData(
            timestamp=float(i),
            sensors={"temp": 85 + i * 0.5, "rpm": 2200 + i * 10, "oil_pressure": 40 - i * 0.3},
        ))

    # Generate summary
    summary = summarize_ticks(room.history[-10:], room.name="engine")
    print(f"📊 Summary: {summary}\n")

    # Ask LLM for decision
    alarm_info = ""
    if room.active_alarms:
        alarm_info = f"\nActive alarms: {json.dumps([{'name': a.name, 'severity': a.severity, 'msg': a.message} for a in room.active_alarms])}"

    prompt = f"Room sensor summary:\n{summary}\n{alarm_info}\n\nWhat should the crew do?"

    print(f"🤖 Asking LLM...")
    decision = await llm_decide(prompt)
    print(f"💡 LLM Decision:\n{decision}")


if __name__ == "__main__":
    asyncio.run(run_llm_agent())
