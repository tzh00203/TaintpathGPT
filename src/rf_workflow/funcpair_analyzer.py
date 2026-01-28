
import logging
from utils import *
from llm_prompt import *
from analyzer_findbugs import *

class funcpair_analyzer:
    def __init__(self, bugreport, llm_client, db, codeinfo_mgr, config, mode):
        self.bugreport = bugreport
        self.llm_client = llm_client
        self.db = db
        self.codeinfo_mgr = codeinfo_mgr
        self.config = config
        self.logger = logging.getLogger(__name__)

    def analysis_function_and_verify_bugs(self, mode):
        if mode in (0, 2):
            return SpaceRelatedVulnerabilityAnalyzer(
                self.bugreport, self.llm_client, self.db,
                self.codeinfo_mgr, self.config, mode
            ).run()
        elif mode == 1:
            return TimeRelatedVulnerabilityAnalyzer(
                self.bugreport, self.llm_client, self.db,
                self.codeinfo_mgr, self.config
            ).run()
        else:
            return FunctionPairAnalyzer(
                self.bugreport, self.llm_client, self.db,
                self.codeinfo_mgr, self.config, mode
            ).run()

    def check_bug(self, findbug_json):
        """检查JSON是否表示有效漏洞（置信度>75%）"""
        isbug = findbug_json.get("是否确定漏洞", False)
        confidence = float(findbug_json.get("置信度", "0%").replace("%", "")) / 100
        return isbug and confidence > 0.75

    def report_bug(self, findbug_json, func_name, vul_reason, logname, bug_model):
        """上报漏洞到数据库"""
        if self.check_bug(findbug_json):
            confidence = float(findbug_json.get("置信度", "0%").replace("%", "")) / 100
            self.db.insert_bugreport(
                confidence, func_name, findbug_json.get("漏洞描述", ""),
                vul_reason, os.path.basename(logname), bug_model
            )
            return True
        return False
    

