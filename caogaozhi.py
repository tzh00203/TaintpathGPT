import ast
import os

def analyze_python_files(directory_path):
    results = []
    
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, directory_path)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    tree = ast.parse(content)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, (
                            # ast.FunctionDef, 
                            # ast.AsyncFunctionDef, 
                            ast.ClassDef)):
                            results.append({
                                'name': node.name,
                                'file': relative_path,
                                'start_line': node.lineno,
                                'end_line': get_end_line(node, content)
                            })
                            
                except (SyntaxError, UnicodeDecodeError) as e:
                    print(f"Error parsing {file_path}: {e}")
    
    return results

def get_end_line(node, content):
    """获取节点结束行号"""
    if hasattr(node, 'end_lineno') and node.end_lineno:
        return node.end_lineno
    
    # 如果没有end_lineno属性，通过decorator_list计算
    lines = content.split('\n')
    start_line = node.lineno - 1  # 转为0-based索引
    
    # 简单估算：查找下一个相同或更低缩进级别的行
    start_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
    
    for i in range(start_line + 1, len(lines)):
        current_line = lines[i]
        if not current_line.strip():  # 空行跳过
            continue
            
        current_indent = len(current_line) - len(current_line.lstrip())
        if current_indent <= start_indent and current_line.strip():
            return i  # 返回1-based行号
    
    return len(lines)  # 如果没有找到，返回文件最后一行

# 使用示例
if __name__ == "__main__":
    project_path = "/data_hdd/tzh24/zgc4/projects/tools/iris/data/project-sources/match_python_8_CVE-2025-54892_1.0.0"
    functions_and_classes = analyze_python_files(project_path)
    
    for item in functions_and_classes:
        print(f"Name: {item['name']}")
        print(f"File: {item['file']}")
        print(f"Lines: {item['start_line']}-{item['end_line']}")
        print("-" * 40)