#!/bin/bash

# 传入的参数: CVE 和 lang
if [ $# -ne 2 ]; then
  echo "用法: $0 <CVE编号> <语言>"
  exit 1
fi

CVE=$1
LANG=$2

# 打印开始执行的命令
echo "正在运行任务，CVE: $CVE, 语言: $LANG"

# 运行命令 1: iris_input.py
echo "步骤 1: 运行 iris_input.py"
echo "运行: python3 src/iris_input.py $CVE"
python3 src/iris_input.py "$CVE"
echo "步骤 1 完成"

# 运行命令 2: build_codeql_dbs.py
echo "步骤 2: 运行 build_codeql_dbs.py"
echo "运行: python scripts/build_codeql_dbs.py --project final_${LANG}_0_${CVE}_1.0.0 --language ${LANG}"
python scripts/build_codeql_dbs.py --project "final_${LANG}_0_${CVE}_1.0.0" --language "$LANG"
echo "步骤 2 完成"

# 运行命令 3: get_packages_codeql.py 或 fetch_package_names_python.py
echo "步骤 3: 运行 get_packages_codeql.py 或 fetch_package_names_python.py"
if [ "$LANG" == "java" or "$LANG" == "cpp"]; then
    echo "运行: python3 scripts/get_packages_codeql.py final_${LANG}_0_${CVE}_1.0.0"
    python3 scripts/get_packages_codeql.py "final_${LANG}_0_${CVE}_1.0.0"
elif [ "$LANG" == "python" ]; then
    echo "运行: python3 src/queries/fetch_package_names_python.py final_${LANG}_0_${CVE}_1.0.0"
    python3 src/queries/fetch_package_names_python.py "final_${LANG}_0_${CVE}_1.0.0"
else
    echo "❌ 未知语言: $LANG, 请使用 'java' 或 'python'"
    exit 1
fi
echo "步骤 3 完成"

# 运行命令 4: iris.py
echo "步骤 4: 运行 iris.py"
echo "运行: python src/iris.py --query cwe-022wLLM --run-id test --llm remote_qwen final_${LANG}_0_${CVE}_1.0.0 --language ${LANG} --general"
python src/iris.py --query cwe-022wLLM --run-id test --llm remote_qwen "final_${LANG}_0_${CVE}_1.0.0" --language "$LANG" --general
echo "步骤 4 完成"

# 完成
echo "所有命令已成功运行!"


