"""
This agent analyzes taint flow paths using LLM and generates symbolic constraints.
Extracts path constraints from source to sink for z3 solver.
"""

from collections.abc import Callable
from xml.sax.saxutils import unescape

from loguru import logger

from common import (
    ExampleUserInput,
    Instructions,
    parse_tool_arguments,
    wrap_between_tags,
)
from agents.tools import (
    BatchTool,
    FinishPathAnalysisTool,
    GeneratePathConstraintsTool,
    ThinkingTool,
    TrackTaintLocationTool,
    process_finish_path_analysis,
    process_generate_path_constraints,
    process_thinking_tool,
    process_track_taint_location,
)
from utils.data_structures import MessageThread
from log import print_ace, print_summarize
from models import common
from models.common import (
    Usage,
    get_usage_input_part,
    get_usage_output_part,
    init_agent_usage_details,
    update_usage_details,
)
from utils.utils import estimate_text_token


SYSTEM_PROMPT = f"""
You are an expert in symbolic execution tasked with analyzing taint flow paths and generating symbolic constraints. You will receive:

1. Taint Path Information: The taint flow path from source to sink, showing:
   - Source: Where taint originates (user input, file read, etc.)
   - Sink: Where tainted data reaches a vulnerable point
   - Intermediate Locations: Code locations where taint flows through
   - Source Code: Actual source code at each location with relevant context

Your task is to analyze the taint flow and generate symbolic constraints that MUST be satisfied for the taint to reach the sink. The path is already determined from CodeQL analysis - you are NOT exploring new paths.

## Key Concept
- Focus on PATH CONSTRAINTS: What conditions must hold for taint to flow from source to sink?
- The constraints describe: IF taint reaches sink, THEN these conditions must hold
- Your goal is to produce SMT-LIB constraints that a z3 solver can use

## Workflow

1. Analyze Taint Flow: Use the `{ThinkingTool['function']['name']}` tool to reason about:
   - How does taint propagate through the code?
   - What conditions affect the taint flow at each location?
   - Which constraints are essential for taint to reach the sink?

2. Track Taint Locations: Use the `{TrackTaintLocationTool['function']['name']}` tool for each location:
   - **source**: Document where taint originates (no constraints usually)
   - **path_constraint**: Extract conditional expressions that must be satisfied for taint to continue flowing
   - **sink**: Identify the vulnerability point and its precondition (what must be FALSE for vulnerability)

3. Generate Complete Path Constraints: Use the `{GeneratePathConstraintsTool['function']['name']}` tool to:
   - Combine all tracked constraints into a unified path description
   - Convert C conditions to SMT-LIB format
   - Include variable declarations for all used variables
   - Add source location comments for traceability

4. Finish Analysis: Use the `{FinishPathAnalysisTool['function']['name']}` tool when:
   - All locations in the taint path have been analyzed
   - Complete path constraints have been generated in SMT-LIB format

## SMT-LIB Format Guidelines

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

### Input Taint Path:
```
Path: PATH 1
Locations:
  - upload.c:249 - source (fgets reads user input)
  - upload.c:270 - path constraint (input validation)
  - upload.c:335 - path constraint (branch selection)
  - upload.c:338 - path constraint (buffer size check)
  - upload.c:339 - sink (buffer overflow vulnerability)
```

### Source Code (excerpt):
```c
// upload.c
int main(int argc, char *argv[]) {
    if (argc > 1) {
        char input[256];
        fgets(input, 256, stdin);  // Line 249 - taint source

        int len = strlen(input);
        if (len > 0 && len < 100) {  // Line 270 - path constraint
            int upload_type = parse_upload_type(input);

            if (upload_type == 1) {  // Line 335 - path constraint
                int buffer_size = get_buffer_size();
                if (buffer_size >= len) {  // Line 338 - path constraint
                    sink(input);  // Line 339 - sink (vulnerability point)
                }
            }
        }
    }
}
```

### Expected Path Constraints Output:
```
; Variable declarations
(declare-const len Int)
(declare-const buffer_size Int)
(declare-const upload_type Int)

; Path constraints from source to sink
; upload.c:270 - input validation
(assert (> len 0))
(assert (< len 100))

; upload.c:335 - branch selection
(assert (= upload_type 1))

; upload.c:338 - sink precondition (must FAIL for vulnerability)
(assert (>= buffer_size len))
```

## Important Guidelines

- Focus on constraints that MUST be satisfied for the taint path
- The constraints describe the COMPLETE path conditions from source to sink
- You are analyzing a FIXED path, not exploring alternatives
- Generate SMT-LIB that can be directly fed to z3 solver
- Be precise and unambiguous in constraint specifications
- Use source code comments to reference specific lines when needed
"""

