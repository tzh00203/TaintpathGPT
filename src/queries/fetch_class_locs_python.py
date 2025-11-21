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


import csv
def save_to_csv(results, output_csv_path):
    """将结果保存为CSV文件"""
    csv_path = output_csv_path + "/results.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['name', 'file', 'start_line', 'end_line']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # 写入表头
        writer.writeheader()
        
        # 写入数据
        for result in results:
            writer.writerow(result)
            
import sys

def main():
    if len(sys.argv) != 3:
        print("Usage: python fetch_class.py <source_directory> <output_directory>")
        print("Example: python fetch_class.py /path/to/python/project /path/to/results")
        sys.exit(1)
    
    source_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    
    if not os.path.exists(source_dir):
        print(f"Source directory {source_dir} does not exist")
        sys.exit(1)
    
    functions_and_classes = analyze_python_files(source_dir)
    # 保存结果为CSV格式
    save_to_csv(functions_and_classes, output_dir)

# 使用示例
if __name__ == "__main__":
    main()