            
from funcpair_analyzer import *


class SpaceRelatedVulnerabilityAnalyzer(funcpair_analyzer):
    #Space related memory corruption vulnerability

    def __init__(self,bugreport,llm_client,db,codeinfo_mgr,config,mode):
        super().__init__(bugreport,llm_client,db,codeinfo_mgr,config,mode)


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


    def analysis_function_core(self,ff, father_funcname, father_code, father_arg_list,
                               father_datastruct_list, father_function_var_list, datastruct_analyzed_dict,
                               findbug_analyzed_dict, analyzed_callpair_list):
        # 使用栈来替代递归
        print("analysis_function_core调用开始")
        stack = [
            (ff, father_funcname, father_code, father_arg_list, father_datastruct_list, father_function_var_list)]
        # print("[+] 进入core分析逻辑", str(ff), str(stack))
        while stack:
            # self.logger.info("analysis_function_core stack",stack)

            current_call = stack.pop()
            ff = current_call[0]
            father_funcname = current_call[1]
            father_code = current_call[2]
            father_arg_list = current_call[3]
            father_datastruct_list = current_call[4]
            father_function_var_list = current_call[5]

            # 大模型始终无法根据子函数调用列表来返回子函数，因此需要通过程序来补全子函数名称
            child_funcname = ff["函数名称"]
            arg_list = ff["参数列表"]

            complete_funcname = self.codeinfo_mgr.get_complete_funcname(father_funcname, child_funcname)  # 这里可能涉及多个子类函数，可能返回多个函数 todo
            func_name, scope = get_funcname_and_scope(complete_funcname)

            self.logger.info(f"father_child: {father_funcname}, {child_funcname}")
        
            # 暂时硬编码函数过滤列表，后续添加入config中
            if func_name in ["ADP_Logself.logger.info", "ADP_LogBuffself.logger.info"] or func_name.startswith("UgpLog"):
                continue
            # self.logger.info(f"func_name scope: {func_name} {scope}")
            # self.logger.info(f"datastruct_analyzed_dict: {datastruct_analyzed_dict}")
            # self.logger.info(f"arg_list1: {arg_list}")

            '''
            目前的datastruct_analyzed_dict形式是{'func_name1':(..),'func_name2':(..)}，存在A::X调用B::X，会不再分析B::X,
            因此这里将datastruct_analyzed_dict，转变成{('scope1::func_name1'):(..)}
            '''
            # elf.logger.info(f"[analysis_function_core]complete_funcname:{complete_funcname} arg_list:{arg_list}")

            self.logger.info(f"[analysis_function_core]complete_funcname:{complete_funcname} arg_list:{arg_list}")
            # 获得函数代码
            args_num = len(arg_list)
            codelist, scopelist = self.db.get_function_code(func_name, scope, args_num)
            self.logger.info(f"codelist_before req: {codelist}")

            for i in range(len(codelist)):
                duplicate_flag = True if i > 0 else False
                code = codelist[i]
                new_scope = scopelist[i] if i < len(scopelist) else scopelist[0] # TODO: 函数的对象范围待精进
                full_name = new_scope + "::" + func_name
                self.logger.info(f"full_name:{full_name}")
                
                if code != "":
                    # 获得函数相关的宏列表
                    # self.logger.info(f"core code now: {code}")
                    macro_list = self.codeinfo_mgr.get_macro_of_function(full_name if new_scope.strip() else func_name, self.call_macro_list, self.macro_macro_list)
                    # 将符合条件的子函数代码展开
                    # 深度搜索宏扩展
                    code, expand_function_list, child_macro_list = self.codeinfo_mgr.expand_function_code(
                                                                                                        full_name if new_scope.strip() else func_name, 
                                                                                                        code,
                                                                                                        self.call_macro_list,
                                                                                                        self.macro_macro_list,
                                                                                                        self.macro_func_list,
                                                                                                        self.call_pair_list
                                                                                                    )  
                    # 将子函数涉及的宏添加到函数宏列表中
                    for child_macro in child_macro_list:
                        macro_list.add(child_macro[1])
                    # 将函数宏列表展开添加到code后
                    code = code + "\n" + self.codeinfo_mgr.get_macro_code(macro_list)

                    # # 获得函数的子函数列表
                    # child_list = self.codeinfo_mgr.get_child_of_function(func_name, self.call_pair_list)
                    # 获得函数相关的数据结构和变量
                    datastruct_list, function_var_list = self.codeinfo_mgr.get_datastruct_of_function(complete_funcname, arg_list,
                                                                                    self.reference_variable_list)
                    # self.logger.info("analysis_function_core datastruct_list,function_var_list:", datastruct_list, function_var_list)

                    prompt = network_recvfunc_code_s(code,
                                                     json.dumps(arg_list, ensure_ascii=False),
                                                     json.dumps(datastruct_list, ensure_ascii=False),
                                                     json.dumps(function_var_list, ensure_ascii=False), self.ext_info)

                    if full_name in datastruct_analyzed_dict.keys() and (len(datastruct_analyzed_dict[full_name])-1) == i :  # TODO: complete_funcname or func_name ?看更多的项目 todo
                        continue
                    else:
                        rsp = self.llm_client.llm_request(prompt, "req", father_funcname, func_name)
                        datastruct_analyzed_dict.setdefault(full_name, []).append(rsp)
                        self.codeinfo_mgr.save_analyzed_dict("datastruct_analyzed_dict", datastruct_analyzed_dict)  # for断点续传

                    if rsp[0] != "":
                        try:
                            analysis_json = json.loads(rsp[0])
                            analysis_json = self.codeinfo_mgr.update_func_pointer_var(analysis_json, func_name)
                            self.logger.info("network_recvfunc_code_s=====:", analysis_json)
                        except json.decoder.JSONDecodeError as e:
                            self.logger.error(f"network_recvfunc_code_s entry_json =json.loads(json_str) error:{e}")

                            continue

                        self.reference_variable_list = self.codeinfo_mgr.update_llm_result(analysis_json.get("数据结构", []), 
                                                                                           duplicate_flag,
                                                                                           func_name,
                                                                                           self.reference_variable_list
                                                                                           )

                        # update_llm_result会更新数据结构的描述，因此调用get_datastruct_of_function获得最新的数据结构
                        
                        datastruct_list, function_var_list = self.codeinfo_mgr.get_datastruct_of_function(complete_funcname,
                                                                                        arg_list,
                                                                                        self.reference_variable_list)

                        # 暂时硬编码漏洞分析函数过滤列表，后续添加入config中
                        if func_name.startswith('Ugp') or func_name.startswith('UJson'):
                            pass
                        else:
                            for bug_model_id in bug_models:

                                prompt = find_bug(code, json.dumps(arg_list, ensure_ascii=False),
                                                  json.dumps(datastruct_list, ensure_ascii=False),
                                                  json.dumps(function_var_list, ensure_ascii=False),
                                                  father_code,
                                                  json.dumps(father_arg_list, ensure_ascii=False),
                                                  json.dumps(father_datastruct_list, ensure_ascii=False),
                                                  json.dumps(father_function_var_list, ensure_ascii=False),
                                                  bug_models[bug_model_id], self.ext_info)
                                findbug_analyzed_flag = full_name + "_" + bug_model_id
                                if findbug_analyzed_flag in findbug_analyzed_dict.keys() and len(findbug_analyzed_dict[findbug_analyzed_flag]) == (len(codelist)*len(bug_models)):
                                    # 该函数已分析过，不再重复寻找漏洞

                                    pass
                                else:
                                    rsp = self.llm_client.llm_request(prompt, "findbug req", father_funcname, func_name)

                                    if rsp[0] != "":
                                        try:
                                            findbug_json = parse_json_safe(rsp[0], self.logger)
                                            if not findbug_json:
                                                continue
                                            # self.logger.info("findbug_json:",findbug_json,rsp[1])
                                            eva_rsp = self.llm_client.evaluate_process(prompt, rsp[0], rsp[1],
                                                                                  father_funcname, func_name)
                                            if eva_rsp != "error":
                                                # 大模型2评估大模型1执行任务的结果是对的，返回原来正确的结果，并退出该函数
                                                if eva_rsp.get("结果", "").lower() == "success" and self.check_bug(
                                                        findbug_json):

                                                    # self.logger.info("find bug result after evaluate:", findbug_json, rsp[1])

                                                    self.logger.info("find bug result after evaluate:", findbug_json, rsp[1])
                                                    # 先判断是否是特定误报，如果不是，则上报漏洞

                                                    prompt = eliminate_false_positives(code, father_code,
                                                                                       json.dumps(arg_list,
                                                                                                  ensure_ascii=False),
                                                                                       json.dumps(datastruct_list,
                                                                                                  ensure_ascii=False),
                                                                                       json.dumps(function_var_list,
                                                                                                  ensure_ascii=False),
                                                                                       findbug_json, rsp[1])

                                                    efp_rsp = self.llm_client.llm_request(prompt,
                                                                                     "eliminate_false_positives",
                                                                                     father_funcname, func_name)
                                                    if efp_rsp[0] != "":
                                                        self.logger.info(f"eliminate_false_positives:{efp_rsp[0]}")
                                                        eliminate_res = json.loads(efp_rsp[0])
                                                        if eliminate_res.get("是否误报", True) == False:
                                                            self.report_bug(findbug_json, func_name, rsp[1], rsp[2],
                                                                       bug_model_id)
                                                            # db.insert_bugreport(1, func_name, "eliminate_false_positives:"+rsp[0], rsp[1], os.path.basename(rsp[2]), bug_model_id)
                                                            # 更新bug_report.html
                                                            self.bugreport.generate_report()
                                                else:
                                                    self.logger.info(f"find bug result after evaluate maybe wrong:{findbug_json},{rsp[1]},{eva_rsp}")
                                            else:
                                                self.logger.error("eva_rsp return error")
                                        except json.decoder.JSONDecodeError as e:
                                            self.logger.error(f"find_bug entry_json =json.loads(json_str) {e}")
                                    else:
                                        self.logger.error("find bug error:json_str is null")

                                    findbug_analyzed_dict.setdefault(findbug_analyzed_flag, []).append(rsp[0])
                                    self.codeinfo_mgr.save_analyzed_dict("findbug_analyzed_dict",
                                                       findbug_analyzed_dict)  # for断点续传

                        for fff in reversed(analysis_json.get("函数调用", [])):
                            if fff.get("函数名称", "") != "" and fff.get("函数名称", "") != full_name and fff.get(
                                    "函数名称", "") not in expand_function_list:
                                '''
                                   这里添加函数指针相关的处理，逻辑：添加一次判断，如果func_name是个函数，那就正常获得code，如果是个变量，就进入函数指针的处理，
                                   函数指针的处理逻辑，查引用，找赋值，直接替换
                                '''
                                child_name = fff.get("函数名称", "")
                                real_funclist = [child_name]
                                child_func_name, child_scope = get_funcname_and_scope(child_name)
                                self.logger.info("Is_function func:" + str(child_func_name) + " " +str(self.db.is_function(child_func_name)))
                                if not self.db.is_function(child_func_name):
                                    real_funclist = self.codeinfo_mgr.getPointerRefFuncName(child_func_name)
                                for func in real_funclist:
                                    fff["函数名称"] = func
                                    self.logger.info(f"from {full_name} to {func}")
                                    analyzed_callpair_list.append((func_name, func, list(expand_function_list)))
                                    self.codeinfo_mgr.save_analyzed_callpair_list(analyzed_callpair_list)
                                    stack.append((fff, complete_funcname, code, arg_list, datastruct_list,
                                                  function_var_list))

                    else:
                        self.logger.error("analysis_function_core:json_str is null")

                else:
                    self.logger.error("analysis_function_core:code is null")

    def run(self):

        target_func_list = self.target_func_list_str

        entry_func_dict = self.entry_func_dict_str

        self.logger.info("logggg vulnscan target func: " + str(target_func_list))
        
        self.logger.info("logggg vulnscan target entry func: " + str(entry_func_dict))

        for target in target_func_list:
            entry_func_dict["名称"] = target
            # self.logger.info("analysis_function_and_find_bugs",entry_func_dict)

            datastruct_analyzed_dict = self.codeinfo_mgr.read_analyzed_dict("datastruct_analyzed_dict")
            findbug_analyzed_dict = self.codeinfo_mgr.read_analyzed_dict("findbug_analyzed_dict")
            analyzed_callpair_list = self.codeinfo_mgr.read_analyzed_callpair_list()
            # self.logger.info("========logggg vulnscan callpair list: " + str(analyzed_callpair_list))
           
            complete_funcname = entry_func_dict.get("名称", "")
            arg_list = entry_func_dict.get("字段", [])
            self.logger.info(f"analysis_function_and_find_bugs complete_funcname:{complete_funcname} {arg_list}")

            func_name, scope = get_funcname_and_scope(complete_funcname)
            # 获得函数代码
            args_num = len(arg_list)
            codelist, scopelist = self.db.get_function_code(func_name, scope, args_num)
            # print(type(codelist), len(codelist))
            codelist = list(set(codelist))
            self.logger.info("logggg vulnscan codelist: " + str(codelist))
            for i in range(len(codelist)):
                code = codelist[i]
                new_scope = scopelist[i] if len(scopelist) > i else scopelist[0]
                full_name = new_scope + "::" + func_name
                print(full_name)
                
                if code != "":
                    # 获得函数相关的宏列表

                    macro_list = self.codeinfo_mgr.get_macro_of_function(full_name if new_scope.strip() else func_name, self.call_macro_list, self.macro_macro_list)
                    # 将符合条件的子函数代码展开
                    # 深度搜索宏扩展
                    code, expand_function_list, child_macro_list = self.codeinfo_mgr.expand_function_code(
                                                                                    full_name if new_scope.strip() else func_name, 
                                                                                    code,
                                                                                    self.call_macro_list,
                                                                                    self.macro_macro_list,
                                                                                    self.macro_func_list,
                                                                                    self.call_pair_list
                                                                                )
                    # self.logger.info("expand_function_list:", func_name, expand_function_list)
                    # self.logger.info("child_macro_list", child_macro_list)
                    # self.logger.info("macro_list:", macro_list)

                    self.logger.info(f"expand_function_list:{func_name} {expand_function_list}")
                    self.logger.info(f"child_macro_list:{child_macro_list}")
                    self.logger.info(f"macro_list:{macro_list}")

                    # 将子函数涉及的宏添加到函数宏列表中
                    for child_macro in child_macro_list:
                        macro_list.add(child_macro[1])
                    # 将函数宏列表展开添加到code后
                    code = code + "\n" + self.codeinfo_mgr.get_macro_code(macro_list)

                    # 获得函数的子函数列表
                    # child_list = self.codeinfo_mgr.get_child_of_function(func_name, self.call_pair_list)
                    # self.logger.info("refer_var_list: "+ str(self.reference_variable_list))
                    datastruct_list, function_var_list = self.codeinfo_mgr.get_datastruct_of_function(complete_funcname, arg_list,
                                                                                    self.reference_variable_list)
                    # self.logger.info("analysis_function_and_find_bugs datastruct_list,function_var_list:", datastruct_list, function_var_list)
                    prompt = network_recvfunc_code_s(code,
                                                     json.dumps(arg_list, ensure_ascii=False),
                                                     json.dumps(datastruct_list, ensure_ascii=False),
                                                     json.dumps(function_var_list, ensure_ascii=False), self.ext_info)

                    if full_name in datastruct_analyzed_dict.keys() and len(datastruct_analyzed_dict[full_name]) == len(codelist):  # TODO: complete_funcname or func_name ?看更多的项目 todo
                        rsp = datastruct_analyzed_dict[full_name][i]
                    else:         
                        rsp = self.llm_client.llm_request(prompt, "req", "null", func_name)

                        datastruct_analyzed_dict.setdefault(full_name, []).append(rsp)
                        self.codeinfo_mgr.save_analyzed_dict("datastruct_analyzed_dict", datastruct_analyzed_dict)  # for断点续传
                    
                    if rsp[0] != "":
                        try:
                            self.logger.info("json_str:",rsp[0])
                            entry_json = json.loads(rsp[0])
                            # self.logger.info("analysis_function_and_find_bugs entry_json:", entry_json)
                        except json.decoder.JSONDecodeError as e:
                            continue
                            
                        self.codeinfo_mgr.update_llm_result(entry_json.get("数据结构", []))
                        self.codeinfo_mgr.update_func_pointer_var(entry_json, target)
                        # print(self.codeinfo_mgr.func_pointer2var_dict)
                        for fff in entry_json.get("函数调用", []):  #

                            self.codeinfo_mgr.update_llm_result(entry_json.get("数据结构", []))
                            # print("==========================================\n", entry_json, "\n============================================")
                       
                            if fff.get("函数名称", "") != "" and fff.get("函数名称", "") != full_name and fff.get(
                                    "函数名称", "") not in expand_function_list:
                                child_name = fff.get("函数名称", "")
                                real_funclist = [child_name]
                                child_func_name, child_scope = get_funcname_and_scope(child_name)
                                if not self.db.is_function(child_func_name):
                                    
                                    # real_funclist = self.codeinfo_mgr.getPointerRefFuncName(child_func_name)
                                    pass
                                    
                                for func in real_funclist:
                                    fff["函数名称"] = func
                                    self.logger.info(f"from {full_name} to {func}")
                                    analyzed_callpair_list.append((func_name, func, list(expand_function_list)))
                                    self.codeinfo_mgr.save_analyzed_callpair_list(analyzed_callpair_list)

                                self.analysis_function_core(fff, complete_funcname, code,
                                                       arg_list, datastruct_analyzed_dict, function_var_list,
                                                       datastruct_analyzed_dict, findbug_analyzed_dict,
                                                       analyzed_callpair_list)  # ,entry_json["函数局部变量"]
                    else:
                        self.logger.error("analysis_function_and_find_bugs:json_str is null")
                else:
                    self.logger.error("analysis_function_and_find_bugs:code is null")

class TimeRelatedVulnerabilityAnalyzer(funcpair_analyzer):
    #Time related memory corruption vulnerability
    def __init__(self,bugreport,llm_client,db,codeinfo_mgr,config):
        super().__init__(bugreport,llm_client,db,codeinfo_mgr,config)

        self.call_pair_list = codeinfo_mgr.call_pair_list
        self.call_macro_list = codeinfo_mgr.call_macro_list
        self.reference_variable_list = codeinfo_mgr.reference_variable
        self.macro_macro_list = codeinfo_mgr.macro_macro_list
        self.macro_func_list = codeinfo_mgr.macro_func_list

        self.target_func_list = config.target_func_list
        self.entry_func_dict = config.entry_func_dict
        self.ext_info = config.ext_info

        self.logger = logging.getLogger(__name__)

    def run(self):
        self.logger.info("Start TimeRelatedVulnerabilityAnalyzer todo")

