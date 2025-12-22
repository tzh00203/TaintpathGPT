import os
import shutil
import zipfile
import sys
import csv

# 获取当前脚本所在的根路径
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# 构造相对路径
BASE_INPUT_DIR = os.path.join(ROOT_DIR, "../data", "project-sources")  # c/, java/, python/ 所在目录
BASE_OUTPUT_DIR = os.path.join(ROOT_DIR, "../data", "project-sources")
PROJECT_INFO_CSV = os.path.join(ROOT_DIR, "../data", "project_info.csv")
HASH_LIST = "030e9d00125cbd1ad759668f85488aba1019c668;a221a864db28eb736d36041df2fa6eb8839fc5cd;ce9e11517eca69e58ed4378d1e47a02bd06863cc"

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
    new_directory = directory
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(extension) or file.endswith('.cpp') or file.endswith('.h'):
                file_path = os.path.join(root, file)
                new_file_path = str(os.path.join(root, file)).replace(directory, new_directory)
                process_file(file_path, output_file=new_file_path)

def remove_code_ifdef(directory):
    import shutil
    
    backup_dir = directory + "_origin" if not directory[-1] == "/" else directory[:-1] + "_origin/"
    
    if os.path.exists(backup_dir):
        print(f"备份目录已存在: {backup_dir}")

    print(f"备份原始目录: {directory} -> {backup_dir}")
    try:
        shutil.copytree(directory, backup_dir)
        print(f"备份完成")
    except Exception as e:
        print(f"备份失败: {e}")
        return
    process_directory(directory)
   

def append_project_info_csv(index, lang, cve, folder_name, vendor=""):
    """向 project_info.csv 追加一行"""
    row = [
        str(index),
        folder_name,
        cve,
        "CWE-22",
        "CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')",
        "", "", "", "", "", "",
        HASH_LIST
    ]

    exists = os.path.exists(PROJECT_INFO_CSV)
    with open(PROJECT_INFO_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if exists:
            f.write("\n")  # 如果文件已经存在，先插入一个换行符
        if not exists:
            writer.writerow([
                "id", "folder_name", "cve", "cwe", "cwe_desc",
                "f1","f2","f3","f4","f5","f6",
                "hashes"
            ])
        writer.writerow(row)
    
    with open(PROJECT_INFO_CSV, "r", newline="", encoding="utf-8") as f:
        content_ = f.read()
    with open(PROJECT_INFO_CSV, "w", newline="", encoding="utf-8") as f:
        f.write(content_.strip())
    print(f"📄 CSV 已追加:\n{row}")



def get_next_index():
    """读取 CSV 最后一行，index + 1"""
    if not os.path.exists(PROJECT_INFO_CSV):
        return 1
    
    with open(PROJECT_INFO_CSV, "r", encoding="utf-8") as f:
        lines = f.read().strip().splitlines()

        if len(lines) <= 1:  # 只有表头
            return 1

        last_line = lines[-1].split(",")
        try:
            last_idx = int(last_line[0])
        except:
            last_idx = 0

        return last_idx + 1
    
    
def detect_language(cve, vendor):
    """根据目录判断 CVE 属于哪个语言"""
    for lang in ["c", "java", "python"]:
        if os.path.isdir(os.path.join(BASE_INPUT_DIR, lang, cve)):
            return lang
    raise Exception(f"❌ 未找到对应语言目录: {cve}")


def copy_or_extract_src(src_path, dst_path):
    """复制 src 内容。如果是 zip 则解压"""
    if os.path.isfile(src_path) and src_path.endswith(".zip"):
        print(f"📦 解压 zip: {src_path}")
        with zipfile.ZipFile(src_path, 'r') as zip_ref:
            zip_ref.extractall(dst_path)
    else:
        print(f"📁 复制目录内容: {src_path}")
        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)


def merge_patch_files(patch_dir, output_file):
    """合并所有 .patch 文件内容"""
    with open(output_file, "w") as out_f:
        for fname in sorted(os.listdir(patch_dir)):
            if fname.endswith(".patch"):
                patch_path = os.path.join(patch_dir, fname)
                out_f.write(f"===== {fname} =====\n")
                with open(patch_path, "r") as p_f:
                    out_f.write(p_f.read())
                out_f.write("\n\n")
    print(f"📝 已写入 patch 内容到: {output_file}")


def process_cve(cve, vendor, idx="0", type="paper", language="c"):
    # lang = detect_language(cve, vendor)
    lang = language

    print(f"🔍 CVE = {cve}, 语言 = {lang}")

    folder_name = f"{type}_{lang}_{idx}_{cve}_{vendor}"
    
    source_path = os.path.join(BASE_OUTPUT_DIR, folder_name)
    remove_code_ifdef(source_path)
    # ---- 写 CSV ----
    next_index = get_next_index()
    append_project_info_csv(next_index, lang, cve, folder_name, vendor)

    print("✅ 完成！")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 src/iris_input.py CVE-XXXX-XXXX c BR-6208AC_V2_1.02(your product model) or python3 src/iris_input.py paper_c_6_CVE-XXXX-XXXX_trendnet_boa")
        sys.exit(1)

    cve_id = ""
    vendor = ""
    idx = ""
    language = ""
    type = ""
    if len(sys.argv) == 4:
        vendor = sys.argv[3].strip()
        cve_id = sys.argv[1].strip()
        process_cve(cve_id, vendor)
    elif len(sys.argv) == 2:
        long_ = sys.argv[1].strip()
        vendor = long_.split("XXXX_")[-1]
        cve_id = long_.split("_")[3]
        idx = long_.split("_")[2]
        language = long_.split("_")[1]
        type = long_.split("_")[0]
        process_cve(cve_id, vendor, idx=idx, type=type, language=language)

