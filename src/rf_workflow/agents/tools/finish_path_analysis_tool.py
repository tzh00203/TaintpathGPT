"""
Tool for finishing path analysis.
"""

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk
from loguru import logger

_FINISH_PATH_ANALYSIS_DESCRIPTION = """Use this tool to indicate that you have completed analysis for the current taint path.

You must ensure:
1. All taint locations in the path have been processed
2. Constraints have been extracted for source, intermediate, and sink locations
3. Path constraints have been generated in SMT-LIB format

Use this tool when:
- All locations in the current path have been analyzed
- You are ready to move to the next path (if any)
- Or all paths have been processed

Example:
```
Completed analysis for PATH 1:
- Source: upload.c:249 (user input)
- Intermediate: 3 constraints extracted (lines 270-271, 335)
- Sink: upload.c:339 (buffer overflow point)
- Total constraints: 5
```"""

FinishPathAnalysisTool = ChatCompletionToolParam(
    type="function",
    function=ChatCompletionToolParamFunctionChunk(
        name="finish_path_analysis",
        description=_FINISH_PATH_ANALYSIS_DESCRIPTION,
        parameters={
            "type": "object",
            "properties": {
                "path_id": {
                    "type": "string",
                    "description": "Path identifier that was completed (e.g., 'PATH 1')",
                },
                "source_location": {
                    "type": "string",
                    "description": "Source location (file:line)",
                },
                "sink_location": {
                    "type": "string",
                    "description": "Sink location (file:line)",
                },
                "constraint_count": {
                    "type": "integer",
                    "description": "Total number of constraints extracted",
                },
                "has_more_paths": {
                    "type": "boolean",
                    "description": "Whether there are more paths to analyze",
                },
            },
            "required": ["path_id", "source_location", "sink_location", "constraint_count", "has_more_paths"],
        },
    ),
)


def process_finish_path_analysis(
    path_id: str,
    source_location: str,
    sink_location: str,
    constraint_count: int,
    has_more_paths: bool
) -> tuple[str, dict]:
    """
    Process path analysis completion.

    Returns:
        (observation message, completion data dict)
    """
    if not path_id:
        return "Error: path_id is required.", {}
    if not source_location:
        return "Error: source_location is required.", {}
    if not sink_location:
        return "Error: sink_location is required.", {}
    if not isinstance(constraint_count, int) or constraint_count < 0:
        return "Error: constraint_count must be a non-negative integer.", {}

    completion_data = {
        "path_id": path_id,
        "source_location": source_location,
        "sink_location": sink_location,
        "constraint_count": constraint_count,
        "has_more_paths": has_more_paths
    }

    logger.info(f"Completed analysis for {path_id}")

    message = (
        f"Path {path_id} analysis completed:\n"
        f"- Source: {source_location}\n"
        f"- Sink: {sink_location}\n"
        f"- Constraints extracted: {constraint_count}\n"
    )

    if has_more_paths:
        message += "\nPlease continue analyzing the next path."
    else:
        message += "\nAll paths have been analyzed. Great job!"

    return message, completion_data