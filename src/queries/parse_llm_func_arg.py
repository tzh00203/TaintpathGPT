#!/usr/bin/env python3
"""
Parse and reformat raw LLM response files into tainted_input format
"""

import json
import os
import glob
import hashlib
from typing import List, Dict, Any


def get_file_hash(obj: Dict[str, Any]) -> str:
    """生成字典对象的哈希值用于去重"""
    key_fields = ['package', 'class', 'method', 'signature']
    key_string = ''.join(str(obj.get(field, '')) for field in key_fields)
    return hashlib.md5(key_string.encode()).hexdigest()


def parse_json_file(file_path: str) -> List[Dict[str, Any]]:
    """解析单个JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        # 清理常见转义符
        content = content.replace('\\n', '').replace('\\t', '')

        # 尝试解析JSON
        data = json.loads(content)
        if isinstance(data, list):
            return data
        else:
            print(f"Warning: {file_path} does not contain a JSON array")
            return []

    except json.JSONDecodeError as e:
        print(f"Error parsing {file_path}: {e}")
        return []
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []


def normalize_response(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    将任意 LLM 响应转换为标准 tainted_input 结构：
    {
      "package": "...",
      "class": "...",
      "method": "...",
      "signature": "...",
      "tainted_input": ["..."]
    }
    """
    tainted_fields = item.get('tainted_input', [])

    return {
        "package": item.get("package", ""),
        "class": item.get("class", ""),
        "method": item.get("method", ""),
        "signature": item.get("signature", ""),
        "tainted_input": tainted_fields or []
    }


def deduplicate(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """根据 package/class/method/signature 去重"""
    seen = set()
    unique = []
    for item in items:
        h = get_file_hash(item)
        if h not in seen:
            seen.add(h)
            unique.append(item)
    return unique


def process_raw_llm_responses(input_dir: str, output_file: str):
    """主逻辑：解析、规范化并保存结果"""
    pattern = os.path.join(input_dir, "raw_llm_response*")
    files = glob.glob(pattern)

    if not files:
        print(f"No files found matching pattern: {pattern}")
        return

    print(f"Found {len(files)} raw response files")

    all_items = []
    for file_path in files:
        print(f"Processing: {os.path.basename(file_path)}")
        responses = parse_json_file(file_path)
        formatted = [normalize_response(r) for r in responses if isinstance(r, dict)]
        all_items.extend(formatted)
        print(f"  - {len(formatted)} valid items extracted")

    print(f"\nTotal items before deduplication: {len(all_items)}")
    unique_items = deduplicate(all_items)
    print(f"Unique items after deduplication: {len(unique_items)}")

    # 保存所有数据到一个文件 llm_labelled_source_func_params.json
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_items, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(unique_items)} source function parameters to {output_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Parse and reformat raw LLM response files into tainted_input format")
    parser.add_argument("input_dir", help="Directory containing raw_llm_response files")
    parser.add_argument("output_file", help="File to save the formatted result (llm_labelled_source_func_params.json)")

    args = parser.parse_args()

    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory {args.input_dir} does not exist")
        return

    process_raw_llm_responses(args.input_dir, args.output_file)


if __name__ == "__main__":
    main()
