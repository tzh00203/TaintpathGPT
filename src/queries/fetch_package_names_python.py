import os
import pandas as pd
import re
import argparse
from pathlib import Path

class PythonPackageExcluder:
    def __init__(self, project_source_path, output_path):
        self.project_source_path = project_source_path
        self.output_file = output_path
        # os.makedirs(output_path, exist_ok=True)
    
    def generate_package_exclusion_list(self):
        """生成Python项目的包排除列表"""
        print(f"Analyzing Python project at: {self.project_source_path}")
        
        # 方法1: 基于目录结构识别包
        dir_packages = self._find_packages_from_directory()
        print(f"Found {len(dir_packages)} packages from directory structure")
        
        # 方法2: 基于导入分析识别包
        import_packages = self._find_packages_from_imports()
        print(f"Found {len(import_packages)} packages from import analysis")
        
        # 合并结果
        all_packages = sorted(list(set(dir_packages + import_packages)))
        print(f"Total unique packages found: {len(all_packages)}")
        
        # 写入文件
        exclusion_file_path = self.output_file
        with open(exclusion_file_path, 'w') as f:
            for package in all_packages:
                f.write(f"{package}\n")
        
        print(f"Exclusion list saved to: {exclusion_file_path}")
        return all_packages
    
    def _find_packages_from_directory(self):
        """基于目录结构识别Python包"""
        package_list = []
        
        try:
            for root, dirs, files in os.walk(self.project_source_path):
                # 跳过隐藏目录和虚拟环境
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'venv', 'env', 'virtualenv']]
                
                # 检查是否包含__init__.py（Python包标志）
                if '__init__.py' in files:
                    rel_path = os.path.relpath(root, self.project_source_path)
                    if rel_path == '.':
                        # 项目根目录本身就是包
                        package_name = self._get_project_name()
                    else:
                        # 将路径转换为Python包格式
                        package_name = rel_path.replace(os.sep, '.')
                    package_list.append(package_name)
                
                # 检查setup.py或pyproject.toml来识别顶级包
                if 'setup.py' in files or 'pyproject.toml' in files:
                    top_package = self._parse_top_level_package(root)
                    if top_package and top_package not in package_list:
                        package_list.append(top_package)
                        
        except Exception as e:
            print(f"Error in directory analysis: {e}")
        
        return package_list
    
    def _find_packages_from_imports(self):
        """通过分析导入语句识别项目包"""
        project_packages = set()
        
        try:
            for root, dirs, files in os.walk(self.project_source_path):
                # 跳过隐藏目录和虚拟环境
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'venv', 'env', 'virtualenv']]
                
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                            
                            # 分析导入语句
                            imports = self._extract_imports(content)
                            
                            # 检查导入的包是否在项目目录中
                            for imported_pkg in imports:
                                if self._is_project_package(imported_pkg):
                                    project_packages.add(imported_pkg)
                                    
                        except Exception as e:
                            print(f"Error reading {file_path}: {e}")
                            
        except Exception as e:
            print(f"Error in import analysis: {e}")
        
        return sorted(list(project_packages))
    
    def _extract_imports(self, content):
        """从Python代码中提取导入的包名"""
        imports = set()
        
        # 匹配 import package 格式
        import_pattern = r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)'
        import_matches = re.findall(import_pattern, content, re.MULTILINE)
        
        # 匹配 from package import 格式
        from_pattern = r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_.]+)\s+import'
        from_matches = re.findall(from_pattern, content, re.MULTILINE)
        
        # 收集所有导入的包（只取顶级包名）
        for match in import_matches:
            top_package = match.split('.')[0]
            imports.add(top_package)
        
        for match in from_matches:
            top_package = match.split('.')[0]
            imports.add(top_package)
        
        return imports
    
    def _is_project_package(self, package_name):
        """检查包名是否对应项目中的目录"""
        # 检查包路径是否存在
        pkg_path = os.path.join(self.project_source_path, package_name.replace('.', os.sep))
        if os.path.exists(pkg_path):
            return True
        
        # 检查是否有对应的目录（即使没有__init__.py）
        possible_dirs = [
            os.path.join(self.project_source_path, package_name),
            os.path.join(self.project_source_path, package_name.replace('.', os.sep))
        ]
        
        for dir_path in possible_dirs:
            if os.path.isdir(dir_path):
                return True
        
        return False
    
    def _get_project_name(self):
        """获取项目名称"""
        # 尝试从setup.py获取
        setup_py = os.path.join(self.project_source_path, 'setup.py')
        if os.path.exists(setup_py):
            try:
                with open(setup_py, 'r') as f:
                    content = f.read()
                match = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", content)
                if match:
                    return match.group(1)
            except:
                pass
        
        # 尝试从pyproject.toml获取
        pyproject_toml = os.path.join(self.project_source_path, 'pyproject.toml')
        if os.path.exists(pyproject_toml):
            try:
                with open(pyproject_toml, 'r') as f:
                    content = f.read()
                match = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", content)
                if match:
                    return match.group(1)
            except:
                pass
        
        # 使用目录名
        return os.path.basename(os.path.abspath(self.project_source_path))
    
    def _parse_top_level_package(self, dir_path):
        """解析顶级包名"""
        return self._get_project_name()

def filter_external_apis(api_candidates_csv, project_packages_file, output_csv=None):
    """过滤外部API，排除项目自身的包"""
    
    # 读取API候选
    api_candidates = pd.read_csv(api_candidates_csv)
    print(f"Total API candidates: {len(api_candidates)}")
    
    # 读取项目包列表
    with open(project_packages_file, 'r') as f:
        project_packages = set(line.strip() for line in f if line.strip())
    
    print(f"Project packages to exclude: {len(project_packages)}")
    print("Sample project packages:", list(project_packages)[:5])
    
    # 过滤掉项目自身的包
    if 'package' in api_candidates.columns:
        external_apis = api_candidates[~api_candidates['package'].isin(project_packages)]
        print(f"External APIs after filtering: {len(external_apis)}")
        
        # 保存结果
        if output_csv:
            external_apis.to_csv(output_csv, index=False)
            print(f"Filtered APIs saved to: {output_csv}")
        
        return external_apis
    else:
        print("Error: 'package' column not found in API candidates CSV")
        return api_candidates

def main():
    parser = argparse.ArgumentParser(description='Generate Python package exclusion list and filter external APIs')
    parser.add_argument('project_path', help='Path to Python project source code')
    # parser.add_argument('output-dir', required=True, help='Output directory for results')
    parser.add_argument('--api-candidates', help='Path to API candidates CSV file (optional)')
    parser.add_argument('--filtered-output', help='Output path for filtered APIs (optional)')
    
    args = parser.parse_args()
    iris_root = Path(__file__).parent.parent.parent
    output_file = iris_root / "data" / "package-names" / f"{args.project_path}.txt"
    src_dir = iris_root / "data" / "project-sources" / f"{args.project_path}/"
    
    # 生成包排除列表
    excluder = PythonPackageExcluder(src_dir, output_file)
    packages = excluder.generate_package_exclusion_list()
    
    # 如果提供了API候选文件，进行过滤
    if args.api_candidates and os.path.exists(args.api_candidates):
        project_packages_file = output_file
        filter_external_apis(args.api_candidates, project_packages_file, args.filtered_output)

if __name__ == "__main__":
    main()