TAINT_PATH_EXAMPLE = """
{
  "path": "PATH 1",
  "locations": [
    {
      "file": "upload.c",
      "line": 249,
      "function": "main"
    },
    {
      "file": "upload.c",
      "line": 271,
      "function": "main"
    },
    {
      "file": "upload.c",
      "line": 335,
      "function": "main"
    },
    {
      "file": "upload.c",
      "line": 338,
      "function": "main"
    },
    {
      "file": "upload.c",
      "line": 339,
      "function": "main"
    }
  ]
}
"""

SOURCE_CODE_EXAMPLE = """
```c
// upload.c (lines 240-350)
int main(int argc, char *argv[]) {
    if (argc > 1) {
        char input[256];
        fgets(input, 256, stdin);  // Line 249: taint source

        int len = strlen(input);
        if (len > 0 && len < 100) {  // Line 271: path constraint
            int upload_type = parse_upload_type(input);

            if (upload_type == 1) {  // Line 335: path constraint
                int buffer_size = get_buffer_size();
                if (buffer_size >= len) {  // Line 338: path constraint
                    sink(input);  // Line 339: sink (vulnerability)
                }
            }
        }
    }
}
```
"""


CONSTRAINT_GENERATION_TEMPERATURE = 0.0


def _process_single_tool_call(
    function_name: str,
    args: dict,
    state: dict,
) -> str:
    """
    Processes a single tool call within the constraint generation agent.

    Args:
        function_name: The name of the tool function called.
        args: The parsed arguments for the tool call.
        state: A dictionary holding mutable state like tracked locations etc.

    Returns:
        The result message from the tool processing.
    """
    observation = f"Error: Unknown tool function {function_name}"

    if function_name == ThinkingTool["function"]["name"]:
        observation = process_thinking_tool(args.get("reasoning"))

    elif function_name == TrackTaintLocationTool["function"]["name"]:
        file_path = args.get("file_path")
        line = args.get("line")
        constraint_type = args.get("constraint_type")
        constraint = args.get("constraint")
        path_impact = args.get("path_impact")
        smtlib = args.get("smtlib")

        if not file_path:
            observation = "Error: file_path is required."
        elif not isinstance(line, int) or line < 1:
            observation = "Error: line must be a positive integer."
        elif constraint_type not in ["source", "path_constraint", "sink"]:
            observation = "Error: constraint_type must be 'source', 'path_constraint', or 'sink'."
        elif not constraint:
            observation = "Error: constraint description is required."
        elif not path_impact:
            observation = "Error: path_impact is required."
        else:
            observation, location_data = process_track_taint_location(
                file_path, line, constraint_type, constraint, path_impact, smtlib
            )
            state["tracked_locations"].append(location_data)
            logger.info(
                f"Tracked taint location: {file_path}:{line} ({constraint_type})"
            )

    elif function_name == GeneratePathConstraintsTool["function"]["name"]:
        path_id = args.get("path_id")
        smtlib_output = args.get("smtlib_output")
        constraint_summary = args.get("constraint_summary")

        if not path_id:
            observation = "Error: path_id is required."
        elif not smtlib_output:
            observation = "Error: smtlib_output is required."
        else:
            observation, path_data = process_generate_path_constraints(
                path_id, smtlib_output, constraint_summary
            )
            state["generated_constraints"].append(path_data)
            logger.info(f"Generated path constraints for {path_id}")

            observation += (
                f"\n\nNow you can:\n"
                f"1. Review your generated constraints for completeness\n"
                f"2. Finish the current path analysis using `{FinishPathAnalysisTool['function']['name']}` tool"
            )

    elif function_name == FinishPathAnalysisTool["function"]["name"]:
        path_id = args.get("path_id")
        source_location = args.get("source_location")
        sink_location = args.get("sink_location")
        constraint_count = args.get("constraint_count")
        has_more_paths = args.get("has_more_paths")

        if not path_id:
            observation = "Error: path_id is required."
        elif not source_location:
            observation = "Error: source_location is required."
        elif not sink_location:
            observation = "Error: sink_location is required."
        elif not isinstance(constraint_count, int) or constraint_count < 0:
            observation = "Error: constraint_count must be a non-negative integer."
        else:
            observation, completion_data = process_finish_path_analysis(
                path_id, source_location, sink_location, constraint_count, has_more_paths
            )
            state["completed_paths"].append(completion_data)
            logger.info(f"Completed analysis for {path_id}")

            if has_more_paths:
                observation += "\n\nPlease continue to the next path."
            else:
                observation += "\n\nAll paths have been analyzed. Great job!"

    elif function_name == BatchTool["function"]["name"]:
        invocations = args.get("invocations", [])
        logger.info(f"Processing batch tool with {len(invocations)} invocations.")
        if len(invocations) == 0:
            observation = f'Error: Empty invocations provided in `{BatchTool["function"]["name"]}`.'
        else:
            invocation_observations = []
            for cnt, invocation in enumerate(invocations):
                inv_func_name = invocation.get("tool_name")
                if not inv_func_name:
                    logger.warning(f"Missing tool_name in invocation: {invocation}")
                    observation = "Invalid invocation: missing tool_name"
                else:
                    parsed_args = parse_tool_arguments({"function": invocation})
                    if parsed_args is None:
                        observation = (
                            f"Failed to parse arguments for tool `{inv_func_name}`"
                        )
                    else:
                        observation = _process_single_tool_call(
                            inv_func_name,
                            parsed_args,
                            state,
                        )
                    invocation_observations.append((cnt, inv_func_name, observation))

            observation = (
                "\n\n".join(
                    f"{cnt+1}. Tool `{inv_func_name}` result:\n{observation}"
                    for cnt, inv_func_name, observation in invocation_observations
                )
                if len(invocation_observations) > 0
                else invocation_observations[0][2]
            )

    else:
        observation = f"Error: Unknown tool `{function_name}`"

    return observation


