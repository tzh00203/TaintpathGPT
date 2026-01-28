import logging
import chardet
import sys
import os
import logging
import json

conn = ""
c = ""


target_files = []
all_dict_list = []
root_func_call = dict()
module_addrrange_dict = {}
blrfunc_to_realfunc_dict = {}
all_func_addr_dict = {}
callfunc_graph = ""
callfunc_graph_streamline_dict = {}
callfunc_tmp = {}
func_callcode_dict = {}
js_str = ""
used_func = []
all_export = []
traverse_up_analyzed_dep_func_dict = {}
analyzed_classname_list = []
analyzed_bugfunc_list = []
target_datastruct_list = []
malloc_info_list = []
inserted_code_list = []


base_type_list = ['void *', 'void',
                  'bool', 'int8','uint8','uint8 *','int8 *','char', 'char *', 'signed char', 'unsigned char', 'wchar_t',
                  'int', 'int *', 'signed int', 'unsigned int','int32','uint32','int32 *','uint32 *',
                  'float', 'double','uint64','int64','uint64 *','int64 *','long', 'signed long', 'unsigned long',
                  'float *', 'double *','long *', 'signed long *', 'unsigned long *',
                  'long long', 'signed long long', 'unsigned long long','long long *', 'signed long long *', 'unsigned long long *',
                  'short', 'signed short', 'unsigned short','int16','uint16','int16 *','uint16 *','short *', 'signed short *', 'unsigned short *',]

analyzed_func_list = []


def is_integer(s):
    s = s.lower()
    try:
        if s.find("0x") != -1:
            s = s.replace("ull", "").replace("ll", "").replace("ul", "").replace("l", "").replace("u", "")
            int(s, 16)
        else:
            int(s)
        return True
    except ValueError:
        return False


def str2int(s):
    s = s.lower()
    if s.find("0x") != -1:
        s = s.replace("ull", "").replace("ll", "").replace("ul", "").replace("l", "").replace("u", "")
        return int(s, 16)
    else:
        return int(s)

def get_encoding(file):
    with open(file, 'rb') as f:
        return chardet.detect(f.read())['encoding'] # type: ignore

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger


def convert_files_to_utf8(project_root):
    '''
    将项目中的所有文件的编码格式转化为utf-8
    '''
    for root, dirs, files in os.walk(project_root):
        for file in files:
            filepath = os.path.join(root, file)  # 自动拼接路径，跨平台
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in ['.c', '.h', '.cpp', '.hpp', '.java']:
            continue

        # 统一路径格式，Windows 用 \，Linux/macOS 用 /
        filepath = os.path.normpath(filepath)

        # Windows 下长路径处理
        if sys.platform.startswith("win"):
            if not os.path.exists(filepath):
                filepath = r"\\?\%s" % filepath

        encoding = get_encoding(filepath)
        if encoding == 'GB2312':
            encoding = 'GB18030'

        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
        except Exception as e:
            print(f"convert_files_to_utf8 read file {filepath}: {e} {encoding}")
            continue

        try:
            with open(filepath, 'w', encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            print(f"convert_files_to_utf8 write file {filepath}: {e}")


def get_funcname_and_scope(funcname):
    if funcname.find("::") != -1:
        flag = funcname.rfind("::")
        func_name = funcname[flag + 2:]
        scope = funcname[:flag]
    elif funcname.find(".") != -1:
        flag = funcname.rfind(".")
        func_name = funcname[flag + 1:]
        scope = ""
    elif funcname.find("->") != -1:
        flag = funcname.rfind("->")
        func_name = funcname[flag + 2:]
        scope = ""
    else:
        scope = ""
        func_name = funcname
    return func_name, scope

import re
from collections import defaultdict

def find_duplicate_functions(file_path):
    try:
        # 正则表达式匹配C函数定义
        function_pattern = re.compile(
            r'^(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*\{'  # 匹配函数名和参数列表
            r'([^}]*)'  # 匹配函数体
            r'\}'       # 匹配结束大括号
            r'(?ms)'    # 多行模式，点匹配包括换行符
        )
        
        functions = defaultdict(list)
        
        with open(file_path, 'r', encoding='utf-8') as file:
            code = file.read()
        
        for match in function_pattern.finditer(code):
            # print(match.group(0))
            all_lines = match.group(0)
            function_name = match.group(1)
            function_body = match.group(2)
            start_pos = match.start()
            line_number = code.count('\n', 0, start_pos) + 1
            
            # 处理函数体：每行添加行号
            body_lines = function_body.split('\n')
            numbered_body = []
            current_line = line_number   # 函数定义行是line_number
            
            # 添加函数定义行
            func_def_part = match.string[match.start():match.start(2)]
            numbered_func_def = f"l{line_number}:" + func_def_part
            
            # 处理函数体每行
            for line in all_lines.split("\n"):
                # if line.strip():  # 跳过空行
                numbered_body.append(f"l{current_line}:" + line)
                current_line += 1
            

            # 组合完整函数
            full_function = '\n'.join(numbered_body) + "\n"
            
            functions[function_name].append({
                'line': line_number,
                'body': full_function
            })
        
        # 筛选出重复函数
        duplicates = {name: info for name, info in functions.items() if len(info) > 1}
    except:
        duplicates = {}
    return duplicates

def print_duplicates(file_path):
    duplicates = find_duplicate_functions(file_path)
    
    if not duplicates:
        print(f"在文件 {file_path} 中没有发现重复的函数定义")
        return
    
    print(f"在文件 {file_path} 中发现以下重复函数定义：\n")
    for func_name, implementations in duplicates.items():
        print(f"函数名: {func_name} (共 {len(implementations)} 个实现)")
        for i, impl in enumerate(implementations, 1):
            print(f"\n实现 #{i}:")
            print(f"位置: 第 {impl['line']} 行")
            print(f"函数体:\n{impl['body']}\n")
        print("="*50)

def parse_json_safe(raw_str, logger):
    """尝试用 json.loads 或 eval 解析字符串"""
    try:
        return json.loads(raw_str)
    except json.JSONDecodeError as e:
        logger.warning(f"json.loads 解析失败: {e}, 尝试使用 eval")
        try:
            return eval(raw_str.replace("true", "True").replace("false", "False"))
        except Exception as e2:
            logger.error(f"eval 解析失败: {e2}")
            return None
        
if __name__ == "__main__":
    c_file_path = "code_input_all/code_input.test/test.c"
    print_duplicates(c_file_path)
