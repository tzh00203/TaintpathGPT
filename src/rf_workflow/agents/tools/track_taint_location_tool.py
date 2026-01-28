"""
Tool for tracking taint locations and extracting path constraints.
"""

from typing import Optional

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk
from loguru import logger

_TRACK_TAINT_LOCATION_DESCRIPTION = """Use this tool to report a taint location
and its associated path constraint.

You must:
1. Specify the exact file path and line number of the taint location
2. Extract the conditional expression that affects the taint flow
3. Describe how this constraint affects the path from source to sink
4. Convert to SMT-LIB format if it's a formal constraint

## Constraint Types
- **source**: Where taint originates (input, file read, etc.)
- **path_constraint**: Conditional that must be satisfied for taint to continue flowing
- **sink**: The vulnerability point where tainted data reaches

## Examples

### Example 1: Source input
```
Location: upload.c:249
Type: source
Constraint: "User input is read via fgets()"
Path impact: Taint originates here with no initial constraints
```

### Example 2: Path validation constraint
```
Location: upload.c:271
Type: path_constraint
Constraint: "strlen(input) > 0 && strlen(input) < 100"
Path impact: This constraint MUST be satisfied for taint to reach the sink
SMT-LIB: (and (> len 0) (< len 100))
```

### Example 3: Branch selection
```
Location: upload.c:335
Type: path_constraint
Constraint: "upload_type == 1"
Path impact: Only when this condition holds does the path lead to the sink
SMT-LIB: (= upload_type 1)
```

### Example 4: Sink precondition
```
Location: upload.c:339
Type: sink
Constraint: "buffer_size >= input_len must be FALSE for vulnerability"
Path impact: This is the sink; vulnerability occurs when precondition is NOT met
SMT-LIB: (< buffer_size input_len)
```

IMPORTANT: Focus on what constraints must be satisfied for the taint flow to
reach the sink successfully. The goal is to identify the path conditions
that enable the vulnerability."""

TrackTaintLocationTool = ChatCompletionToolParam(
    type="function",
    function=ChatCompletionToolParamFunctionChunk(
        name="track_taint_location",
        description=_TRACK_TAINT_LOCATION_DESCRIPTION,
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Source file path (e.g., 'upload.c')",
                },
                "line": {
                    "type": "integer",
                    "description": "Line number of taint location",
                },
                "constraint_type": {
                    "type": "string",
                    "enum": ["source", "path_constraint", "sink"],
                    "description": "Type of constraint at this location",
                },
                "constraint": {
                    "type": "string",
                    "description": "Natural language description of the constraint",
                },
                "smtlib": {
                    "type": "string",
                    "description": "SMT-LIB format of the constraint",
                },
                "path_impact": {
                    "type": "string",
                    "description": "How this constraint affects the path from source to sink",
                },
            },
            "required": [
                "file_path", "line", "constraint_type",
                "constraint", "path_impact"
            ],
        },
    ),
)


def process_track_taint_location(
    file_path: str,
    line: int,
    constraint_type: str,
    constraint: str,
    path_impact: str,
    smtlib: Optional[str] = None,
) -> tuple[str, dict]:
    """
    Process taint location tracking.

    Returns:
        (observation message, location data dict)
    """
    if not file_path:
        return "Error: file_path is required.", {}
    if not isinstance(line, int) or line < 1:
        return "Error: line must be a positive integer.", {}
    if constraint_type not in ["source", "path_constraint", "sink"]:
        return "Error: type must be 'source', 'path_constraint', or 'sink'.", {}
    if not constraint:
        return "Error: constraint description is required.", {}
    if not path_impact:
        return "Error: path_impact is required.", {}

    location_data = {
        "file_path": file_path,
        "line": line,
        "constraint_type": constraint_type,
        "constraint": constraint,
        "smtlib": smtlib,
        "path_impact": path_impact
    }

    logger.info(f"Tracked taint location: {file_path}:{line} ({constraint_type})")

    return (
        f"Successfully tracked taint location at {file_path}:{line} "
        f"(type: {constraint_type}).\n"
        f"Constraint: {constraint}\n"
        f"Path impact: {path_impact}\n"
        f"SMT-LIB: {smtlib if smtlib else 'N/A'}",
        location_data
    )