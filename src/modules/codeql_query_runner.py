import os
import sys
import subprocess as sp
import pandas as pd
import shutil
import json
import re
import argparse
import numpy as np
import copy
import math
import random

from src.config import CODEQL_DIR
from src.queries import QUERIES

CODEQL = f"{CODEQL_DIR}/codeql"

ENTRY_SCRIPT_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)) + "/../")

class CodeQLQueryRunner:
    def __init__(self, project_output_path, project_codeql_db_path, project_logger, language):
        self.project_output_path = project_output_path
        self.project_codeql_db_path = project_codeql_db_path
        self.project_logger = project_logger
        self.language = language
        self.project_source_path = ENTRY_SCRIPT_DIR.replace("src", "") + "data/project-sources/" + project_codeql_db_path.split("/")[-1]
      

    def run(self, query, target_csv_path=None, suffix=None, dyn_queries={}):
        """
        :param query, is a string that should be a key in the QUERIES dictionary
        :param target_csv_path, is a path where the result csv should be stored to
        :param suffix, ???
        :param dyn_queries, is a dictionary {<name>: <content>} of dyanmically generated queries.
                            The name needs to be ending with a `.ql` or `.qll` extension.
        """
        # 0. Sanity check
        if query not in QUERIES:
            self.project_logger.error(f"  ==> Unknown query `{query}`; aborting"); exit(1)

        # 1. Create the directory in CodeQL's queries path
        suffix_dir = "" if suffix is None else f"/{suffix}"
        codeql_query_dir = f"{self.project_output_path}/myqueries/{query}{suffix_dir}"
        os.makedirs(codeql_query_dir, exist_ok=True)

        # 2. Copy the basic queries and supporting queries to the codeql directory
        for q in QUERIES[query]["queries"]:
            shutil.copy(f"{ENTRY_SCRIPT_DIR}/{q}", f"{codeql_query_dir}/")

        # 3. Write the dynamic queries
        for dyn_query_name, content in dyn_queries.items():
            with open(f"{codeql_query_dir}/{dyn_query_name}", "w") as f:
                f.write(content)

        # 4. Setup the paths
        main_query = QUERIES[query]["queries"][0] if self.language == "java" else ( QUERIES[query]["queries"][1]  )
        main_query_name = main_query.split("/")[-1]
        codeql_query_path = f"{codeql_query_dir}/{main_query_name}"

        query_result_path = f"{self.project_output_path}/{query}{suffix_dir}"
        query_result_bqrs_path = f"{self.project_output_path}/{query}{suffix_dir}/results.bqrs"
        query_result_csv_path = f"{self.project_output_path}/{query}{suffix_dir}/results.csv"
        os.makedirs(query_result_path, exist_ok=True)

        # 5. Run the query and generate result bqrs
        if self.language == "java":
            # 原有的CodeQL查询执行方式
            print([CODEQL, "query", "run", f"--database={self.project_codeql_db_path}", f"--output={query_result_bqrs_path}", "--", codeql_query_path])
            sp.run([CODEQL, "query", "run", f"--database={self.project_codeql_db_path}", f"--output={query_result_bqrs_path}", "--", codeql_query_path])
        else:  # python
            # Python脚本执行方式
            project_source_path = self.project_source_path  # 需要确保这个属性存在，指向项目源代码目录
            python_command = ["python", codeql_query_path, project_source_path, query_result_path]
            print(python_command)
            sp.run(python_command)
            
            # 对于Python脚本，可能需要手动创建结果文件或检查脚本输出
            # 如果Python脚本直接生成CSV，可以跳过BQRS步骤
            python_result_csv = f"{query_result_path}/results.csv"  # 假设Python脚本生成这个文件
            
            # 如果Python脚本没有生成标准结果文件，可能需要特殊处理
            if not os.path.exists(python_result_csv):
                # 检查是否有其他可能的结果文件
                result_files = [f for f in os.listdir(query_result_path) if f.endswith('.csv')]
                if result_files:
                    python_result_csv = f"{query_result_path}/{result_files[0]}"
                else:
                    self.project_logger.error(f"  ==> Python script did not generate expected result file for `{query}`; aborting")
                    exit(1)

        # 6. Decode the query (仅适用于Java/CodeQL)
        if self.language == "java":
            sp.run([CODEQL, "bqrs", "decode", query_result_bqrs_path, "--format=csv", f"--output={query_result_csv_path}"])
            if not os.path.exists(query_result_csv_path):
                self.project_logger.error(f"  ==> Failed to decode result bqrs from `{query}`; aborting")
                exit(1)
        else:  # python
            # 对于Python，直接使用脚本生成的CSV文件
            query_result_csv_path = python_result_csv
            if not os.path.exists(query_result_csv_path):
                self.project_logger.error(f"  ==> Python script failed to generate results for `{query}`; aborting")
                exit(1)

        # 7. Copy the query out
        if target_csv_path is not None:
            shutil.copy(query_result_csv_path, target_csv_path)
