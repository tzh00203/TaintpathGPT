"""
Tool for generating complete path constraints in SMT-LIB format.
"""

from typing import Optional

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk
from loguru import logger

_GENERATE_PATH_CONSTRAINTS_DESCRIPTION = """Use this tool to generate complete path constraints in SMT-LIB format for z3 solver.

You must:
1. Combine all tracked constraints into a single path constraint
2. Convert C conditions to proper SMT-LIB syntax
3. Include variable declarations
4. Ensure constraints are solvable and complete

## SMT-LIB Format Requirements

1. **Variable Declarations**:
   - All variables used in constraints must be declared
   - Use appropriate types (Int, Real, Bool)
   - Example: `(declare-const len Int)`

2. **Assert Statements**:
   - Each constraint wrapped in `(assert ...)`
   - Use SMT-LIB operators:
     - Comparison: `>`, `<`, `>=`, `<=`, `=`, `distinct`
     - Logical: `and`, `or`, `not`, `=>`, `ite`
   - Example: `(assert (and (> len 0) (< len 100)))`

3. **Source Comments**:
   - Include source location comments: `; file.c:line`
   - Helps trace back to original code

## Complete Example
```
; Variable declarations
(declare-const len Int)
(declare-const buffer_size Int)
(declare-const upload_type Int)

; Source constraint
; upload.c:249
(assert (> len 0))

; Intermediate validation
; upload.c:271
(assert (< len 100))

; Branch condition
; upload.c:335
(assert (= upload_type 1))

; Sink precondition
; upload.c:338
(assert (>= buffer_size len))
```

Output the complete SMT-LIB constraints for the current path."""

GeneratePathConstraintsTool = ChatCompletionToolParam(
    type="function",
    function=ChatCompletionToolParamFunctionChunk(
        name="generate_path_constraints",
        description=_GENERATE_PATH_CONSTRAINTS_DESCRIPTION,
        parameters={
            "type": "object",
            "properties": {
                "path_id": {
                    "type": "string",
                    "description": "Path identifier (e.g., 'PATH 1')",
                },
                "smtlib_output": {
                    "type": "string",
                    "description": "Complete SMT-LIB constraints for z3 solver",
                },
                "constraint_summary": {
                    "type": "string",
                    "description": "Summary of constraints extracted for this path",
                },
            },
            "required": ["path_id", "smtlib_output"],
        },
    ),
)


def process_generate_path_constraints(
    path_id: str,
    smtlib_output: str,
    constraint_summary: Optional[str] = None
) -> tuple[str, dict]:
    """
    Process path constraint generation.

    Returns:
        (observation message, path constraint dict)
    """
    if not path_id:
        return "Error: path_id is required.", {}
    if not smtlib_output:
        return "Error: smtlib_output is required.", {}

    path_data = {
        "path_id": path_id,
        "smtlib_output": smtlib_output,
        "constraint_summary": constraint_summary
    }

    logger.info(f"Generated path constraints for {path_id}")

    return (
        f"Successfully generated SMT-LIB constraints for {path_id}.\n"
        f"Summary: {constraint_summary if constraint_summary else 'N/A'}\n\n"
        f"You can now:\n1. Finish current path analysis using finish_path_analysis tool\n"
        f"2. Continue to the next path if there are more paths",
        path_data
    )