"""
Bug Report Generator
从SQLite数据库中读取bug表数据并生成HTML报告
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import argparse
import logging
from rf_config import *

class BugReportGenerator:

    def __init__(self, project_path: str, database_path: str,database_name: str):
        """
        初始化Bug报告生成器
        
        Args:
            db_path: SQLite数据库路径
            output_dir: 输出目录
        """

        self.db_path = os.path.join(project_path, database_path, database_name)
        self.output_dir = os.path.join(project_path, database_path)
        self.log_dir = os.path.join(project_path, database_path, "llm_log")
        self.logger = logging.getLogger(__name__)
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        
    def get_bug_data(self) -> List[Dict[str, Any]]:
        """
        从数据库中获取bug数据
        
        Returns:
            bug数据列表
        """
        try:
            print(self.db_path)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取表结构信息
            cursor.execute("PRAGMA table_info(bugreport)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            self.logger.info(f"数据库表结构: {column_names}")
            
            # 查询所有bug数据
            cursor.execute("SELECT * FROM bugreport ORDER BY rowid DESC")
            rows = cursor.fetchall()
            
            self.logger.info(f"查询到 {len(rows)} 条记录")
            
            # 转换为字典列表
            bugs = []
            for row in rows:
                bug_dict = {}
                for i, value in enumerate(row):
                    bug_dict[column_names[i]] = value
                bugs.append(bug_dict)
                
            conn.close()
            return bugs
            
        except sqlite3.Error as e:
            self.logger.error(f"数据库查询失败: {e}")
            return []
        except Exception as e:
            self.logger.error(f"获取bug数据失败: {e}")
            return []
    
    def get_statistics(self, bugs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        计算统计信息
        
        Args:
            bugs: bug数据列表
            
        Returns:
            统计信息字典
        """
        stats = {
            'total_bugs': len(bugs),
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0,
            'p1_model_count': 0,
            'p2_model_count': 0
        }
        
        for bug in bugs:
            # 统计置信度分布
            confidence =float(bug.get('confidence_level', 0))
            if confidence > 0.9:
                stats['high_confidence'] += 1
            elif confidence >= 0.8:
                stats['medium_confidence'] += 1
            else:
                stats['low_confidence'] += 1
                
            # 统计模型分布
            model = bug.get('bug_model', '')
            if model == 'p1':
                stats['p1_model_count'] += 1
            elif model == 'p2':
                stats['p2_model_count'] += 1
        
        return stats
    
    def generate_html(self, bugs: List[Dict[str, Any]], stats: Dict[str, Any]) -> str:
        """
        生成HTML报告
        
        Args:
            bugs: bug数据列表
            stats: 统计信息
            
        Returns:
            HTML内容
        """
        html_template = """<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>漏洞分析平台</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; background-color: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; text-align: center; }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header p {{ font-size: 1.2em; opacity: 0.9; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); text-align: center; transition: transform 0.3s ease; }}
        .stat-card:hover {{ transform: translateY(-5px); }}
        .stat-number {{ font-size: 2.5em; font-weight: bold; color: #667eea; margin-bottom: 10px; }}
        .stat-label {{ color: #666; font-size: 1.1em; }}
        .confidence-high {{ color: #e74c3c; }}
        .confidence-medium {{ color: #f39c12; }}
        .confidence-low {{ color: #27ae60; }}
        .bugs-section {{ background: white; border-radius: 10px; padding: 30px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); margin-bottom: 30px; }}
        .section-title {{ font-size: 1.8em; margin-bottom: 20px; color: #2c3e50; border-bottom: 3px solid #667eea; padding-bottom: 10px; }}
        .bug-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        .bug-table th, .bug-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        .bug-table th {{ background-color: #f8f9fa; font-weight: 600; color: #495057; }}
        .bug-table tr:hover {{ background-color: #f8f9fa; }}
        .confidence-badge {{ padding: 4px 8px; border-radius: 12px; font-size: 0.85em; font-weight: 500; }}
        .confidence-high-badge {{ background-color: #ffebee; color: #c62828; }}
        .confidence-medium-badge {{ background-color: #fff3e0; color: #ef6c00; }}
        .confidence-low-badge {{ background-color: #e8f5e8; color: #2e7d32; }}
        .model-badge {{ padding: 4px 8px; border-radius: 12px; font-size: 0.85em; font-weight: 500; }}
        .model-p1 {{ background-color: #e3f2fd; color: #1565c0; }}
        .model-p2 {{ background-color: #f3e5f5; color: #7b1fa2; }}
        .description-cell {{ max-width: 300px; word-wrap: break-word; }}
        .reasoning-cell {{ max-width: 400px; word-wrap: break-word; }}
        .log-link {{ color: #667eea; text-decoration: none; }}
        .log-link:hover {{ text-decoration: underline; }}
        .expandable {{ cursor: pointer; }}
        .expandable:hover {{ background-color: #f0f8ff; }}
        .details-row {{ display: none; background-color: #f8f9fa; }}
        .details-content {{ padding: 20px; border-top: 1px solid #ddd; }}
        @media (max-width: 768px) {{ .container {{ padding: 10px; }} .header h1 {{ font-size: 2em; }} .stats-grid {{ grid-template-columns: 1fr; }} .bug-table {{ font-size: 0.9em; }} .bug-table th, .bug-table td {{ padding: 8px; }} }}
    </style>
</head>
<body>
    <div class=\"container\">\n        <div class=\"header\">\n            <h1>🔍 奇点AI漏洞分析平台</h1>\n            <p>生成时间: {generation_time}</p>\n        </div>\n        \n        <div class=\"stats-grid\">\n            <div class=\"stat-card\">\n                <div class=\"stat-number\">{total_bugs}</div>\n                <div class=\"stat-label\">总漏洞数</div>\n            </div>\n            <div class=\"stat-card\">\n                <div class=\"stat-number confidence-high\">{high_confidence}</div>\n                <div class=\"stat-label\">高置信度(>90%)漏洞</div>\n            </div>\n            <div class=\"stat-card\">\n                <div class=\"stat-number confidence-medium\">{medium_confidence}</div>\n                <div class=\"stat-label\">中置信度(>=80%)漏洞</div>\n            </div>\n            <div class=\"stat-card\">\n                <div class=\"stat-number confidence-low\">{low_confidence}</div>\n                <div class=\"stat-label\">低置信度漏洞</div>\n            </div>\n            <div class=\"stat-card\">\n                <div class=\"stat-number\">{p1_model_count}</div>\n                <div class=\"stat-label\">P1类型检测</div>\n            </div>\n            <div class=\"stat-card\">\n                <div class=\"stat-number\">{p2_model_count}</div>\n                <div class=\"stat-label\">P2类型检测</div>\n            </div>\n        </div>\n        \n        <div class=\"bugs-section\">\n            <h2 class=\"section-title\">📋 漏洞详情列表</h2>\n            <table class=\"bug-table\">\n                <thead>\n                    <tr>\n                        <th>ID</th>\n                        <th>漏洞函数名称</th>\n                        <th>漏洞AI描述</th>\n                        <th>置信度</th>\n                        <th>模型</th>\n                        <th>日志</th>\n                    </tr>\n                </thead>\n                <tbody>\n                    {bug_rows}\n                </tbody>\n            </table>\n        </div>\n    </div>\n    \n    <script>\n        document.addEventListener('DOMContentLoaded', function() {{\n            // 为统计卡片添加动画\n            const statNumbers = document.querySelectorAll('.stat-number');\n            statNumbers.forEach(stat => {{\n                const finalValue = parseInt(stat.textContent);\n                let currentValue = 0;\n                const increment = finalValue / 50;\n                const timer = setInterval(() => {{\n                    currentValue += increment;\n                    if (currentValue >= finalValue) {{\n                        stat.textContent = finalValue;\n                        clearInterval(timer);\n                    }} else {{\n                        stat.textContent = Math.floor(currentValue);\n                    }}\n                }}, 20);\n            }});\n            \n            // 为可展开行添加点击事件\n            const expandableRows = document.querySelectorAll('.expandable');\n            expandableRows.forEach(row => {{\n                row.addEventListener('click', function() {{\n                    const detailsRow = this.nextElementSibling;\n                    if (detailsRow && detailsRow.classList.contains('details-row')) {{\n                        if (detailsRow.style.display === 'none' || detailsRow.style.display === '') {{\n                            detailsRow.style.display = 'table-row';\n                        }} else {{\n                            detailsRow.style.display = 'none';\n                        }}\n                    }}\n                }});\n            }});\n        }});\n    </script>\n</body>\n</html>"""
        
        # 生成漏洞表格行
        bug_rows_html = ""
        for bug in bugs:
            confidence = float(bug.get('confidence_level', 0))
            confidence_class = 'confidence-high-badge' if confidence > 0.9 else 'confidence-medium-badge' if confidence >= 0.8 else 'confidence-low-badge'

            model = bug.get('bug_model', '')
            model_class = 'model-p1' if model == 'p1' else 'model-p2'
            log_file = os.path.join(self.log_dir,bug.get('log', ''))
            log_link = f"<a href=\"{log_file}\" class=\"log-link\" target=\"_blank\">查看日志</a>" if log_file else "无"
            
            # 主行
            bug_rows_html += f"""
            <tr class=\"expandable\">\n                <td>{bug.get('rowid', 'N/A')}</td>\n                <td>{bug.get('funcname', 'N/A')}</td>\n                <td class=\"description-cell\">{bug.get('vul_descripe', 'N/A')}</td>\n                <td><span class=\"confidence-badge {confidence_class}\">{confidence:.2f}</span></td>\n                <td><span class=\"model-badge {model_class}\">{model}</span></td>\n                <td>{log_link}</td>\n            </tr>\n            """
            
            # 详细信息行
            reasoning = bug.get('vul_reason', '')
            if reasoning:
                bug_rows_html += f"""
            <tr class=\"details-row\">\n                <td colspan=\"6\">\n                    <div class=\"details-content\">\n                        <h4>🔍 漏洞AI推理过程</h4>\n                        <p>{reasoning}</p>\n                    </div>\n                </td>\n            </tr>\n            """
        
        # 填充模板
        html_content = html_template.format(
            generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_bugs=stats['total_bugs'],
            high_confidence=stats['high_confidence'],
            medium_confidence=stats['medium_confidence'],
            low_confidence=stats['low_confidence'],
            p1_model_count=stats['p1_model_count'],
            p2_model_count=stats['p2_model_count'],
            bug_rows=bug_rows_html
        )
        
        return html_content
    
    def generate_report(self, output_filename: Optional[str] = None) -> str:
        """
        生成完整的bug报告
        
        Args:
            output_filename: 输出文件名，如果为None则自动生成
            
        Returns:
            输出文件路径
        """
        try:
            # 获取bug数据
            bugs = self.get_bug_data()
            if not bugs:
                self.logger.warning("没有找到bug数据")
                return ""
            
            # 计算统计信息
            stats = self.get_statistics(bugs)
            
            # 生成HTML内容
            html_content = self.generate_html(bugs, stats)
            
            # 确定输出文件名
            if output_filename is None:
                output_filename = f"bug_report.html"
            
            # 确保文件名有.html扩展名
            if not output_filename.endswith('.html'):
                output_filename += '.html'
            
            # 写入文件
            output_path = os.path.join(self.output_dir, output_filename)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"报告已生成: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"生成报告失败: {e}")
            return ""

def main():
    """主函数"""
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    config = Config("config.json")
    # 生成报告
    generator = BugReportGenerator(config.projects, config.database_path,config.database_name)
    output_path = generator.generate_report()
    
    if output_path:
        print(f"✅ 报告生成成功: {output_path}")
        return 0
    else:
        print("❌ 报告生成失败")
        return 1

if __name__ == "__main__":
    exit(main()) 