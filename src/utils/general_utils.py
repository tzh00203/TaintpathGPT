import pandas as pd

def make_hashable(value):
    """确保值是可哈希的，如果是列表则转换为元组"""
    if isinstance(value, list):
        return tuple(value)
    return value

def remove_duplicates(api_list):
    """去重字典列表"""
    seen = set()
    unique_apis = []
    for api in api_list:
        # 处理字典中的每个值，使其变为可哈希
        # print(api)
        if type(api) is not dict:continue
        api_hashable = {k: make_hashable(v) for k, v in api.items()}
        api_tuple = frozenset(api_hashable.items())  # 使用处理后的字典项
        if api_tuple not in seen:
            seen.add(api_tuple)
            unique_apis.append(api)
    return unique_apis


def get_location_code_line(location_str):
    """从location字符串中提取源代码行，支持单行和多行"""
    location_str = location_str.replace("file://", "")
    if pd.isna(location_str) or not isinstance(location_str, str):
        return location_str
    # 支持多种格式：file.c:123 或 file.c:123-125 或 file.c:123:456
    parts = location_str.split(':')
    if len(parts) < 2:
        return location_str
    
    file_path = parts[0]
    start_line = int(parts[1])
    end_line = int(parts[-2])
    lines = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin1', errors='ignore') as f:
            lines = f.readlines()
    try:
        if start_line > end_line:
            return location_str
        # print(start_line, end_line)
        # 提取多行代码
        code_lines = []
        for i in range(start_line, end_line + 1):
            code_lines.append(f"{lines[i-1].rstrip().strip()}")

        return '\n'.join(code_lines)
    except Exception as e:
        print(e)
        return location_str