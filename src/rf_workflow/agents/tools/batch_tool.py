"""
Tool for executing multiple tool calls in a single function call.
"""

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk

_BATCH_TOOL_DESCRIPTION = """Execute multiple tool calls in a single function call. Use this when you need to make multiple independent tool calls at once.

This is useful when:
- You need to process multiple taint locations simultaneously
- You want to batch track multiple constraints
- Making multiple independent decisions at once

Example:
```
invocations: [
  {
    "tool_name": "track_taint_location",
    "arguments": {
      "file_path": "upload.c",
      "line": 249,
      "type": "source",
      "constraint": "user input read",
      "reasoning": "taint source"
    }
  },
  {
    "tool_name": "track_taint_location",
    "arguments": {
      "file_path": "upload.c",
      "line": 271,
      "type": "intermediate",
      "constraint": "strlen check",
      "reasoning": "input validation"
    }
  }
]
```"""

BatchTool = ChatCompletionToolParam(
    type="function",
    function=ChatCompletionToolParamFunctionChunk(
        name="batch",
        description=_BATCH_TOOL_DESCRIPTION,
        parameters={
            "type": "object",
            "properties": {
                "invocations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tool_name": {
                                "type": "string",
                                "description": "Name of the tool to call",
                            },
                            "arguments": {
                                "type": "object",
                                "description": "Arguments to pass to the tool",
                            },
                        },
                        "required": ["tool_name"],
                    },
                    "description": "List of tool invocations to execute",
                },
            },
            "required": ["invocations"],
        },
    ),
)