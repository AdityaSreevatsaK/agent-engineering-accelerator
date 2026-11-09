"""Strands calculator agent on a real Bedrock model, for live runs with --epochs.

Needs AWS credentials with Bedrock access. AEA_MODEL_ID selects the model (default Claude Haiku 5.5).
The system prompt spells out the reply conventions the dataset checks, which the offline double follows by construction.
"""

import os

from strands import Agent
from strands.models import BedrockModel

from examples.calculator.agent import calculator

DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-5-5"
SYSTEM_PROMPT = """You are a calculator. Always use the calculator tool for arithmetic; never compute in your head.
Reply rules:
- Normally reply with only the resulting number, nothing else (for example: 42).
- If the message starts with "json:", reply with only a JSON object, no code fences:
  {"result": <number>, "operation": "<add|sub|mul|div>"}
- If the tool fails, say so and quote the tool's error message.
- If the request is not arithmetic, do not call the tool; say you can only help with arithmetic."""


def build_live_agent() -> Agent:
    model = BedrockModel(model_id=os.environ.get("AEA_MODEL_ID", DEFAULT_MODEL_ID))
    return Agent(model=model, tools=[calculator], system_prompt=SYSTEM_PROMPT, callback_handler=None)
