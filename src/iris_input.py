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


def process_cve(cve, vendor):
    # lang = detect_language(cve, vendor)
    lang = "c"
    print(f"🔍 CVE = {cve}, 语言 = {lang}")

    src_base = os.path.join(BASE_INPUT_DIR, lang, cve)
    src_dir = os.path.join(src_base, "src")
    patch_dir = os.path.join(src_base, "patch")
    folder_name = f"paper_{lang}_3_{cve}_{vendor}"
    output_dirname = f"paper_{lang}_3_{cve}_1.0.0"
    output_dir = os.path.join(BASE_OUTPUT_DIR, output_dirname)

    print(f"📁 目标目录: {output_dir}")
    # os.makedirs(output_dir, exist_ok=True)

    # # 处理 src
    # if not os.path.isdir(src_dir):
    #     raise Exception(f"❌ src 目录不存在: {src_dir}")

    # src_items = os.listdir(src_dir)
    # if not src_items:
    #     raise Exception("❌ src 目录为空")

    # first_item = os.path.join(src_dir, src_items[0])

    # copy_or_extract_src(first_item, output_dir)

    # # 处理 patch
    # if os.path.isdir(patch_dir):
    #     diff_file = os.path.join(output_dir, "diff.txt")
    #     merge_patch_files(patch_dir, diff_file)
    # else:
    #     print("⚠️ 无 patch 目录，跳过")

    # print("✅ 完成!")
    
    # ---- 写 CSV ----
    next_index = get_next_index()
    append_project_info_csv(next_index, lang, cve, folder_name, vendor)

    print("✅ 完成！")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 script.py CVE-XXXX-XXXX")
        sys.exit(1)

    cve_id = sys.argv[1].strip()
    vendor = ""
    print(sys.argv)
    if len(sys.argv) == 4:
        vendor = sys.argv[3].strip()
        print(vendor)
    process_cve(cve_id, vendor)

