"""
Tool for thinking and reasoning during taint path analysis.
"""

from typing import Optional

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk
from loguru import logger

_THINKING_TOOL_DESCRIPTION = """Use this tool to think step-by-step about the taint flow and constraint extraction process.

You can use this tool to:
1. Analyze the taint flow path structure
2. Reason about which constraints are relevant at each location
3. Plan the constraint extraction strategy
4. Track the relationship between taint source and sink

Example reasoning:
```
The taint flow starts at line 249 where user input is read.
The input then passes through validation at line 270-271.
Finally, tainted data reaches a sink at line 339.
The key constraints to extract are:
- Input validation at line 270-271 (length check, format check)
- Path selection at line 335 (branch condition)
- Sink precondition at line 338 (buffer size check)
```"""

ThinkingTool = ChatCompletionToolParam(
    type="function",
    function=ChatCompletionToolParamFunctionChunk(
        name="thinking",
        description=_THINKING_TOOL_DESCRIPTION,
        parameters={
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Step-by-step reasoning about taint flow and constraint extraction",
                },
            },
            "required": ["reasoning"],
        },
    ),
)


def process_thinking_tool(reasoning: Optional[str]) -> str:
    """Process thinking tool."""
    if not reasoning:
        return "Error: No reasoning provided. Please provide your reasoning."
    logger.info(f"Thinking: {reasoning}")
    return f"Recorded your reasoning."