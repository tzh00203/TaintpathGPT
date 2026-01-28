import re

# 简单但鲁棒的正则表达式
def extract_function_info_simple(text):
    """使用多个正则表达式模式尝试匹配"""
    patterns = [
        # 模式1: 处理有used关键字的情况
        r'^[|-]?FunctionDecl[^<]*<[^:]*\.c:(\d+):[^,]*,\s*line:(\d+):[^>]*>[^>]*used\s+(\w+)\s',
        # 模式2: 处理没有used关键字的情况
        r'^[|-]?FunctionDecl[^<]*<[^:]*\.c:(\d+):[^,]*,\s*line:(\d+):[^>]*>[^>]*\s+(\w+)\s+\'',
        # 模式3: 更通用的模式
        r'\.c:(\d+):[^,]*,\s*line:(\d+):[^>]*>.*?(?:used\s+)?(\w+)\s+\'',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return {
                'start_line': match.group(1),
                'end_line': match.group(2),
                'function_name': match.group(3)
            }
    
    return None

# 测试
test_texts = [
    '|-FunctionDecl 0x17d8f2b0 </data_hdd/tzh24/zgc4/projects/tools/NS-IoT/test/test_src/upload.c:77:1, line:142:1> line:77:16 used get_option \'unsigned char *(struct dhcpMessage *, int)\'',
    '-FunctionDecl 0x2c47a990 </data_hdd/tzh24/zgc4/projects/tools/NS-IoT/test/test_src/upload.c:146:1, line:352:1> line:146:5 main \'int (int, char **)\''
]

print("匹配结果:")
for i, text in enumerate(test_texts, 1):
    result = extract_function_info_simple(text)
    if result:
        print(f"文本{i}: 函数={result['function_name']}, 起始行={result['start_line']}, 结束行={result['end_line']}")
    else:
        print(f"文本{i}: 匹配失败")
        # 调试输出
        print(f"  文本: {text[:100]}")