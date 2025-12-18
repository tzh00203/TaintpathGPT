#!/usr/bin/env python3
"""
C/C++ Conditional Function Definition Extractor
Extract function definitions that are inside complete conditional compilation blocks
"""

import os
import re
import sys
import csv
from typing import List, Dict, Any, Set, Tuple, Optional
from datetime import datetime
from tqdm import tqdm

class CCppConditionalFunctionExtractor:
    def __init__(self, project_root: str = None):
        self.excluded_dirs = {
            'test', 'tests', '__pycache__', '.pytest_cache', 
            'build', 'bin', 'obj', '.git', '.svn', '.vscode',
            'Debug', 'Release', 'x64', 'x86', 'out', 'dist',
            'third_party', 'vendor', 'external', 'deps'
        }
        self.excluded_files = {
            'test_', '_test', '.test.', 'test.', '_spec.', 'spec.',
            'mock_', '_mock', 'unittest_', 'benchmark_'
        }
        self.project_root = project_root
        self.seen_records: Set[str] = set()
        
        # 函数签名正则表达式（只匹配到 { 为止）
        self.function_sig_pattern = re.compile(r'''
            # 前置修饰符
            (?:^|[\s;])
            (?P<modifiers>
                (?:(?:static|extern|inline|virtual|explicit|friend|constexpr|consteval|constinit)\s+)*
            )
            # 返回类型
            (?P<return_type>
                (?:(?:const\s+|volatile\s+|mutable\s+)*
                (?:unsigned\s+|signed\s+|long\s+|short\s+)?
                (?:struct\s+|class\s+|enum\s+|union\s+|typename\s+)?
                [\w_:<>]+
                (?:\s*\*+\s*|\s*&\s*|\s*&&\s*|\s*const\s*)?
                \s+)+
            )
            # 函数名和模板
            (?P<function>
                ~?[\w_]+
                (?:<[^>]+>)?
            )
            \s*
            \(
            (?P<params>[^)]*)
            \)
            \s*
            (?:const\s*)?
            (?:noexcept\s*(?:\([^)]*\))?\s*)?
            (?:override\s*)?
            (?:final\s*)?
            (?:=\s*(?:0|default|delete)\s*)?
            \s*
            \{  # 只匹配到函数体开始
        ''', re.VERBOSE | re.MULTILINE | re.DOTALL)

    def should_exclude(self, file_path: str) -> bool:
        """检查文件是否应该被排除"""
        filename = os.path.basename(file_path).lower()
        dirname = os.path.basename(os.path.dirname(file_path))
        
        for prefix in self.excluded_files:
            if filename.startswith(prefix.lower()):
                return True
        
        if dirname in self.excluded_dirs:
            return True
        
        if 'test' in file_path.lower():
            return True
        
        ext = os.path.splitext(filename)[1].lower()
        valid_extensions = {'.c', '.cpp', '.cc', '.cxx', '.c++', '.h', '.hpp', '.hh', '.hxx', '.h++'}
        return ext not in valid_extensions

    def get_package_name(self, file_path: str) -> str:
        """从文件路径提取包名"""
        if self.project_root:
            try:
                rel_path = os.path.relpath(os.path.dirname(file_path), self.project_root)
                if rel_path == '.':
                    return ""
                
                parts = rel_path.split(os.sep)
                filtered_parts = []
                for part in parts:
                    if part and part not in self.excluded_dirs:
                        filtered_parts.append(part)
                
                return '.'.join(filtered_parts) if filtered_parts else ""
            except ValueError:
                pass
        
        dir_name = os.path.basename(os.path.dirname(file_path))
        return dir_name if dir_name and dir_name != '.' else ""

    def get_class_name(self, file_path: str) -> str:
        """从文件名提取类名"""
        filename = os.path.basename(file_path)
        base_name = os.path.splitext(filename)[0]
        
        if base_name.lower().endswith('_test'):
            base_name = base_name[:-5]
        
        if '_' in base_name:
            parts = base_name.split('_')
            base_name = ''.join(part.capitalize() for part in parts if part)
        
        return base_name

    def extract_return_type(self, signature: str) -> str:
        """从函数签名中提取返回类型"""
        match = re.search(r'''
            ^\s*
            (?:static\s+|extern\s+|inline\s+|virtual\s+|explicit\s+)*
            (?:const\s+|volatile\s+|mutable\s+)*
            (?:unsigned\s+|signed\s+|long\s+|short\s+)?
            (?:struct\s+|class\s+|enum\s+|union\s+|typename\s+)?
            ([\w_:<>]+(?:\s*\*+\s*|\s*&\s*|\s*&&\s*|\s*const\s*)?)
            \s+\w+\s*\(
        ''', signature, re.VERBOSE | re.IGNORECASE)
        
        if match:
            return_type = match.group(1).strip()
            return_type = re.sub(r'\s+', ' ', return_type)
            return return_type if return_type else "void"
        
        return "void"

    def extract_parameter_types(self, params_str: str) -> str:
        """提取参数类型（分号分隔）"""
        if not params_str or params_str.strip() == "" or params_str.strip() == "void":
            return "void"
        
        params_str = params_str.strip()
        params = []
        current_param = ""
        depth = 0
        
        for char in params_str:
            if char == '<' or char == '(' or char == '[':
                depth += 1
                current_param += char
            elif char == '>' or char == ')' or char == ']':
                depth -= 1
                current_param += char
            elif char == ',' and depth == 0:
                if current_param.strip():
                    params.append(current_param.strip())
                current_param = ""
            else:
                current_param += char
        
        if current_param.strip():
            params.append(current_param.strip())
        
        param_types = []
        for param in params:
            words = param.split()
            if not words:
                continue
            
            for i in range(len(words) - 1, -1, -1):
                word = words[i]
                if word and word[-1].isalnum() and not word.startswith('...'):
                    param_type_words = words[:i] + words[i+1:]
                    break
            else:
                param_type_words = words
            
            param_type = ' '.join(param_type_words)
            if param_type:
                param_types.append(param_type.strip())
            else:
                param_types.append(param.strip())
        
        return ';'.join(param_types) if param_types else "void"

    def find_matching_brace(self, content: str, start_pos: int) -> int:
        """查找与 { 匹配的 } 的位置，处理嵌套、字符串和注释"""
        if start_pos >= len(content) or content[start_pos] != '{':
            return -1
        
        depth = 1
        pos = start_pos + 1
        in_string = False
        string_char = None
        in_comment = False
        in_block_comment = False
        
        while pos < len(content) and depth > 0:
            ch = content[pos]
            prev_ch = content[pos-1] if pos > 0 else ''
            
            # 处理字符串
            if not in_comment and not in_block_comment:
                if ch == '"' or ch == "'":
                    if not in_string:
                        in_string = True
                        string_char = ch
                    elif string_char == ch and prev_ch != '\\':
                        in_string = False
                        string_char = None
            
            # 处理注释
            elif not in_string:
                if ch == '/' and pos + 1 < len(content):
                    next_ch = content[pos+1]
                    if next_ch == '/' and not in_block_comment:
                        in_comment = True
                        pos += 1  # 跳过 /
                    elif next_ch == '*' and not in_comment:
                        in_block_comment = True
                        pos += 1  # 跳过 *
                elif ch == '\n' and in_comment:
                    in_comment = False
                elif ch == '*' and pos + 1 < len(content):
                    if content[pos+1] == '/' and in_block_comment:
                        in_block_comment = False
                        pos += 1  # 跳过 /
            
            # 统计大括号（不在字符串和注释中）
            if not in_string and not in_comment and not in_block_comment:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        return pos  # 返回匹配的 } 的位置
            
            pos += 1
        
        return -1  # 没有找到匹配的 }

    def find_matching_preprocessor_block(self, content: str, func_start: int, func_end: int) -> Optional[Tuple[str, str, int, int]]:
        """
        查找函数所在的完整预处理块
        
        Returns:
            (condition_type, condition_macro, block_start, block_end) 或 None
        """
        # 1. 向上查找最近的条件编译指令
        lines_before = content[:func_start].split('\n')
        conditional_line = -1
        condition_type = ""
        condition_macro = ""
        
        for i in range(len(lines_before) - 1, -1, -1):
            line = lines_before[i].strip()
            
            # 匹配条件编译指令
            ifdef_match = re.match(r'^\s*#\s*ifdef\s+(\w+)', line)
            if ifdef_match:
                conditional_line = i
                condition_type = "IFDEF"
                condition_macro = ifdef_match.group(1)
                break
            
            ifndef_match = re.match(r'^\s*#\s*ifndef\s+(\w+)', line)
            if ifndef_match:
                conditional_line = i
                condition_type = "IFNDEF"
                condition_macro = ifndef_match.group(1)
                break
            
            if_match = re.match(r'^\s*#\s*if\s+(.+)$', line)
            if if_match:
                conditional_line = i
                condition_type = "IF"
                condition_macro = if_match.group(1)
                break
            
            elif_match = re.match(r'^\s*#\s*elif\s+(.+)$', line)
            if elif_match:
                conditional_line = i
                condition_type = "ELIF"
                condition_macro = elif_match.group(1)
                break
            
            # 如果遇到其他预处理指令但不是条件开始，继续向上
            if line and line.startswith('#') and not line.startswith('#endif'):
                # 继续向上查找
                pass
        
        if conditional_line == -1:
            return None  # 没有找到条件编译指令
        
        # 2. 向下查找对应的 #endif
        lines_after = content[func_end:].split('\n')
        endif_line = -1
        depth = 1  # 已经有一个条件开始了
        
        for i, line in enumerate(lines_after):
            line_stripped = line.strip()
            
            # 检查是否是条件编译开始
            if re.match(r'^\s*#\s*(?:ifdef|ifndef|if|elif)\b', line_stripped):
                depth += 1  # 嵌套条件，深度增加
            elif line_stripped.startswith('#endif'):
                depth -= 1  # 条件结束，深度减少
                
                if depth == 0:
                    endif_line = i
                    break
        
        if endif_line == -1:
            return None  # 没有找到对应的 #endif
        
        # 3. 检查在函数体和对应的#endif之间是否有其他条件编译开始
        # 计算函数结束到#endif之间的内容
        block_content = '\n'.join(lines_after[:endif_line])
        
        # 检查是否有新的条件编译开始（除了函数体开始的哪个）
        nested_conditionals = re.findall(r'^\s*#\s*(?:ifdef|ifndef|if|elif)\b', block_content, re.MULTILINE)
        
        if len(nested_conditionals) > 0:
            # 有新的条件编译开始，说明函数不完全在这个条件块内
            return None
        
        # 计算块的起始和结束位置
        block_start_pos = self.get_line_start_position(content, conditional_line)
        block_end_pos = func_end + len('\n'.join(lines_after[:endif_line+1]))
        
        return (condition_type, condition_macro, block_start_pos, block_end_pos)
    
    def get_line_start_position(self, content: str, line_num: int) -> int:
        """获取指定行在内容中的起始位置"""
        lines = content.split('\n')
        if line_num >= len(lines):
            return len(content)
        
        # 计算前line_num行的总长度（包括换行符）
        position = 0
        for i in range(line_num):
            position += len(lines[i]) + 1  # +1 换行符
        
        return position

    def extract_doc_comment(self, content: str, pos: int) -> str:
        """提取函数前的文档注释"""
        before_content = content[:pos]
        lines = before_content.split('\n')
        
        doc_lines = []
        for line in reversed(lines[-10:]):
            line = line.strip()
            
            if line.startswith('///') or line.startswith('//!'):
                doc_lines.insert(0, line[3:].strip())
            elif line.startswith('//'):
                doc_lines.insert(0, line[2:].strip())
            elif line.startswith('/*'):
                if '*/' in line:
                    comment = line[2:line.index('*/')].strip()
                    doc_lines.insert(0, comment)
                break
            elif line.startswith('*'):
                doc_lines.insert(0, line[1:].strip())
            elif line and not line.startswith('*') and not line.startswith('//'):
                break
        
        return ' '.join(doc_lines)

    def extract_function_info(self, match: re.Match, file_path: str, line_num: int, 
                             condition_info: Optional[Tuple[str, str]] = None) -> Optional[Dict[str, str]]:
        """从正则匹配中提取函数信息"""
        full_match = match.group(0)
        return_type_group = match.group('return_type') or "void"
        function_name = match.group('function') or ""
        params = match.group('params') or ""
        
        return_type_group = return_type_group.strip()
        function_name = function_name.strip()
        params = params.strip()
        
        # 跳过非函数的关键字
        if function_name in ["if", "for", "while", "switch", "else", "do", "try", "catch"]:
            return None
        
        package = self.get_package_name(file_path)
        clazz = self.get_class_name(file_path)
        
        modifiers = match.group('modifiers') or ""
        modifiers = modifiers if ( "_" not in modifiers) else ""
        # print(111, return_type_group)
        return_type_group = return_type_group.split("\n")[-1] if "\n" in return_type_group else return_type_group
        full_signature = f"{modifiers}{return_type_group} {function_name}({params})"
        full_signature = re.sub(r'\s+', ' ', full_signature).strip()
        
        return_type = self.extract_return_type(full_signature)
        parameter_types = self.extract_parameter_types(params)
        
        if parameter_types == "void":
            internal_signature = f"{function_name}()"
        else:
            param_list = parameter_types.split(';')
            internal_signature = f"{function_name}({', '.join(param_list)})"
        
        location = f"file://{file_path}:{line_num}:0"
        doc = ""
        
        if condition_info:
            cond_type, cond_macro = condition_info
            doc = f"[{cond_type} {cond_macro}] "
        
        return {
            'package': package,
            'clazz': clazz,
            'func': function_name,
            'full_signature': full_signature,
            'internal_signature': internal_signature,
            'location': location,
            'parameter_types': parameter_types,
            'return_type': return_type,
            'doc': doc
        }

    def analyze_file(self, file_path: str) -> List[Dict[str, str]]:
        """分析单个C/C++文件，提取在完整条件编译块内的函数"""
        if self.should_exclude(file_path):
            return []
        
        results = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 查找所有函数签名（到 { 为止）
            for match in self.function_sig_pattern.finditer(content):
                # 获取函数名
                func_name = match.group('function')
                
                # 计算行号
                line_num = content[:match.start()].count('\n') + 2
                
                # 找到函数体开始位置（{ 的位置）
                brace_start = match.end() - 1  # { 的位置
                
                # 查找匹配的 }
                func_end = self.find_matching_brace(content, brace_start)
                if func_end == -1:
                    # print(f"  警告: 找不到匹配的 }} for {func_name}")
                    continue
                
                # 查找函数所在的完整预处理块
                block_info = self.find_matching_preprocessor_block(
                    content, match.start(), func_end
                )
                
                # 如果没有找到完整的条件编译块，跳过
                if not block_info:
                    continue
                
                cond_type, cond_macro, block_start, block_end = block_info
                
                # 确保函数完全在条件块内
                if match.start() >= block_start and func_end <= block_end:
                    # 提取函数信息
                    func_info = self.extract_function_info(
                        match, file_path, line_num, (cond_type, cond_macro)
                    )
                    
                    if func_info is None:
                        continue
                    
                    # 提取文档注释
                    doc = self.extract_doc_comment(content, match.start())
                    func_info['doc'] = func_info['doc'] + doc
                    
                    # 构建唯一标识
                    unique_key = f"{func_info['package']}|{func_info['clazz']}|{func_info['func']}|{func_info['full_signature']}"
                    
                    if unique_key not in self.seen_records:
                        self.seen_records.add(unique_key)
                        results.append(func_info)
                        
                        # print(f"  ✓ {func_info['func']} (line {line_num}) - Inside #{cond_type.lower()} {cond_macro} block")
                
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
        
        return results

    def analyze_directory(self, directory: str) -> List[Dict[str, str]]:
        """分析整个目录"""
        all_results = []
        
        # print(f"📁 Scanning directory: {directory}")
        # print("-" * 60)
        
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
            
            for file in files:
                file_path = os.path.join(root, file)
                if not self.should_exclude(file_path):
                    relative_path = os.path.relpath(file_path, directory)
                    # print(f"📄 {relative_path}")
                    results = self.analyze_file(file_path)
                    all_results.extend(results)
        
        return all_results

    def save_results_as_csv(self, results: List[Dict[str, str]], output_dir: str, filename: str = None):
        """保存为CSV文件"""
        # os.makedirs(output_dir, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"complete_conditional_functions_{timestamp}.csv"
        
        csv_path = output_dir
        
        fieldnames = [
            'package', 'clazz', 'func', 'full_signature', 
            'internal_signature', 'location', 'parameter_types', 
            'return_type', 'doc'
        ]
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            
            for result in tqdm(results, desc="fetch the func params in IFDEF..."):
                row = {field: result.get(field, "") for field in fieldnames}
                writer.writerow(row)
        
        print("-" * 60)
        print(f"Results saved to: {csv_path}")
        print(f"Total functions in complete conditional blocks: {len(results)}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python extract_complete_conditionals.py <source_directory> <output_directory>")
        print("Example: python extract_complete_conditionals.py /path/to/cpp/project ./output")
        sys.exit(1)
    
    source_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    if not os.path.exists(source_dir):
        print(f"❌ Source directory {source_dir} does not exist")
        sys.exit(1)
    
    analyzer = CCppConditionalFunctionExtractor(project_root=source_dir)
    
    print("\t\t==>Complete Conditional Block Function Extractor")
    print("\t\t\t==>Extracts ONLY functions that are COMPLETELY inside conditional blocks")
    print("\t\t\t==>Function must be between #ifdef/#if and matching #endif")
    
    results = analyzer.analyze_directory(source_dir)
    analyzer.save_results_as_csv(results, output_dir)
    # return results


if __name__ == "__main__":
    main()