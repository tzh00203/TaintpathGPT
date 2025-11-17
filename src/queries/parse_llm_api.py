#!/usr/bin/env python3
"""
Parse and categorize raw LLM response files
"""

import json
import os
import glob
from typing import List, Dict, Any
import hashlib

def get_file_hash(obj: Dict[str, Any]) -> str:
    """生成字典对象的哈希值用于去重"""
    # 基于关键字段生成哈希
    key_fields = ['package', 'class', 'method']
    key_string = ''.join(str(obj.get(field, '')) for field in key_fields)
    return hashlib.md5(key_string.encode()).hexdigest()

def parse_json_file(file_path: str) -> List[Dict[str, Any]]:
    """解析单个JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # 清理JSON内容
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

def categorize_and_deduplicate(responses: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """分类并去重响应数据"""
    categorized = {
        'sink': [],
        'source': [],
        'taint_prop': []
    }
    
    seen_hashes = {
        'sink': set(),
        'source': set(),
        'taint_prop': set()
    }
    
    for item in responses:
        if not isinstance(item, dict):
            continue
            
        item_type = item.get('type', '').lower()
        
        # 确保有必要的字段
        if not all(key in item for key in ['package', 'class', 'method', 'signature', 'type']):
            continue
        if (item["package"] == "" and item["class"] == "") :continue
        # 根据类型分类
        if item_type in categorized or item_type == "taint-propagator":
            item_hash = get_file_hash(item)
            item_type = "taint_prop" if item_type == "taint-propagator" else item_type
            # 检查是否重复
            if item_hash not in seen_hashes[item_type]:
                seen_hashes[item_type].add(item_hash)
                
                # 确保sink类型有sink_args字段
                if item_type == 'sink' and 'sink_args' not in item:
                    continue
                
                categorized[item_type].append(item)
    
    return categorized

def save_categorized_data(categorized: Dict[str, List[Dict[str, Any]]], output_dir: str):
    """保存分类后的数据"""
    os.makedirs(output_dir, exist_ok=True)
    
    for category, items in categorized.items():
        if items:
            output_file = os.path.join(output_dir, f"llm_labelled_{category}_apis.json")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
            
            print(f"Saved {len(items)} {category} items to {output_file}")

def process_raw_llm_responses(input_dir: str, output_dir: str):
    """处理所有raw_llm_response文件"""
    # 查找所有前缀为raw_llm_response的文件
    pattern = os.path.join(input_dir, "raw_llm_response*")
    files = glob.glob(pattern)
    
    if not files:
        print(f"No files found matching pattern: {pattern}")
        return
    
    print(f"Found {len(files)} files to process")
    
    all_responses = []
    
    # 解析所有文件
    for file_path in files:
        print(f"Processing: {os.path.basename(file_path)}")
        responses = parse_json_file(file_path)
        all_responses.extend(responses)
        print(f"  - Found {len(responses)} items")
    
    print(f"\nTotal items found: {len(all_responses)}")
    
    # 分类并去重
    categorized = categorize_and_deduplicate(all_responses)
    
    # 打印统计信息
    for category, items in categorized.items():
        print(f"{category}: {len(items)} items")
    
    # 保存结果
    save_categorized_data(categorized, output_dir)
    
    # 打印一些示例
    print("\nExamples:")
    for category in ['sink', 'source', 'taint_prop']:
        if categorized[category]:
            example = categorized[category][0]
            print(f"{category.upper()}: {example.get('package', '')}.{example.get('class', '')}.{example.get('method', '')}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Parse and categorize raw LLM response files')
    parser.add_argument('input_dir', help='Directory containing raw_llm_response files')
    parser.add_argument('output_dir', help='Directory to save categorized results')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory {args.input_dir} does not exist")
        return
    
    process_raw_llm_responses(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()