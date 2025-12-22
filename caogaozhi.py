#!/usr/bin/env python3
import re
import sys
import os

def remove_external_ifdef(code):
    """
    移除函数体外部的 #ifdef/#endif 条件编译指令，保留函数体
    """
    lines = code.split('\n')
    result = []
    i = 0
    n = len(lines)
    
    while i < n:
        line = lines[i]
        stripped_line = line.strip()
        
        # 检查是否是函数体外的 #ifdef 或 #if
        if stripped_line.startswith('#ifdef') or stripped_line.startswith('#if') or stripped_line.startswith('#ifndef'):
            # 查找对应的 #endif
            ifdef_count = 1
            j = i + 1
            start_line = i
            
            while j < n and ifdef_count > 0:
                stripped = lines[j].strip()
                if stripped.startswith('#ifdef') or stripped.startswith('#if') or stripped.startswith('#ifndef'):
                    ifdef_count += 1
                elif stripped.startswith('#endif'):
                    ifdef_count -= 1
                    if ifdef_count == 0:
                        end_line = j
                        break
                j += 1
            
            if ifdef_count == 0:
                # 提取 #ifdef 块中的内容
                block_content = lines[start_line+1:end_line]
                
                # 检查块中是否包含函数定义
                # 合并块内容为字符串进行更全面的检查
                block_text = '\n'.join(block_content)
                
                # 多种函数定义模式
                function_patterns = [
                    # 标准函数定义: 返回类型 函数名(参数) {
                    r'\b(?:void|int|char|float|double|bool|struct|enum|class|unsigned|long|short|static|extern|inline|const|virtual)\s+[\w\*&\s]+\s*\([^)]*\)\s*\{',
                    # 构造函数/析构函数 (C++)
                    r'\b(?:public|private|protected):',
                    # 模板函数 (C++)
                    r'template\s*<[^>]*>\s*\w+\s+\w+\s*\([^)]*\)\s*\{',
                ]
                
                has_function = False
                for pattern in function_patterns:
                    if re.search(pattern, block_text, re.MULTILINE | re.DOTALL):
                        has_function = True
                        break
                
                if has_function:
                    # 保留函数体，去掉外部的 #ifdef/#endif
                    result.extend(block_content)
                    print(f"已移除条件编译指令: {stripped_line}")
                else:
                    # 如果没有函数，保留原始内容（包括 #ifdef）
                    result.extend(lines[start_line:end_line+1])
                
                i = end_line + 1
                continue
        
        # 如果不是函数体外的条件编译，保留原行
        result.append(lines[i])
        i += 1
    
    return '\n'.join(result)
def process_file(input_file, output_file=None):
    """
    处理单个文件
    """
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    processed_content = remove_external_ifdef(content)
    
    if output_file is None:
        output_file = input_file
    else:
        output_dir = os.path.dirname(output_file)
        if output_dir:  # 如果不是当前目录
            os.makedirs(output_dir, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(processed_content)
    
    print(f"处理完成: {input_file} -> {output_file}")
    return processed_content

def process_directory(directory, extension='.c'):
    """
    处理目录下的所有文件
    """
    new_directory = directory + "_wo_ifdef" if not directory.endswith("/") else directory[:-1] + "_wo_ifdef/"
    if not os.path.exists(new_directory):
        os.makedirs(new_directory)
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(extension) or file.endswith('.cpp') or file.endswith('.h'):
                file_path = os.path.join(root, file)
                new_file_path = str(os.path.join(root, file)).replace(directory, new_directory)
                process_file(file_path, output_file=new_file_path)

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  1. 处理单个文件: python script.py input.c [output.c]")
        print("  2. 处理整个目录: python script.py -d directory")
        return
    
    if sys.argv[1] == '-d' and len(sys.argv) >= 3:
        directory = sys.argv[2]
        process_directory(directory)
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) >= 3 else None
        process_file(input_file, output_file)

if __name__ == "__main__":
    main()