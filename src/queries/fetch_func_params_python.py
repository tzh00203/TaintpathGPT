#!/usr/bin/env python3
"""
Python External API Analysis
Generate CSV results with proper quoting and package name formatting
"""

import ast
import os
import sys
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime

class PythonAPIAnalyzer:
    def __init__(self, project_root: str = None):
        self.excluded_dirs = {'test', 'tests', '__pycache__', '.pytest_cache'}
        self.excluded_files = {'test_', '_test.py', 'conftest.py'}
        self.project_root = project_root
        self.seen_records = set()  # 用于去重的集合
    
    def _get_record_key(self, call_info: Dict[str, Any]) -> tuple:
        """生成记录的唯一标识键（基于前5个属性）"""
        return (
            call_info['callstr'],
            call_info['package'], 
            call_info['clazz'],
            call_info['full_signature'],
            call_info['internal_signature']
        )

    def is_external_call(self, node: ast.Call, file_path: str) -> bool:
        """判断是否为外部调用（排除测试框架等）"""
        filename = os.path.basename(file_path)
        dirname = os.path.basename(os.path.dirname(file_path))
        
        # 排除测试文件和目录
        if any(filename.startswith(prefix) for prefix in self.excluded_files):
            return False
        if dirname in self.excluded_dirs:
            return False
        if 'test' in file_path.lower():
            return False
            
        return True
    
    def get_call_string(self, node: ast.Call) -> str:
        """生成调用字符串，如 'new StringBuilder(...)'"""
        if isinstance(node.func, ast.Name):
            return f"{node.func.id}(...)"
        elif isinstance(node.func, ast.Attribute):
            return f"{node.func.attr}(...)"
        else:
            return "unknown(...)"
    
    def get_package_name(self, file_path: str) -> str:
        """从文件路径提取包名（相对路径）"""
        if self.project_root:
            # 获取相对于项目根目录的路径
            try:
                rel_path = os.path.relpath(os.path.dirname(file_path), self.project_root)
                # 将路径分隔符转换为包分隔符
                package_name = rel_path.replace(os.sep, '.')
                # 如果是当前目录，返回空字符串
                if package_name.startswith("src."):
                    return package_name.replace("src.", "")
                if package_name == '.':
                    return ""
                return package_name
            except ValueError:
                pass
        
        # 如果没有项目根目录或计算失败，使用目录名
        dir_name = os.path.basename(os.path.dirname(file_path))
        return dir_name if dir_name and dir_name != '.' else ""
    
    def get_class_name(self, file_path: str) -> str:
        """从文件名提取类名"""
        filename = os.path.basename(file_path)
        if filename.endswith('.py'):
            return filename[:-3]  # 移除.py扩展名
        return filename
    
    def full_signature(self, func_node: ast.FunctionDef) -> str:
        """生成完整的函数签名"""
        func_name = func_node.name
        params = []
        
        # 处理参数
        for arg in func_node.args.args:
            param_name = arg.arg
            param_type = self._get_annotation_type(arg.annotation) if arg.annotation else "Any"
            params.append(f"{param_type} {param_name}")
        
        # 处理返回值类型
        return_type = self._get_annotation_type(func_node.returns) if func_node.returns else "Any"
        
        return f"{return_type} {func_name}({', '.join(params)})"
    
    def internal_signature(self, func_node: ast.FunctionDef) -> str:
        """生成内部签名（只有参数类型）"""
        func_name = func_node.name
        param_types = []
        
        for arg in func_node.args.args:
            param_type = self._get_annotation_type(arg.annotation) if arg.annotation else "Any"
            param_types.append(param_type)
        
        return f"{func_name}({', '.join(param_types)})"
    
    def _get_annotation_type(self, annotation) -> str:
        """获取类型注解的字符串表示"""
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Attribute):
            return f"{annotation.value.id}.{annotation.attr}"
        elif isinstance(annotation, ast.Subscript):
            return self._get_subscript_type(annotation)
        else:
            return "Any"
    
    def _get_subscript_type(self, node: ast.Subscript) -> str:
        """处理泛型类型如 List[str]"""
        if isinstance(node.value, ast.Name):
            base_type = node.value.id
            if isinstance(node.slice, ast.Name):
                return f"{base_type}[{node.slice.id}]"
        return "Any"
    
    def param_types(self, func_node: ast.FunctionDef) -> str:
        """获取参数类型字符串（分号分隔）"""
        types = []
        for arg in func_node.args.args:
            if arg.annotation:
                types.append(self._get_annotation_type(arg.annotation))
            else:
                types.append("Any")
        return ";".join(types)
    
    def is_static_as_string(self, func_node: ast.FunctionDef) -> str:
        """检查是否为静态方法"""
        for decorator in func_node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == 'staticmethod':
                return "true"
        return "false"
    
    def get_return_type(self, func_node: ast.FunctionDef) -> str:
        """获取返回值类型"""
        if func_node.returns:
            return self._get_annotation_type(func_node.returns)
        return "Any"
    
    def get_docstring(self, func_node: ast.FunctionDef) -> str:
        """获取文档字符串"""
        docstring = ast.get_docstring(func_node) or ""
        # 清理文档字符串，移除换行符
        return docstring.replace('\n', ' ').replace('\r', ' ').strip()
    
    def get_location(self, node, file_path: str) -> str:
        """生成位置字符串"""
        line_start = getattr(node, 'lineno', 0)
        line_end = line_start
        # 简单的位置估算
        col_start = 0
        col_end = len(ast.unparse(node)) if hasattr(ast, 'unparse') else 20
        
        return f"file://{file_path}:{line_start}:{col_start}:{line_end}:{col_end}"
    
    def analyze_file(self, file_path: str) -> List[Dict[str, Any]]:
        """分析单个Python文件"""
        results = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    continue
                    # 检查是否为外部调用
                    if self.is_external_call(node, file_path):
                        # 获取包名（模块名）
                        package_name = ""
                        if isinstance(node.func, ast.Attribute):
                            # 处理属性调用，如 builtins.eval
                            if isinstance(node.func.value, ast.Name):
                                package_name = node.func.value.id  # 提取 builtins
                            elif isinstance(node.func.value, ast.Attribute):
                                # 处理嵌套属性，如 module.submodule.function
                                package_name = self._get_nested_attribute_name(node.func.value)
                        
                        if package_name == "self" or package_name.startswith("self"): continue

                        # 获取调用信息
                        call_info = {
                            'callstr': self.get_call_string(node),
                            'package': package_name,  # 如 "builtins"
                            'clazz': self._get_call_class_name(node),  # 需要实现这个方法
                            'full_signature': self._get_call_signature(node),
                            'internal_signature': self._get_call_func_name(node),
                            'func': self._get_call_func_name(node),
                            'is_static': "false",
                            'file': os.path.basename(file_path),
                            'location': self.get_location(node, file_path),
                            'parameter_types': "",
                            'return_type': "",
                            'doc': ""
                        }
                        # 检查是否已存在相同记录
                        record_key = self._get_record_key(call_info)
                        if record_key not in self.seen_records:
                            self.seen_records.add(record_key)
                            results.append(call_info)
                            print(f"Added unique record: {call_info['callstr']}")
                        else:
                            print(f"Skipped duplicate: {call_info['callstr']}")
                
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # 分析函数定义
                    package_name = self.get_package_name(file_path)
                    class_name = self.get_class_name(file_path)
                    func_name = node.name
                    full_sig = self.full_signature(node)
                    doc_string = self.get_docstring(node)
                    
                    # 生成CSV格式的记录
                    func_info = {
                        'callstr': f"{package_name},{class_name},{func_name},{full_sig},{doc_string}",
                        'package': package_name,
                        'clazz': class_name,
                        'full_signature': full_sig,
                        'internal_signature': self.internal_signature(node),
                        'func': func_name,
                        'is_static': self.is_static_as_string(node),
                        'file': os.path.basename(file_path),
                        'location': self.get_location(node, file_path),
                        'parameter_types': self.param_types(node),
                        'return_type': self.get_return_type(node),
                        'doc': doc_string
                    }
                    
                    # 检查是否已存在相同记录
                    record_key = self._get_record_key(func_info)
                    if record_key not in self.seen_records:
                        self.seen_records.add(record_key)
                        results.append(func_info)
                        print(f"Added unique record: {func_info['callstr']}")
                    else:
                        print(f"Skipped duplicate: {func_info['callstr']}")
                    
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
        
        return results
    
    def _get_call_func_name(self, call_node: ast.Call) -> str:
        """获取调用函数名"""
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr
        else:
            return "unknown"
    
    def analyze_directory(self, directory: str) -> List[Dict[str, Any]]:
        """分析整个目录"""
        all_results = []
        
        for root, dirs, files in os.walk(directory):
            # 跳过测试目录
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
            
            for file in files:
                if file.endswith('.py') and not any(file.startswith(prefix) for prefix in self.excluded_files):
                    file_path = os.path.join(root, file)
                    results = self.analyze_file(file_path)
                    all_results.extend(results)
        
        return all_results

    def save_results_as_csv(self, results: List[Dict[str, Any]], output_dir: str, filename: str = None):
        """保存为包含所有必要列的CSV"""
        os.makedirs(output_dir, exist_ok=True)
        
        if filename is None:
            filename = f"results.csv"
        
        csv_path = os.path.join(output_dir, filename)
        
        # 包含Iris代码期望的所有列
        fieldnames = [
            'package', 'clazz', 'func', 'full_signature', 'doc', 
            'location', 'parameter_types', 'return_type', 'internal_signature',
            'is_static', 'file', 'callstr'
        ]
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            
            for result in results:
                row = {field: result.get(field, "") for field in fieldnames}
                writer.writerow(row)

    def _get_call_func_name(self, call_node: ast.Call) -> str:
        """获取调用函数名"""
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr  # 提取 eval
        else:
            return "unknown"

    def _get_call_class_name(self, call_node: ast.Call) -> str:
        """获取调用所属的类名"""
        # 对于简单的调用，很难准确获取类名
        return ""

    def _get_call_signature(self, call_node: ast.Call) -> str:
        """生成类似Java风格的完整方法签名"""
        func_name = self._get_call_func_name(call_node)
        package_name = ""
        
        if isinstance(call_node.func, ast.Attribute) and isinstance(call_node.func.value, ast.Name):
            package_name = call_node.func.value.id
        
        # 生成参数列表
        params = []
        for i, arg in enumerate(call_node.args):
            param_type = self._infer_argument_type(arg)
            params.append(f"{param_type} p{i}")
        
        # 处理关键字参数
        for i, keyword in enumerate(call_node.keywords, start=len(call_node.args)):
            param_name = keyword.arg or f"p{i}"
            param_type = self._infer_argument_type(keyword.value)
            params.append(f"{param_type} {param_name}")
        
        # 如果没有参数，添加空参数列表
        if not params:
            params_str = ""
        else:
            params_str = ", ".join(params)
        
        # 推断返回类型（在Python中很难准确获取）
        return_type = self._infer_return_type(call_node)
        
        if package_name:
            return f"{return_type} {package_name}.{func_name}({params_str})"
        else:
            return f"{return_type} {func_name}({params_str})"

    def _infer_argument_type(self, arg_node: ast.AST) -> str:
        """推断参数类型"""
        if isinstance(arg_node, ast.Constant):
            if isinstance(arg_node.value, str):
                return "str"
            elif isinstance(arg_node.value, int):
                return "int"
            elif isinstance(arg_node.value, float):
                return "float"
            elif isinstance(arg_node.value, bool):
                return "bool"
            elif arg_node.value is None:
                return "None"
            else:
                return "object"
        
        elif isinstance(arg_node, ast.List):
            return "list"
        elif isinstance(arg_node, ast.Dict):
            return "dict"
        elif isinstance(arg_node, ast.Tuple):
            return "tuple"
        elif isinstance(arg_node, ast.Set):
            return "set"
        elif isinstance(arg_node, ast.Name):
            # 根据变量名推断类型（启发式）
            name = arg_node.id
            if name in {'s', 'str', 'string', 'text'}:
                return "str"
            elif name in {'i', 'n', 'num', 'count', 'index'}:
                return "int"
            elif name in {'f', 'float_val'}:
                return "float"
            elif name in {'b', 'flag', 'is_'}:
                return "bool"
            elif name in {'lst', 'list_', 'items'}:
                return "list"
            elif name in {'d', 'dict_', 'mapping'}:
                return "dict"
            else:
                return "object"
        
        elif isinstance(arg_node, ast.Call):
            return "object"  # 函数调用返回对象
        
        else:
            return "object"

    def _infer_return_type(self, call_node: ast.Call) -> str:
        """推断返回类型"""
        func_name = self._get_call_func_name(call_node)
        
        # 常见函数的返回类型映射
        return_type_map = {
            'eval': 'object',
            'exec': 'None',
            'compile': 'code',
            'open': 'file',
            'len': 'int',
            'str': 'str',
            'int': 'int',
            'float': 'float',
            'list': 'list',
            'dict': 'dict',
            'append': 'None',
            'update': 'None',
            'get': 'object',
            'pop': 'object'
        }
        
        return return_type_map.get(func_name, "object")

    def _get_nested_attribute_name(self, node: ast.Attribute) -> str:
        """处理嵌套属性，如 module.submodule.function"""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return '.'.join(reversed(parts))


def main():
    if len(sys.argv) != 3:
        print("Usage: python api_analyzer.py <source_directory> <output_directory>")
        print("Example: python api_analyzer.py /path/to/python/project /path/to/results")
        sys.exit(1)
    
    source_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    if not os.path.exists(source_dir):
        print(f"Source directory {source_dir} does not exist")
        sys.exit(1)
    
    # 使用源目录作为项目根目录来计算相对包名
    analyzer = PythonAPIAnalyzer(project_root=source_dir)
    print(f"Analyzing Python code in: {source_dir}")
    results = analyzer.analyze_directory(source_dir)
    
    print(f"Analysis completed. Found {len(results)} results.")
    
    # 保存结果为CSV格式
    analyzer.save_results_as_csv(results, output_dir)

if __name__ == "__main__":
    main()