def _process_tool_call(
    response_tool_calls: list[dict],
    state: dict,
    process_single_tool_call_func: Callable,
) -> tuple[list[tuple[str, str, str]], list[str]]:

    batched_observations = []
    called_tools = []

    for tool_call in response_tool_calls:
        function_name = tool_call.get("function").get("name")
        tool_call_id = tool_call.get("id")
        called_tools.append(function_name)

        logger.info(f"Constraint generation agent calling tool `{function_name}`")

        # Parse arguments
        args = parse_tool_arguments(tool_call)
        if args is None:
            observation = "Failed to parse tool call arguments."
            batched_observations.append((function_name, tool_call_id, observation))
            continue

        # Handle BatchTool or single tool calls
        if function_name == BatchTool["function"]["name"]:
            # Pass batch processing to _process_single_tool_call
            batched_observations = _process_single_tool_call(
                [tool_call], state, process_single_tool_call_func
            )[0]
            called_tools.extend(batched_observations[1])
        else:
            observation = process_single_tool_call_func(
                function_name,
                args,
                state,
            )
            batched_observations.append((function_name, tool_call_id, observation))

    return batched_observations, called_tools


def generate_taint_constraints(
    taint_path: str,
    source_code: str,
    parallel_num: int | None = None,
) -> Generator[
    tuple[
        str,          # path_id
        str,          # source_location
        str,          # sink_location
        int,           # constraint_count
        str,          # smtlib_output
        dict[str, tuple[int, Usage]],  # usage_details
        MessageThread,
    ]
]:
    """
    Generate taint path constraints using LLM analysis.

    Args:
        taint_path: Taint path data (path_id, locations, source, sink)
        source_code: Complete source code for analysis
        parallel_num: Optional number of paths to generate in parallel

    Yields:
        path_id: Path identifier
        source_location: Source location (file:line)
        sink_location: Sink location (file:line)
        constraint_count: Number of constraints extracted
        smtlib_output: SMT-LIB constraints for z3 solver
        usage_details: Usage details accumulated since last yield
        msg_thread: Current message thread
    """
    import json

    # Parse taint path JSON
    try:
        path_data = json.loads(taint_path)
    except json.JSONDecodeError:
        logger.error("Failed to parse taint path JSON")
        return

    path_id = path_data.get("path", "UNKNOWN")
    locations = path_data.get("locations", [])
    source_location = f"{locations[0]['file']}:{locations[0]['line']}"
    sink_location = f"{locations[-1]['file']}:{locations[-1]['line']}"

    # Build message thread
    msg_thread: MessageThread = MessageThread()
    system_prompt = (
        Instructions(instructions=SYSTEM_PROMPT).to_xml()
        + b"\n"
        + ExampleUserInput(
            example_user_input=TAINT_PATH_EXAMPLE
        ).to_xml()
        + b"\n"
        + ExampleUserInput(
            example_user_input=f"Source Code:\n{SOURCE_CODE_EXAMPLE}"
        ).to_xml()
    ).decode()
    system_prompt = unescape(system_prompt)
    msg_thread.add_system(system_prompt)

    # Build user prompt
    user_prompt = f"Taint Path:\n{json.dumps(path_data, indent=2)}\n\n"
    user_prompt += f"Source Code:\n{source_code}"

    msg_thread.add_user(user_prompt)

    print_ace(user_prompt, "Taint Path Constraint Generation")

    finished = False

    # State dictionary to pass mutable state to the helper function
    state = {
        "tracked_locations": [],      # List of tracked locations
        "generated_constraints": [],   # List of generated constraints
        "completed_paths": [],        # List of completed path analyses
        "last_yielded_index": -1,   # Index of the last yielded path
    }

    usage_details = init_agent_usage_details()

    last_call: list[str] = ["INITIAL"]

    initial_prompt_caching_tokens = None

    input_tokens = 0
    newly_added_tokens = 0

    # Main loop - process tool calls until the finish tool is called
    while not finished:

        available_tools = [
            BatchTool,
            ThinkingTool,
            TrackTaintLocationTool,
            GeneratePathConstraintsTool,
            FinishPathAnalysisTool,
        ]

        # Call model with tools support
        response_content, response_tool_calls, usage = common.SELECTED_MODEL.call(
            msg_thread.to_msg(),
            temperature=CONSTRAINT_GENERATION_TEMPERATURE,
            tools=available_tools,
            tool_choice="any" if available_tools else "auto",
            parallel_tool_calls=True,
        )

        newly_added_tokens = 0
        input_tokens = (
            usage.input_tokens + usage.cache_write_tokens + usage.output_tokens
        )

        if initial_prompt_caching_tokens is None:
            initial_prompt_caching_tokens = usage.cache_write_tokens

        logger.info(
            "Constraint generation agent response: {}",
            response_content,
        )

        update_usage_details(usage_details, last_call, get_usage_input_part(usage))
        last_call = []

        # Add model's response to the message thread
        msg_thread.add_model(response_content, response_tool_calls)

        # Process tool calls
        if response_tool_calls:

            # Process tool calls
            batched_observations, last_call = _process_tool_call(
                response_tool_calls, state, _process_single_tool_call
            )

            # Add all observations to the message thread
            for i, (func_name, call_id, obs) in enumerate(batched_observations):
                msg_thread.add_tool(
                    obs,
                    name=func_name,
                    tool_call_id=call_id,
                )
                newly_added_tokens += estimate_text_token(obs)

            # Check if current path is complete
            if state["completed_paths"]:
                finished = True
                break

        else:
            # No tool calls - prompt model to use tools
            _msg = "Please use the provided tools to achieve the goal."
            msg_thread.add_user(_msg)
            newly_added_tokens += estimate_text_token(_msg)
            last_call = ["non_tool"]

        update_usage_details(usage_details, last_call, get_usage_output_part(usage))

        # Check if we have a completed path to yield
        for i in range(state["last_yielded_index"] + 1, len(state["completed_paths"])):
            logger.info(f"Yielding path {i+1}")
            path_data = state["completed_paths"][i]

            # Create a copy of the current usage_details to yield
            yield_usage_details = {k: v for k, v in usage_details.items()}

            # Reset accumulated usage for next yield
            usage_details = init_agent_usage_details()

            state["last_yielded_index"] = i

            yield (
                path_data.get("path_id", "UNKNOWN"),
                source_location,
                sink_location,
                len(state["tracked_locations"]),
                path_data.get("smtlib_output", ""),
                yield_usage_details,
                msg_thread.copy(),
            )

        if parallel_num is not None:
            if state["last_yielded_index"] + 1 >= parallel_num:
                logger.info(
                    f"Reached the maximum number ({parallel_num}) of paths, finishing..."
                )
                finished = True

    # Create a summary of all paths analyzed
    final_output = "\nEXPLORATION SUMMARY:\n"
    for i, path_data in enumerate(state["completed_paths"]):
        final_output += f"\n--- Path {i+1} ---\n"
        final_output += f"PATH ID: {path_data.get('path_id', 'UNKNOWN')}\n"
        final_output += f"SOURCE: {source_location}\n"
        final_output += f"SINK: {sink_location}\n"
        final_output += f"CONSTRAINTS GENERATED: {len(state['tracked_locations'])}\n"

    print_summarize(final_output, "Taint Path Constraint Generation Results")

    logger.debug(
        "Taint path constraint generation completed. Message thread: {}",
        msg_thread,
    )