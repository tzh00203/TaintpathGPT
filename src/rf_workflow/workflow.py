
from db_manager import *
from codeinfo_manager import *
from funcpair_analyzer import *
from llm_client import LLMClient
from bug_report_generator import BugReportGenerator
from utils import *
from rf_config import *


def main():
    logger = setup_logging()
    
    config = Config("./config/config.libjpeg.read_jpeg_file.json")
    config.ensure_directory()

    os.chdir(config.project_root)

    logger.info("=====step1: initialize LLM client=====")
    llm_client = LLMClient(config.ai_url,config.api_key,config.database_path)

    logger.info("=====step2: initialize bug report generator=====")
    bugreport = BugReportGenerator(config.projects, config.database_path,config.database_name)

    logger.info("=====step3: initialize database manager=====")
    db = DatabaseManager(config.database_path, config.database_name)

    logger.info("=====step4: initialize code info manager and generate database=====")
    codeinfo_mgr = CodeInfoManager(config.database_path, config.database_name, config.project_root, config.output_encoding,
                         config.input_encoding, config.code_input,db)
    codeinfo_mgr.genDatabase()
    codeinfo_mgr.build_base_info()
    

    # 更新数据库冗余函数代码
    db.update_duplicates_func(codeinfo_mgr.duplicates_func_dict)
    codeinfo_mgr.duplicates_func_dict={}
        
    # 定义入口攻击者可控字段，根据精简后的函数调用栈，将攻击者可控属性传递下去，并将代码中相应变量的判断条件添加到对应字段的说明中
    logger.info("=====step5: analyze functions and verify bugs=====")
    mode_ = config.mode 
    vul = funcpair_analyzer(bugreport,llm_client,db,codeinfo_mgr,config,mode_)
    #mode_ = config.mode  #config中定义漏洞挖掘模式 空间型内存破坏漏洞:0,时间型内存破坏漏洞:1,逻辑漏洞:2,...
    mode_ = 666   #暂时硬编码选择0
    vul.analysis_function_and_verify_bugs(mode_)
    logger.info("=====all steps completed=====")
    # db.close()


if __name__ == "__main__":
    main()
