#!/usr/bin/env python3
"""
SARIF 文件解析脚本
将 results.sarif 转换为格式化的 JSON 文件
"""

import json
import os
from datetime import datetime

def parse_sarif_file(sarif_file_path, output_file_path):
    """
    解析 SARIF 文件并生成格式化的 JSON 输出
    """
    try:
        # 读取 SARIF 文件
        with open(sarif_file_path, 'r', encoding='utf-8') as f:
            sarif_data = json.load(f)
        
        # 提取关键信息
        parsed_results = {
            "metadata": {
                "source_file": sarif_file_path,
                "parsed_at": datetime.now().isoformat(),
                "total_runs": len(sarif_data.get("runs", [])),
                "schema": sarif_data.get("$schema", "")
            },
            "results": []
        }
        
        # 遍历所有 runs
        for run_index, run in enumerate(sarif_data.get("runs", [])):
            run_info = {
                "run_index": run_index,
                "tool": run.get("tool", {}).get("driver", {}).get("name", "Unknown"),
                "version": run.get("tool", {}).get("driver", {}).get("version", "Unknown"),
                "total_results": len(run.get("results", [])),
                "results": []
            }
            
            # 遍历所有结果
            for result_index, result in enumerate(run.get("results", [])):
                result_info = {
                    "result_index": result_index,
                    "rule_id": result.get("ruleId", ""),
                    "level": result.get("level", "warning"),
                    "message": result.get("message", {}).get("text", ""),
                    "locations": [],
                    "data_flow": []
                }
                
                # 提取位置信息
                for location in result.get("locations", []):
                    physical_location = location.get("physicalLocation", {})
                    artifact_location = physical_location.get("artifactLocation", {})
                    region = physical_location.get("region", {})
                    
                    location_info = {
                        "file": artifact_location.get("uri", ""),
                        "start_line": region.get("startLine", 0),
                        "start_column": region.get("startColumn", 0),
                        "end_line": region.get("endLine", 0),
                        "end_column": region.get("endColumn", 0)
                    }
                    result_info["locations"].append(location_info)
                
                # 提取数据流信息
                for code_flow in result.get("codeFlows", []):
                    for thread_flow in code_flow.get("threadFlows", []):
                        flow_steps = []
                        files_involved = set()  # 用于检测跨文件流
                        
                        for step in thread_flow.get("locations", []):
                            step_location = step.get("location", {}).get("physicalLocation", {})
                            step_artifact = step_location.get("artifactLocation", {})
                            step_region = step_location.get("region", {})
                            
                            flow_step = {
                                "step_number": step.get("index", 0),
                                "node_type": step.get("nodeType", ""),
                                "description": step.get("description", {}).get("text", ""),
                                "file": step_artifact.get("uri", ""),
                                "line": step_region.get("startLine", 0),
                                "column": step_region.get("startColumn", 0)
                            }
                            
                            flow_steps.append(flow_step)
                            files_involved.add(step_artifact.get("uri", ""))  # 记录涉及的文件
                        
                        # 如果涉及多个文件，标记为跨文件流
                        if len(files_involved) > 1:
                            result_info["data_flow"].append({
                                "thread_flow_index": len(result_info["data_flow"]),
                                "steps": flow_steps,
                                "is_cross_file_flow": True
                            })
                        elif flow_steps:
                            result_info["data_flow"].append({
                                "thread_flow_index": len(result_info["data_flow"]),
                                "steps": flow_steps,
                                "is_cross_file_flow": False
                            })
                
                if result_info["data_flow"]:
                    run_info["results"].append(result_info)
            
            parsed_results["results"].append(run_info)
        
        # 保存格式化的 JSON
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(parsed_results, f, indent=2, ensure_ascii=False)
        
        print(f"✅ SARIF 文件解析完成！")
        print(f"📁 输入文件: {sarif_file_path}")
        print(f"📁 输出文件: {output_file_path}")
        print(f"📊 总运行数: {parsed_results['metadata']['total_runs']}")
        
        total_findings = sum(run['total_results'] for run in parsed_results['results'])
        print(f"🔍 总发现数: {total_findings}")
        
        return parsed_results
        
    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 {sarif_file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ 错误: JSON 解析失败 - {e}")
        return None
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None

def create_summary(parsed_data, summary_file_path):
    """
    创建摘要报告
    """
    if not parsed_data:
        return
    
    summary = {
        "summary": {
            "total_runs": parsed_data["metadata"]["total_runs"],
            "total_findings": 0,
            "findings_by_level": {},
            "findings_by_rule": {}
        },
        "detailed_findings": []
    }
    
    for run in parsed_data["results"]:
        summary["summary"]["total_findings"] += run["total_results"]
        
        for result in run["results"]:
            # 按级别统计
            level = result["level"]
            summary["summary"]["findings_by_level"][level] = summary["summary"]["findings_by_level"].get(level, 0) + 1
            
            # 按规则统计
            rule_id = result["rule_id"]
            summary["summary"]["findings_by_rule"][rule_id] = summary["summary"]["findings_by_rule"].get(rule_id, 0) + 1
            
            # 详细发现
            finding = {
                "rule_id": rule_id,
                "level": level,
                "message": result["message"],
                "locations": result["locations"],
                "data_flow_steps": len(result.get("data_flow", [{}])[0].get("steps", [])) if result.get("data_flow") else 0
            }
            summary["detailed_findings"].append(finding)
    
    # 保存摘要
    with open(summary_file_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"📋 摘要报告已保存: {summary_file_path}")

if __name__ == "__main__":
    # 文件路径
    sarif_file = "./test/results.sarif"
    output_file = "./test/parsed_results.json"
    summary_file = "./test/summary_report.json"
    
    # 检查文件是否存在
    if not os.path.exists(sarif_file):
        print(f"❌ 错误: 当前目录下找不到 {sarif_file}")
        print("请确保 results.sarif 文件存在于当前目录")
        exit(1)
    
    # 解析 SARIF 文件
    parsed_data = parse_sarif_file(sarif_file, output_file)
    
    # 创建摘要报告
    if parsed_data:
        create_summary(parsed_data, summary_file)
        
        print("\n🎉 解析完成！生成的文件:")
        print(f"   📄 详细结果: {output_file}")
        print(f"   📊 摘要报告: {summary_file}")
        print(f"\n💡 使用 'cat {output_file} | jq .' 查看格式化结果")
