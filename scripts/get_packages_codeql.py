import subprocess
import sys
import re
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
import sys
sys.path.append(str(Path(__file__).parent.parent))
from src.config import PROJECT_SOURCE_CODE_DIR

def run_codeql_query(db_path, query_path):
    try:
        subprocess.run(
            ["codeql", "query", "run", "--database", str(db_path), 
             "--output=results.bqrs", str(query_path)],
            check=True, capture_output=True, text=True
        )
        result = subprocess.run(
            ["codeql", "bqrs", "decode", "--format=csv", "results.bqrs"],
            capture_output=True, text=True, check=True
        )
        packages = set()
        rows = result.stdout.strip().split("\n")[1:]
        for line in rows:
            parts = line.split(",")
            if len(parts) >= 1:
                pkg_name = parts[0].strip().strip('"')
                packages.add(pkg_name)
        return packages
    except subprocess.CalledProcessError as e:
        print(f"Error running CodeQL command: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return set()

def find_maven_group_ids(project_dir):
    """
    递归查找项目中的所有 pom.xml 文件，并提取 groupId 和 artifactId 信息
    """
    group_ids = set()

    # 递归查找所有 pom.xml 文件
    for pom_path in Path(project_dir).rglob("pom.xml"):
        try:
            tree = ET.parse(pom_path)
            root = tree.getroot()
            ns = {'mvn': re.findall(r'{(.*)}', root.tag)[0]} if '{' in root.tag else {}
            
            # 提取 <groupId> 和 <artifactId>
            for group_id in root.findall('.//mvn:groupId', ns):
                group_ids.add(group_id.text.strip())
            for artifact_id in root.findall('.//mvn:artifactId', ns):
                group_ids.add(artifact_id.text.strip())
                
        except Exception as e:
            print(f"Error parsing {pom_path}: {e}")
    
    return group_ids

def find_files_in_project(project_dir, extensions=[".java"]):
    """
    查找项目文件夹中的所有指定扩展名的文件，返回文件路径列表
    """
    files = []
    for ext in extensions:
        files.extend(Path(project_dir).rglob(f"*{ext}"))
    return files

def extract_package_from_filepath(file_path, base_dir):
    """
    从文件路径中提取包名，假设文件夹结构与 Java 包结构一致
    """
    package_path = file_path.relative_to(base_dir).parent  # 获取相对于 base_dir 的路径
    package_name = ".".join(package_path.parts)  # 转换路径为包名
    return package_name

def filter_internal_packages(packages, internal_package_prefixes):
    """
    根据前缀过滤出内部包
    """
    internal_packages = []
    
    for pkg_name in packages:
        for prefix in internal_package_prefixes:
            if pkg_name.startswith(prefix):
                internal_packages.append(pkg_name)
                break  # 如果包名匹配多个前缀，停止继续检查
    return internal_packages

def main():
    parser = argparse.ArgumentParser(description="Extract internal packages from a Java project")
    parser.add_argument("project_name", help="Name of the project")
    parser.add_argument("--internal-package", help="Base package name for internal packages (e.g., 'com.example')")
    internal_packages = []
    args = parser.parse_args()
    project_name = args.project_name
    internal_package = args.internal_package
    
    iris_root = Path(__file__).parent.parent
    output_file = iris_root / "data" / "package-names" / f"{project_name}.txt"
    query_path = iris_root / "scripts" / "codeql-queries" / "packages.ql"
    db_path = iris_root / "data" / "codeql-dbs" / project_name
    project_path = Path(PROJECT_SOURCE_CODE_DIR) / project_name
    print(f"Project path: {project_path}")

    # 获取所有从 pom.xml 提取的 Maven 包名（groupId 和 artifactId）
    group_ids = find_maven_group_ids(project_path)
    if not group_ids:
        print("Error: No Maven groupIds or artifactIds found.")
        pass
        # sys.exit(1)
    
    print(f"Detected Maven groupIds/artifactIds: {group_ids}")
    
    # 如果没有提供 internal_package 参数，尝试从路径中推断
    if not internal_package:
        print("Internal package not specified, trying to detect from project files...")
        # source_dir = Path(project_path) / "src" / "main" / "java"
        source_dir = Path(project_path)
        if source_dir.exists():
            files = find_files_in_project(source_dir)

            if files:
                for ii in files:
                    internal_package = extract_package_from_filepath(ii, source_dir)
                    internal_packages.append(internal_package)
            else:
                print("Error: No Java source files found.")
                sys.exit(1)
    
        else:
            print("Error: Source directory not found.")
            sys.exit(1)
    internal_packages = list(set(internal_packages))
    print(f"Detected internal package: {internal_packages}")
    if not internal_packages:
        print("Error: Could not detect internal package name.")
        print("Please specify it with --internal-package (e.g., --internal-package com.example)")
        sys.exit(1) 
    
    # 运行 CodeQL 查询获取所有包名
    print(f"Running CodeQL query for all packages in {project_name}...")
    all_packages = run_codeql_query(db_path, query_path)
    if not all_packages:
        print("No packages found or CodeQL query failed.")
        return
    print(f"Found {len(all_packages)} total packages.")
    
    # 过滤出内部包
    internal_packages = filter_internal_packages(all_packages, group_ids)
    excluded_packages = [pkg for pkg in all_packages if pkg not in internal_packages]
    
    print("Excluded packages:", excluded_packages)
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        for package in sorted(internal_packages):
            f.write(f"{package}\n")
    
    print(f"Results written to {output_file}")
    
    Path("results.bqrs").unlink(missing_ok=True)

if __name__ == "__main__":
    main()
