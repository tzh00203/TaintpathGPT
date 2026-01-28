import os
import json
import subprocess
import re
import sys
from collections import defaultdict

ROOT_PATH = "/data_hdd/tzh24/zgc4/projects/tools/NS-IoT/"

# Add ROOT_PATH to system path for importing
sys.path.append(ROOT_PATH)

# Import necessary models
from src.models.remote_config import *

class Config:
    def __init__(self, codeql_result_path, config_file=None):
        self.project_root = ROOT_PATH
        self.database_path = ""
        self.database_name = ""
        self.code_input = ""
        self.input_encoding = ""
        self.output_encoding = ""
        self.ai_url = ""
        self.api_key = ""
        self.log_path = ""
        self.projects = ""
        self.targets = ""
        self.target_func_list = ""
        self.entry_func_dict = ""
        self.ext_info = ""
        self.mode = 0
        self.codeql_result_path = codeql_result_path
        self.func_snippets = {}  # key="file:func", value={"file": ..., "name": ..., "start": ..., "end": ...}

        if config_file:
            self.from_file(config_file)

    def maintain_func_snippet(self, file_path: str, func_name: str, start_line: int, end_line: int):
        """Maintain function snippet info"""
        key = f"{file_path}:{func_name}"
        self.func_snippets[key] = {
            "file": file_path,
            "name": func_name,
            "start": start_line,
            "end": end_line
        }

    def get_func_snippet(self, file_path: str, func_name: str):
        """Get function snippet info"""
        key = f"{file_path}:{func_name}"
        return self.func_snippets.get(key)

    def find_func_by_line(self, file_path: str, line: int):
        """Find function by line number"""
        for key, info in self.func_snippets.items():
            if info["file"] == file_path and info["start"] <= line <= info["end"]:
                return info
        return None

    def from_file(self, config_file: str):
        """Initialize configuration from a file."""
        with open(config_file, 'r', encoding="utf-8") as f:
            config_dict = json.load(f)

        self.database_path = os.path.join(self.project_root, config_dict['database_path']).replace("\\", "/")
        self.database_name = config_dict['database_name']
        self.code_input = config_dict['code_input']
        self.input_encoding = config_dict['input_encoding']
        self.output_encoding = config_dict['output_encoding']
        self.ai_url = config_dict['ai_url']
        self.api_key = config_dict['api_key']
        self.log_path = os.path.join(self.database_path, "llm_log").replace("\\", "/")
        self.projects = os.path.join(self.project_root, "project").replace("\\", "/")
        self.targets = os.path.join(self.project_root, "targets").replace("\\", "/")
        self.target_func_list = config_dict['target_func_list']
        self.entry_func_dict = config_dict['entry_func_dict']
        self.ext_info = config_dict['ext_info']
        self.mode = config_dict['mode']

    def ensure_directory(self):
        """Ensure necessary directories exist."""
        os.makedirs(self.database_path, exist_ok=True)
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(self.projects, exist_ok=True)
        os.makedirs(self.targets, exist_ok=True)

    def gen_ast_files(self):
        """Generate AST files for each unique file referenced in the CodeQL results."""
        try:
            with open(self.codeql_result_path, 'r', encoding='utf-8') as file:
                codeql_json = json.load(file)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading CodeQL result file: {e}")
            return []

        paths_list = codeql_json.get("results", [])[0].get("results", [])
        files_list = self._extract_files(paths_list)

        ast_pre = []
        for file_path in files_list:
            full_file_path = os.path.join(ROOT_PATH, "test", "test_src", file_path)
            ast_file_path = full_file_path.replace(".cpp", ".ast").replace(".c", ".ast")
            self._run_clang(full_file_path, ast_file_path)
            ast_pre.append((file_path, ast_file_path))
        return ast_pre

    def _extract_files(self, paths_list):
        """Extract unique file paths from CodeQL results."""
        files_list = set()
        for path_tmp in paths_list:
            for data_flow_tmp in path_tmp.get("data_flow", []):
                for step in data_flow_tmp.get("steps", []):
                    file_path = step.get("file")
                    if file_path:
                        files_list.add(file_path)
        return list(files_list)

    def _run_clang(self, file_path, ast_path):
        """Run clang to generate AST for a given file."""
        clang_cmd = ["clang", "-Xclang", "-ast-dump", "-fsyntax-only", "-ferror-limit=100", file_path]
        try:
            with open(ast_path, "w") as ast_file:
                subprocess.run(clang_cmd, stdout=ast_file, stderr=subprocess.DEVNULL, text=True, check=True)
        except subprocess.CalledProcessError as e:
            # print(f"Error running clang on {file_path}: {e.stderr}")
            pass

    def gen_func_pairs(self):
        """Generate function pairs based on SARIF results and AST analysis."""
        def parse_functions_from_ast(ast_file):
            """Parse functions from the AST dump generated by clang."""
            functions = []
            patterns = [
                r'^[|-]?FunctionDecl[^<]*<[^:]*\.c:(\d+):[^,]*,\s*line:(\d+):[^>]*>[^>]*used\s+(\w+)\s',
                r'^[|-]?FunctionDecl[^<]*<[^:]*\.c:(\d+):[^,]*,\s*line:(\d+):[^>]*>[^>]*\s+(\w+)\s+\'',
                r'\.c:(\d+):[^,]*,\s*line:(\d+):[^>]*>.*?(?:used\s+)?(\w+)\s+\'',
            ]
            with open(ast_file, "r", errors="ignore") as f:
                for line in f:
                    if "FunctionDecl" in line:
                        match = None
                        for pattern in patterns:
                            match = re.search(pattern, line)
                            if match:
                                break
                        if match:
                            functions.append({
                                "name": match.group(3),
                                "start": int(match.group(1)),
                                "end": int(match.group(2)),
                            })
                            self.maintain_func_snippet(
                                ast_file.replace(".ast", ".c"),
                                match.group(3),
                                int(match.group(1)),
                                int(match.group(2))
                            )
                            
            return functions

        def extract_locations_from_sarif(sarif_json):
            """Extract locations from the SARIF JSON, including main locations and data flow steps."""
            locations = list()
            path_locations = dict()
            for run in sarif_json.get("results", []):
                for result in run.get("results", []):
                    for i, df in enumerate(result.get("data_flow", [])):
                        path_str = "PATH " + str(i+1)
                        for step in df.get("steps", []):
                            file = step.get("file")
                            line = step.get("line")
                            if file and line:
                                if (len(locations) > 0 and (file, line) != locations[-1]) or locations == []:
                                    locations.append((file, line))
                        path_locations[path_str] = locations.copy()
                        locations.clear()
            return path_locations

        def find_function_for_line(functions, line):
            """Find the function corresponding to a line number."""
            for func in functions:
                if func["start"] <= line <= func["end"]:
                    return func["name"]
            return "<global>"

        def analyze(sarif_path, ast_map):
            """Main function to analyze SARIF results and match lines to functions."""
            with open(sarif_path, "r") as f:
                sarif = json.load(f)

            file_to_funcs = {file: parse_functions_from_ast(ast) for file, ast in ast_map.items()}
            path_locations = extract_locations_from_sarif(sarif)
            results = []
            for path_index, locations in path_locations.items():
                results.append({"path": path_index, "locations": []})
                for file, line in locations:
                    if file not in file_to_funcs:
                        continue
                    func = find_function_for_line(file_to_funcs[file], line)
                    results[-1]["locations"].append({
                        "file": file,
                        "line": line,
                        "function": func
                    })
            return results
        ast_pre = self.gen_ast_files()
        sarif_path = self.codeql_result_path
        ast_map = {src: ast for src, ast in ast_pre}
        output = analyze(sarif_path, ast_map)
        print(json.dumps(output, indent=2))
        open(ROOT_PATH + "src/rf_workflow/output/func_pairs.json", "w").write(json.dumps(output, indent=2))


if __name__ == "__main__":
    config = Config("/data_hdd/tzh24/zgc4/projects/tools/NS-IoT/test/parsed_results.json")
    config.gen_func_pairs()