"""
Test script for taint path constraint generation agent.
"""

import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.agent_PCsolver import generate_taint_constraints


def main():
    ROOT_PATH = "/data_hdd/tzh24/zgc4/projects/tools/NS-IoT/"

    # Mock taint path data
    taint_path = """
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
          "line": 270,
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

    # Mock source code
    source_code = """
    // upload.c (lines 240-350)
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
                        process_upload(input);  // Line 339 - sink
                    }
                }
            }
        }
    }
    """

    # Mock func snippets
    func_snippets = {
        "upload.c:main": {
            "file": "upload.c",
            "name": "main",
            "start": 240,
            "end": 350
        }
    }

    print("=" * 60)
    print("Testing Taint Path Constraint Generation Agent")
    print("=" * 60)

    # Call the agent generator
    print("\nCalling agent with taint path and source code...")
    print(f"Source: {taint_path[:100]}...")
    print(f"Source code length: {len(source_code)} bytes")

    path_constraints = []
    for (
        path_id,
        source_location,
        sink_location,
        constraint_count,
        smtlib_output,
        usage_details,
        msg_thread,
    ) in generate_taint_constraints(taint_path, source_code):
        print(f"\n{'=' * 40}")
        print(f"Path ID: {path_id}")
        print(f"Source: {source_location}")
        print(f"Sink: {sink_location}")
        print(f"Constraints generated: {constraint_count}")

        print(f"\n{'=' * 40}")
        print("SMT-LIB Output:")
        print("-" * 40)
        print(smtlib_output)
        print("-" * 40)

        path_constraints.append({
            "path_id": path_id,
            "source_location": source_location,
            "sink_location": sink_location,
            "constraint_count": constraint_count,
            "smtlib_output": smtlib_output,
        })

    print("\n" + "=" * 60)
    print(f"Analysis complete! Processed {len(path_constraints)} path(s)")
    print("=" * 60)

    return path_constraints


if __name__ == "__main__":
    main()