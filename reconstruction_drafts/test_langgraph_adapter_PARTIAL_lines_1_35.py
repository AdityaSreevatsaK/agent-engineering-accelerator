import asyncio
import importlib
import json
import math
import sys
import textwrap
import uuid

import pytest
from inspect_ai.log import read_eval_log
from inspect_ai.model import ChatMessageTool, ModelName
from inspect_ai.scorer import CORRECT
from inspect_ai.solver import TaskState

from langchain_core.messages import AIMessage

from agent_accelerator.adapters.langgraph import _dedupe, _json_safe, langgraph_agent
from agent_accelerator.cli import main
from agent_accelerator.dataset import DATASET_FORMAT_VERSION, Case, load_dataset
from agent_accelerator.run import build_task, run_task
from agent_accelerator.scorers import CASE_CHECKS, run_checks

DOUBLES = "aea_lg_contract_doubles"
QUESTION = "What is 1 plus 2?"


class Opaque:
    """A value JSON cannot hold, with a fixed repr."""

    def __repr__(self):
        return "Opaque()"


OPAQUE = Opaque()