class FunctionPairAnalyzer(funcpair_analyzer):
    
    def __init__(self, bugreport, llm_client, db, codeinfo_mgr, config, mode):
        super().__init__(bugreport, llm_client, db, codeinfo_mgr, config, mode)
        self.call_pair_list = codeinfo_mgr.call_pair_list
        self.call_macro_list = codeinfo_mgr.call_macro_list
        self.reference_variable_list = codeinfo_mgr.reference_variable
        self.macro_macro_list = codeinfo_mgr.macro_macro_list
        self.macro_func_list = codeinfo_mgr.macro_func_list

        self.target_func_list_str = config.target_func_list
        self.entry_func_dict_str = config.entry_func_dict
        self.ext_info = config.ext_info
        self.mode = mode

        self.logger = logging.getLogger(__name__)

    def process_function_code(self, code, func_name, full_name, new_scope, expand_function_list):
        if code:
            macro_list = self.codeinfo_mgr.get_macro_of_function(full_name, self.call_macro_list, self.macro_macro_list)
            code, expand_function_list, child_macro_list = self.codeinfo_mgr.expand_function_code(
                full_name, code, self.call_macro_list, self.macro_macro_list, self.macro_func_list, self.call_pair_list)

            # 将子函数涉及的宏添加到宏列表
            for child_macro in child_macro_list:
                macro_list.add(child_macro[1])

            code += "\n" + self.codeinfo_mgr.get_macro_code(macro_list)
            return code, expand_function_list
        return None, expand_function_list

    def analyze_function(self, func_name, code, expand_function_list, complete_funcname, arg_list):
        # 获取函数相关的数据结构和变量
        datastruct_list, function_var_list = self.codeinfo_mgr.get_datastruct_of_function(complete_funcname, arg_list, self.reference_variable_list)
        prompt = network_recvfunc_code_s(code,
                                         json.dumps(arg_list, ensure_ascii=False),
                                         json.dumps(datastruct_list, ensure_ascii=False),
                                         json.dumps(function_var_list, ensure_ascii=False), self.ext_info)

        return prompt, datastruct_list, function_var_list

    def handle_rsp(self, rsp, full_name, func_name, codelist, datastruct_analyzed_dict, datastruct_list, function_var_list, analyzed_callpair_list):
        if rsp[0] != "":
            try:
                analysis_json = json.loads(rsp[0])
                analysis_json = self.codeinfo_mgr.update_func_pointer_var(analysis_json, func_name)
                self.logger.info("network_recvfunc_code_s=====:", analysis_json)
            except json.decoder.JSONDecodeError as e:
                self.logger.error(f"Error decoding JSON: {e}")
                return

            self.reference_variable_list = self.codeinfo_mgr.update_llm_result(analysis_json.get("数据结构", []), True, func_name, self.reference_variable_list)

            # Update datastruct
            datastruct_list, function_var_list = self.codeinfo_mgr.get_datastruct_of_function(full_name, datastruct_list, self.reference_variable_list)
            
            for fff in analysis_json.get("函数调用", []):
                self.process_function_call(fff, full_name, expand_function_list, analyzed_callpair_list)

    def process_function_call(self, fff, full_name, expand_function_list, analyzed_callpair_list):
        child_name = fff.get("函数名称", "")
        real_funclist = [child_name]
        child_func_name, child_scope = get_funcname_and_scope(child_name)

        if not self.db.is_function(child_func_name):
            pass

        for func in real_funclist:
            fff["函数名称"] = func
            self.logger.info(f"from {full_name} to {func}")
            analyzed_callpair_list.append((full_name, func, list(expand_function_list)))
            self.codeinfo_mgr.save_analyzed_callpair_list(analyzed_callpair_list)

    def analysis_function_core(self, ff, father_funcname, father_code, father_arg_list, father_datastruct_list,
                               father_function_var_list, datastruct_analyzed_dict, findbug_analyzed_dict, analyzed_callpair_list):
        print("analysis_function_core调用开始")
        stack = [(ff, father_funcname, father_code, father_arg_list, father_datastruct_list, father_function_var_list)]
        
        while stack:
            current_call = stack.pop()
            ff = current_call[0]
            father_funcname = current_call[1]
            father_code = current_call[2]
            father_arg_list = current_call[3]
            father_datastruct_list = current_call[4]
            father_function_var_list = current_call[5]

            child_funcname = ff["函数名称"]
            arg_list = ff["参数列表"]

            complete_funcname = self.codeinfo_mgr.get_complete_funcname(father_funcname, child_funcname)
            func_name, scope = get_funcname_and_scope(complete_funcname)

            self.logger.info(f"father_child: {father_funcname}, {child_funcname}")

            if func_name.startswith("UgpLog"):
                continue

            self.logger.info(f"[analysis_function_core]complete_funcname:{complete_funcname} arg_list:{arg_list}")

            args_num = len(arg_list)
            codelist, scopelist = self.db.get_function_code(func_name, scope, args_num)
            self.logger.info(f"codelist_before req: {codelist}")

            for i in range(len(codelist)):
                code = codelist[i]
                new_scope = scopelist[i] if i < len(scopelist) else scopelist[0]
                full_name = new_scope + "::" + func_name

                code, expand_function_list = self.process_function_code(code, func_name, full_name, new_scope, expand_function_list)

                if code:
                    prompt, datastruct_list, function_var_list = self.analyze_function(func_name, code, expand_function_list, complete_funcname, arg_list)

                    if full_name not in datastruct_analyzed_dict.keys() or len(datastruct_analyzed_dict[full_name]) != len(codelist):
                        rsp = self.llm_client.llm_request(prompt, "req", "null", func_name)
                        datastruct_analyzed_dict.setdefault(full_name, []).append(rsp)
                        self.codeinfo_mgr.save_analyzed_dict("datastruct_analyzed_dict", datastruct_analyzed_dict)

                    self.handle_rsp(rsp, full_name, func_name, codelist, datastruct_analyzed_dict, datastruct_list, function_var_list, analyzed_callpair_list)

    def run(self):
        target_func_list = self.target_func_list_str
        entry_func_dict = self.entry_func_dict_str

        self.logger.info(f"logggg vulnscan target func: {str(target_func_list)}")
        self.logger.info(f"logggg vulnscan target entry func: {str(entry_func_dict)}")

        for target in target_func_list:
            entry_func_dict["名称"] = target
            datastruct_analyzed_dict = self.codeinfo_mgr.read_analyzed_dict("datastruct_analyzed_dict")
            findbug_analyzed_dict = self.codeinfo_mgr.read_analyzed_dict("findbug_analyzed_dict")
            analyzed_callpair_list = self.codeinfo_mgr.read_analyzed_callpair_list()

            complete_funcname = entry_func_dict.get("名称", "")
            arg_list = entry_func_dict.get("字段", [])
            self.logger.info(f"analysis_function_and_find_bugs complete_funcname:{complete_funcname} {arg_list}")

            func_name, scope = get_funcname_and_scope(complete_funcname)
            args_num = len(arg_list)
            codelist, scopelist = self.db.get_function_code(func_name, scope, args_num)

            codelist = list(set(codelist))
            self.logger.info(f"logggg vulnscan codelist: {str(codelist)}")

            for i in range(len(codelist)):
                code = codelist[i]
                new_scope = scopelist[i] if len(scopelist) > i else scopelist[0]
                full_name = new_scope + "::" + func_name

                if code != "":
                    macro_list = self.codeinfo_mgr.get_macro_of_function(full_name, self.call_macro_list, self.macro_macro_list)
                    code, expand_function_list, child_macro_list = self.codeinfo_mgr.expand_function_code(
                        full_name, code, self.call_macro_list, self.macro_macro_list, self.macro_func_list, self.call_pair_list
                    )

                    self.logger.info(f"expand_function_list:{expand_function_list}")
                    self.logger.info(f"child_macro_list:{child_macro_list}")
                    self.logger.info(f"macro_list:{macro_list}")

                    for child_macro in child_macro_list:
                        macro_list.add(child_macro[1])

                    code = code + "\n" + self.codeinfo_mgr.get_macro_code(macro_list)

                    datastruct_list, function_var_list = self.codeinfo_mgr.get_datastruct_of_function(complete_funcname, arg_list, self.reference_variable_list)

                    prompt = network_recvfunc_code_s(code, json.dumps(arg_list, ensure_ascii=False), json.dumps(datastruct_list, ensure_ascii=False), json.dumps(function_var_list, ensure_ascii=False), self.ext_info)

                    if full_name not in datastruct_analyzed_dict.keys() or len(datastruct_analyzed_dict[full_name]) != len(codelist):
                        rsp = self.llm_client.llm_request(prompt, "req", "null", func_name)
                        datastruct_analyzed_dict.setdefault(full_name, []).append(rsp)
                        self.codeinfo_mgr.save_analyzed_dict("datastruct_analyzed_dict", datastruct_analyzed_dict)

                    self.handle_rsp(rsp, full_name, func_name, codelist, datastruct_analyzed_dict, datastruct_list, function_var_list, analyzed_callpair_list)
