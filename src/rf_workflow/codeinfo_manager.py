import sqlite3
from utils import *
import shutil
import re
from collections import defaultdict


INLINE_FUNCTION_LINE_NUM = 5


class CodeInfoManager:
    def __init__(self,database_path, database_name,project_root,output_encoding, input_encoding, code_input,db):
        self.database_path = database_path
        self.database_name = database_name
        self.project_root = project_root
        self.output_encoding = output_encoding
        self.input_encoding = input_encoding
        self.code_input = code_input
        self.db = db

        self.call_pair_list = []
        self.call_macro_list = []
        self.macro_macro_list = []
        self.macro_func_list = []
        self.reference_variable = []
        self.typedef_base_type_dict = {}
        self.call_graph = {}

        self.duplicates_func_dict = self.get_duplicates_func(code_input)
        
        
        # # code_info_mgr维护变量到函数指针的映射表 和 函数指针到变量的映射表，通过识别到的变量类型(函数指针 -- 变量名)实现对函数间接调用关系的维护
        self.var2func_pointer_dict = {}
        self.func_pointer2var_dict = {}
        self.logger = logging.getLogger(__name__)

    def genDatabase(self):
        '''
        使用Doxygen创建代码数据库
        '''

        if os.path.exists(os.path.join(self.database_path, self.database_name)):
            self.logger.info('Database already exists')
            return

        print('[genDatabase] 开始创建数据库')

        # if os.path.exists(os.path.join(self.database_path, self.database_name)):
        #     self.logger.info('Database already exists')
        #     return

        self.logger.info('[genDatabase] 开始创建数据库')

        convert_files_to_utf8(self.code_input) # 改变项目编码方式
        with open('Doxyfile', "r") as f:
            lines = f.readlines()

        print(self.database_name, self.output_encoding, self.input_encoding, self.code_input)

        for i, line in enumerate(lines):
            # 匹配以 OUTPUT_DIRECTORY 开头的行（忽略大小写和前后空格）
            # self.logger.info(line,type(line))
            if re.match(r'^\s*OUTPUT_DIRECTORY\s*=', line, re.IGNORECASE):
                # 替换为新路径（保留原有格式，如引号）
                lines[i] = re.sub(r'=\s*.*', f'= {self.database_path}', line)
            elif re.match(r'^\s*DOXYFILE_ENCODING\s*=', line, re.IGNORECASE):
                lines[i] = re.sub(r'=\s*.*', f'= {self.output_encoding}', line)
            elif re.match(r'^\s*INPUT_ENCODING\s*=', line, re.IGNORECASE):
                lines[i] = re.sub(r'=\s*.*', f'= {self.input_encoding}', line)
            elif re.match(r'^\s*INPUT\s*=', line, re.IGNORECASE):
                lines[i] = re.sub(r'=\s*.*', f'= {self.code_input}', line)
        with open('Doxyfile', "w") as f:
            f.writelines(lines)

        self.logger.info(f"doxygen Doxyfile")

        exit_code = os.system(f"doxygen Doxyfile")
        if exit_code == 0:
            src = self.database_path + "/sqlite3/" + self.database_name
            dst = self.database_path + "/" + self.database_name
            shutil.copy(src, dst)
        return exit_code

    def update_func_pointer_var(self, llm_result_json, father_func=None):
        """
        将llm识别结果中的函数指针信息保存,更新到类实例中
        目标是: 1. 子函数能够通过参数的初始化名称直接通过字典查到对应的函数指针有哪些
                2. 维护要查找的函数指针字典
        """
        func_pointer_pattern = r'\w+\s*\(\*\w*\)\s*\([^)]*\)\s*'
        var_info_list = llm_result_json.get("函数局部变量",{})
        # 每次需要清空局部函数对变量到函数的赋值
        self.var2func_pointer_dict = {}
        input_arg_dict = {}
        
        # 对识别到的函数内局部变量的赋值以及是否为入参临时维护一个字典服务函数调用的处理
        for var_tmp in var_info_list:
            name_tmp = var_tmp.get("名称", "")
            type_tmp = var_tmp.get("类型","")
            des_tmp = var_tmp.get("说明", "")
            value_tmp = var_tmp.get("值", "")  # 是一个list
            var_fullname = father_func + ":" + name_tmp
            
            self.logger.info("in pointer update: " + var_fullname)
            
            if re.match(func_pointer_pattern, type_tmp.strip()) or "函数指针" in des_tmp:
                self.var2func_pointer_dict.setdefault(var_fullname, []).extend(value_tmp)
                self.var2func_pointer_dict[var_fullname] = [ nn for nn in 
                                                            list(set(self.var2func_pointer_dict[var_fullname])) 
                                                            if self.db.is_function(nn) ]
            if var_tmp.get("入参", False) or var_tmp.get("入参索引", None):
                input_arg_dict[name_tmp] = var_tmp.get("入参索引", None)
        self.logger.info("in pointer update: " + str(self.var2func_pointer_dict))     
        self.logger.info("in pointer update input args: " + str(input_arg_dict))         
        refer_func_list = []
        child_func_list = llm_result_json.get("函数调用",{})
        
        for child_func_tmp in child_func_list:
            child_name_tmp = child_func_tmp.get("函数名称", "")
            child_name_func_tmp, child_name_scope_tmp = get_funcname_and_scope(child_name_tmp)
            
            if not self.db.is_function(child_name_func_tmp):
                refer_list_tmp = (
                     # 目标1：如果执行的函数指针变量是入参，在维护的字典中查找对应的真实函数指针
                    self.func_pointer2var_dict.get(father_func + ":" + str(input_arg_dict[child_name_func_tmp]), [])
                    if child_name_func_tmp in input_arg_dict
                    # 目标1：如果使用的是函数指针变量执行子函数，查找变量对应的真实函数指针
                    else self.var2func_pointer_dict.get(father_func + ":" + child_name_func_tmp, [])
                )
                
                for rr in set(refer_list_tmp):  # 直接用set去重
                    if not self.db.is_function(rr) and rr in input_arg_dict:
                        rr_l = self.func_pointer2var_dict.get(father_func + ":" + str(input_arg_dict[child_name_func_tmp]), [])
                        for item in rr_l:
                            refer_func_list.append({
                                **child_func_tmp,
                                "函数名称": item 
                            })
                    elif self.db.is_function(rr):
                        refer_func_list.append({
                            **child_func_tmp,  # 使用解包语法简化字典复制
                            "函数名称": rr
                        })

            # 目标2：在调用的子函数中，把传入的函数指针都维护在本地
            for arg_tmp in child_func_tmp.get("参数列表", []):
                arg_type_tmp = arg_tmp.get("类型", "")
                arg_index_tmp = arg_tmp.get("索引", None)
                arg_name_tmp = arg_tmp.get("名称","")
                func_, scope_ = get_funcname_and_scope(arg_name_tmp)
                arg_fullname_tmp = child_name_func_tmp + ":" + func_
                # 如果子函数传入的参数是真的函数指针，直接维护在字典
                if self.db.is_function(func_):
                    self.func_pointer2var_dict.setdefault(child_name_func_tmp + ":" + str(arg_index_tmp), []).append(func_)
                
                # 如果传入的参数是指针变量，通过字典找真实
                elif re.match(func_pointer_pattern, arg_type_tmp.strip()) or "函数指针" in arg_tmp.get("说明", ""):
                    var_fullname_tmp = father_func + ":" + arg_name_tmp
                    self.logger.info("传入的参数是指针变量，通过字典找真实"+str(arg_name_tmp))
                    if arg_name_tmp in input_arg_dict:
                        self.logger.info("变量为入参： "+str(arg_name_tmp)+" child_name: " + child_name_tmp)
                        index_tmp = input_arg_dict[arg_name_tmp]
                        self.func_pointer2var_dict.setdefault(child_name_tmp + ":" + str(arg_index_tmp), []).extend(
                            self.func_pointer2var_dict.get(father_func + ":" + str(index_tmp), [])
                        )
                        continue
                    if "var_fullname_tmp" not in self.var2func_pointer_dict:continue
                    for refer_func_tmp in self.var2func_pointer_dict[var_fullname_tmp]:
                        if self.db.is_function(refer_func_tmp):
                            self.func_pointer2var_dict.setdefault(child_name_func_tmp + ":" + str(arg_index_tmp), []).append(refer_func_tmp)

        llm_result_json["函数调用"].extend(refer_func_list)
        self.logger.info("in pointer update func2var: " + str(self.func_pointer2var_dict))     
        return llm_result_json
            
    
    def get_duplicates_func(self, project_path):
        
        """
        冗余函数字典格式:
            {
                func_1: [
                    {'line': , 'body': str }
                ]
            }
        """
        
        duplicates_func_dict = {}
        
        
        for root, dirs, files in os.walk(project_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                duplicates_func_dict.update(find_duplicate_functions(file_path)) 
    
        return duplicates_func_dict

    def build_base_info(self):
        '''
        创建基础目标信息
        '''

        # make_target_list(target_files_path, main_target)
        self.logger.info("start build_base_info")
        # 创建函数数据库
        self.db.create_table()
        self.db.clean_db()

        self.call_pair_list = self.get_call_pair()
        self.call_macro_list = self.get_call_macro()
        self.macro_macro_list = self.get_macro_macro()
        self.macro_func_list = self.get_macro_func()
        self.reference_variable = self.get_reference_variable()
        self.typedef_base_type_dict = self.get_all_macro_def()
        self.call_graph = self.get_callgraph()
        # 对doxygen生成的初始数据库进行
        if self.db.is_object_exits("flag_update_all_function_code_into_db_done") == False:
            self.logger.info("start update_all_function_code")
            self.update_all_function_code_into_db()

        self.logger.info("update_all_function_code has done")

    def get_call_pair(self):
        if self.db.is_object_exits("callpair_list"):
            self.logger.info("callpair_list 已存在数据库，直接读取")
            call_pair = self.db.get_json_object("callpair_list").decode('utf-8')
            call_pair_list = json.loads(call_pair)
        else:
            self.logger.info("创建callpair_list...")
            call_pair_list = self.db.get_sqlite_call()
            self.db.insert_json_object("callpair_list", json.dumps(call_pair_list, ensure_ascii=False).encode('utf-8'))
        return call_pair_list

    def get_call_macro(self):
        if self.db.is_object_exits("call_macro"):
            self.logger.info("call_macro_list 已存在数据库，直接读取")
            call_macro = self.db.get_json_object("call_macro").decode('utf-8')
            call_macro_list = json.loads(call_macro)
        else:
            self.logger.info("创建call_macro_list...")
            call_macro_list = self.db.get_func_and_macro()
            self.db.insert_json_object("call_macro", json.dumps(call_macro_list, ensure_ascii=False).encode('utf-8'))
        return call_macro_list

    def get_macro_macro(self):
        if self.db.is_object_exits("macro_macro"):
            self.logger.info("macro_macro_list 已存在数据库，直接读取")
            macro_macro = self.db.get_json_object("macro_macro").decode('utf-8')
            macro_macro_list = json.loads(macro_macro)
        else:
            self.logger.info("创建macro_macro_list...")
            macro_macro_list = self.db.get_macro_and_macro()
            self.db.insert_json_object("macro_macro", json.dumps(macro_macro_list, ensure_ascii=False).encode('utf-8'))
        return macro_macro_list

    def get_macro_func(self):
        if self.db.is_object_exits("macro_func"):
            self.logger.info("macro_func_list 已存在数据库，直接读取")
            macro_func = self.db.get_json_object("macro_func").decode('utf-8')
            macro_func_list = json.loads(macro_func)
        else:
            self.logger.info("创建macro_func_list...")
            macro_func_list = self.db.get_macro_and_func()
            self.db.insert_json_object("macro_func", json.dumps(macro_func_list, ensure_ascii=False).encode('utf-8'))
        return macro_func_list

    def get_reference_variable(self):
        '''
        获得函数相关的变量
        '''
        if self.db.is_object_exits("reference_variable"):

            self.logger.info("获得函数相关的变量,reference_variable 已存在数据库，直接读取")
            self.logger.info("reference_variable 已存在数据库，直接读取")

            reference_variable = self.db.get_json_object("reference_variable").decode('utf-8')
            reference_variable_list = json.loads(reference_variable)
        else:
            self.logger.info("创建reference_variable...")
            reference_variable_list = self.db.get_reference_variable()
            self.db.insert_json_object("reference_variable",
                                  json.dumps(reference_variable_list, ensure_ascii=False).encode('utf-8'))
        return reference_variable_list

    def get_callgraph(self):

        if self.db.is_object_exits("callgraph"):
            self.logger.info("callgraph 已存在数据库，直接读取")
            call_graph_value = self.db.get_json_object("callgraph").decode('utf-8')
            graph = json.loads(call_graph_value)
        else:
            self.logger.info("创建callgraph...")
            graph = self.build_call_hierarchy()
            self.db.insert_json_object("call_graph", json.dumps(graph, ensure_ascii=False).encode('utf-8'))
        return graph

    def get_complete_funcname(self,father_funcname, child_funcname):
        if father_funcname in self.call_graph.keys():
            child_funcname_list = self.call_graph[father_funcname]
            for child_func in child_funcname_list:
                if child_func.find(child_funcname) != -1:
                    funcname, scope = get_funcname_and_scope(child_func)
                    if funcname == child_funcname:
                        return child_func
        return child_funcname

    def build_call_hierarchy(self):
        """
        生成调用关系JSON文件，格式 {"caller": ["callee1", "callee2"]}
        :param db_path: 输入数据库路径
        :param output_path: 输出JSON文件路径
        """
        # 1. 从数据库读取原始调用关系
        call_pairs = self.db.get_sqlite_call()

        # 2. 构建调用关系字典
        call_dict = defaultdict(list)
        for caller, callee in call_pairs:
            call_dict[caller].append(callee)

        # 3. 对调用列表去重并排序
        call_dict = {
            caller: sorted(list(set(callees)))  # 去重后排序
            for caller, callees in call_dict.items()
        }
        return call_dict

    def get_all_macro_def(self):
        if self.db.is_object_exits("macro_def"):
            self.logger.info("macro_def 已存在数据库，直接读取")
            macro_def_value = self.db.get_json_object("macro_def").decode('utf-8')
            macro_def_value_dict = json.loads(macro_def_value)
        else:
            self.logger.info("创建macro_def...")
            macro_def_value_dict = self.db.get_all_macro_def_core()
            self.db.insert_json_object("macro_def", json.dumps(macro_def_value_dict, ensure_ascii=False).encode('utf-8'))
        return macro_def_value_dict

    def get_all_function_dict(self):
        if self.db.is_object_exits("all_function_dict"):
            self.logger.info("all_function_dict 已存在数据库，直接读取")
            function_dict_str = self.db.get_json_object("all_function_dict").decode('utf-8')
            function_dict = json.loads(function_dict_str)
        else:
            self.logger.info("创建all_function_dict...")
            function_dict = self.db.get_all_function_dict_core()
            self.db.insert_json_object("all_function_dict", json.dumps(function_dict, ensure_ascii=False).encode('utf-8'))
        return function_dict

    def update_all_function_code_into_db(self):
        '''
        对doxygen的new_memberdef表里函数进行函数代码获得，并更新到code字段
        :param conn:数据库连接对象
        :return:None
        '''

        tmp_function_dict = self.get_all_function_dict()
        # self.logger.info(tmp_function_dict)
        for filepath in tmp_function_dict.keys():
            self.extract_and_save_function_code(filepath, tmp_function_dict[filepath], self.typedef_base_type_dict)

        self.db.insert_json_object('flag_update_all_function_code_into_db_done', 'done')

    def extract_and_save_function_code(self, file_path, function_list, typedef_base_type_dict):
        '''
        根据传入的函数所在文件路径，函数名称，函数起始行号来提取函数代码片段
        :param conn:数据库连接对象
        :param file_path: 函数所在文件路径
        :param function_list: [(函数名称，函数起始行号)]
        :return: True/Flase 提取函数是否成功
        '''
        self.logger.info(f"extract_and_save_function_code:{file_path}")
        filepath = os.path.normpath(file_path)

        if os.path.exists(filepath) == False:
            filepath = r"\\?\%s" % (filepath)
        encoding = get_encoding(filepath)
        if encoding == 'GB2312':
            encoding = 'GB18030'
        # self.logger.info(filepath,encoding)
        with open(filepath, 'r', encoding=encoding) as f:  # ,errors='ignore'
            # lines = f.readlines()
            # 给每一行代码添加行号
            lines = []
            line = f.readline()
            # self.logger.info(line)
            line = self.replace_typedef_base_type(line, typedef_base_type_dict)
            idx = 1
            while line:
                lines.append("l%d:" % (idx) + line)
                line = f.readline()
                line = self.replace_typedef_base_type(line, typedef_base_type_dict)
                idx = idx + 1

        for func in function_list:
            funcname = func[0]
            # self.logger.info(funcname)
            start_line = func[1]
            rowid = func[2]
            start_line -= 1  # 转换为 0-based 索引
            brace_count = 0
            end_line = start_line
            in_function = False

            for i in range(start_line, len(lines)):
                line = lines[i]
                stripped = line.strip()
                if '{' in stripped and not in_function:
                    in_function = True
                if in_function:
                    brace_count += stripped.count('{')
                    brace_count -= stripped.count('}')
                    if brace_count == 0:
                        end_line = i + 1  # 包含结束行
                        break
            if self.db.get_func_tuple(rowid) not in inserted_code_list:
                inserted_code_list.append(self.db.get_func_tuple(rowid))
                code = ''.join(lines[start_line:end_line])
                self.db.insert_function_code(funcname, code, rowid)

    def replace_typedef_base_type(self,content, macro_def_value_dict):
        for k in macro_def_value_dict.keys():
            if content.find(k + " ") != -1:
                content = content.replace(k + " ", macro_def_value_dict[k] + " ")
        return content

    def save_analyzed_dict(self, obj_name, analyzed_dict):
        '''
        analyzed_dict是已分析过的函数数据，将analyzed_dict落盘到文件中
        :return: None
        '''
        # self.logger.info(f"save_analyzed_dict:{obj_name}",analyzed_dict.keys())
        analyzed_dict_str = json.dumps(analyzed_dict, ensure_ascii=False).encode('utf-8')
        self.db.insert_json_object(obj_name, analyzed_dict_str)

    def read_analyzed_dict(self, obj_name):
        '''
        读取analyzed_dict.txt
        :return: analyzed_dict
        '''

        if self.db.is_object_exits(obj_name):
            try:
                analyzed_dict_str = self.db.get_json_object(obj_name).decode('utf-8')
            except:
                analyzed_dict_str = self.db.get_json_object(obj_name)
            analyzed_dict = json.loads(analyzed_dict_str)
        else:
            analyzed_dict = {}
        self.logger.info(f"read_analyzed_dict:{obj_name}:{analyzed_dict.keys()}")
        return analyzed_dict

    def save_analyzed_callpair_list(self, analyzed_callpair_list):
        # self.logger.info("start save_analyzed_callpair_list",analyzed_callpair_list)
        analyzed_callpair_list_str = json.dumps(analyzed_callpair_list, ensure_ascii=False).encode('utf-8')
        self.db.insert_json_object("analyzed_callpair_list", analyzed_callpair_list_str)

    def read_analyzed_callpair_list(self):
        if self.db.is_object_exits("analyzed_callpair_list"):
            analyzed_dict_str = self.db.get_json_object("analyzed_callpair_list").decode('utf-8')
            analyzed_dict = json.loads(analyzed_dict_str)
        else:
            analyzed_dict = []
        return analyzed_dict

    def get_macro_of_function(self,funcname, func_macro_list, macro_macro_list):
        '''
        获得函数相关的所有宏,返回集合,{‘macro1','macro2'..}
        '''
        found_values = set()
        initial_values = set()
        for func_macro in func_macro_list:
            if func_macro[0] == funcname:
                initial_values.add(func_macro[1])
                found_values.add(func_macro[1])

        def search_in(search_key):
            for item in macro_macro_list:
                if (item[0] == search_key or item[1] == search_key) and item[1] not in found_values:
                    found_values.add(item[1])
                    search_in(item[0])
                    search_in(item[1])

        for item in initial_values:
            search_in(item)
        return found_values

    def expand_function_code(self, func_name, code, call_macro_list, macro_macro_list, macro_func_list, call_pair_list):
        '''
        展开函数代码，包含短小的子函数调用
        '''
        expand_func_list = set()
        child_number_macros_list = set()
        try:
            # 获得函数的函数宏列表和整数宏列表
            func_macros, number_macros = self.get_int_macro_and_func_macro_of_function(func_name, call_macro_list,
                                                                                  macro_macro_list,
                                                                                  macro_func_list)
            # self.logger.info("func_macros:",func_name,func_macros)
            tmp_list = set()
            for func_macro in func_macros:
                for macro_func in macro_macro_list:
                    if func_macro[1] == macro_func[0]:
                        tmp_list.add(func_macro[1])
                        # self.logger.info(macro_func)
            # self.logger.info("tmp_list:",tmp_list)
            print("获得子函数代码中...")
            child_funcs = self.get_child_of_function(func_name, call_pair_list)
            for child_func in child_funcs:
                # 这里是宏展开，参数不知道数量，现在的逻辑是用一个magic_num，默认选择能匹配上函数名的第一个
                print("现在展开子函数{child_dunc}")
                magic_num = 99
                child_code_list, child_scope_list = self.db.get_function_code(child_func, "", magic_num)
                for child_code in child_code_list:
                    if child_code:
                        code_lines = len(child_code.split("\n"))
                        if code_lines < INLINE_FUNCTION_LINE_NUM:
                            grandson_funcs = self.get_child_of_function(child_func, call_pair_list)
                            if len(grandson_funcs) == 0:
                                print("获得子函数的函数宏列表和整数宏列表...")
                                # todo 2025.6.12需求2
                                child_func_macros, child_number_macros = self.get_int_macro_and_func_macro_of_function(
                                    child_func, call_macro_list, macro_macro_list, macro_func_list)
                                # self.logger.info("child_func_macros:",len(child_func_macros),child_number_macros,child_func_macros)
                                if len(child_func_macros) == 0:
                                    code += "\n" + child_code
                                    expand_func_list.add(child_func)
                                    child_number_macros_list.update(child_number_macros)
        except Exception as e:
            self.logger.error(f"展开函数代码错误:{e}")
            #self.logger.info(f"expand_function_code e: {func_name}", e)
            #traceback.self.logger.info_exc()
        return code, expand_func_list, child_number_macros_list

    def get_int_macro_and_func_macro_of_function(self,funcname, func_macro_list, macro_macro_list, macro_func_list):
        '''
        返回函数相关的函数宏func_result集合, {(func,macro1},{func,macro2},{func,macro3},{macro3,macro4}..}
        整数宏number_result集合 {(macro1,macro2},{macro2,macro3}..}
        '''
        func_related = set()
        number_related = set()
        visited = set()

        func_result = set()
        number_result = set()

        # 第一步，在func_macro_list中找到funcname相关的macro
        initial_elements = []
        for item in func_macro_list:
            if item[0] == funcname:
                initial_elements.append(item)

        def can_reach_macro_func_list(element, path=None):
            if path is None:
                path = set()

            element = tuple(element) if isinstance(element, list) else element

            # 如果当前元素已经在路径中，说明成环，停止搜索
            if element in path:
                return False

            # 将当前元素添加到路径中
            path.add(element)
            current_value = element[1]

            # 检查是否连接到macro_func_list中的任何元素
            if any(current_value == item[0] for item in macro_func_list):
                return True

            # 检查当前元素是否在c列表中
            if element in macro_func_list:
                return True

            # 在macro_macro_list中搜索下一个可能的元素
            for next_item in macro_macro_list:
                if next_item[0] == current_value:
                    next_item = tuple(next_item) if isinstance(next_item, list) else next_item
                    if next_item not in path and can_reach_macro_func_list(next_item, path):
                        return True
            return False

        # 对每个元素进行分类
        def classify_elements(element):
            element = tuple(element) if isinstance(element, list) else element

            if element in visited:
                return
            visited.add(element)

            # 检查元素是否能到达macro_func_list列表中的任何元素
            if can_reach_macro_func_list(element):
                func_related.add(element)
                # 将路径上所有元素都添加到func_related
                current_value = element[1]
                for next_item in macro_macro_list:
                    next_item = tuple(next_item) if isinstance(next_item, list) else next_item
                    if next_item[0] == current_value and next_item not in visited:
                        classify_elements(next_item)
            else:
                number_related.add(element)
                # 继续搜索相关元素
                current_value = element[1]
                for next_item in macro_macro_list:
                    next_item = tuple(next_item) if isinstance(next_item, list) else next_item
                    if next_item[0] == current_value and next_item not in visited:
                        classify_elements(next_item)

        # 从初始元素开始分类
        for initial_item in initial_elements:
            classify_elements(initial_item)

        for f in func_related:
            func_result.add(f)
        for n in number_related:
            number_result.add(n)
        return func_result, number_result

    def get_child_of_function(self,funcname, call_pair_list):
        '''
        获得函数的子函数集合
        '''
        child_func = set()
        for call_pair in call_pair_list:
            if call_pair[0] == funcname:
                child_func.add(call_pair[1])

        return child_func

    def get_macro_code(self, macro_list):
        '''
        将macro_list中的macro转化为字符串
        '''
        macro_code = ""
        for macro in macro_list:
            value = self.db.get_initializer_of_variable(macro)
            macro_code += f"#define {macro} {value}\n"

        return macro_code
    def get_datastruct_of_function(self, funcname, arg_list, reference_variable_list):
        '''
        reference_variable_list:函数涉及的变量列表
        返回datastruct_list :相关数据结构列表
        function_var_list：函数相关变量描述列表
        '''
        function_var_list = []
        datastruct_list = []
        handled_structs = set()
        # self.logger.info("get_datastruct_of_function: "+funcname + " " + str(arg_list) + " " + str(reference_variable_list))
        for arg in arg_list:
            arg_type = (arg.get("类型", "")
               .replace("*", "")
               .replace("const", "")
               .replace("struct", "")
               .replace("enum", "")
               .replace("union", "")
               .replace(" ", ""))

            
            datastruct_list = self.db.get_datastruct_core(datastruct_list, arg_type, handled_structs)

        for item in reference_variable_list:
            if item[0] == funcname:
                if item[1] not in function_var_list:
                    var_dict = self.db.get_function_var(item[1])
                    # self.logger.info("get_datastruct_of_function var_dict:"+funcname+item[1]+str(var_dict))
                    if var_dict not in function_var_list:
                        function_var_list.append(var_dict)
                        datastruct_list = self.db.get_datastruct_core(datastruct_list, var_dict.get("类型",""),
                                                              handled_structs)
                        # self.logger.info("get_datastruct_of_function datastruct_list:",funcname,item[1],datastruct_list)

        # self.logger.info("get_datastruct_of_function last:",funcname,datastruct_list,function_var_list)
        return datastruct_list, function_var_list

    def update_llm_result(self, datastruct, duplicate_code_flag=False, func_name = "", func_var_list=[]):
        self.logger.info(f"update_llm_result:{datastruct}")
        for d in datastruct:
            self.db.update_variable_desc(d.get("名称", ""), d.get("字段", []))
            
        
        # "函数局部变量": [   
        #     {      "名称": "info",      "类型": "PlatformInfo",      
        #      "说明": "PlatformInfo结构体实例，包含ID、名称和描述字段",      
        #      "值": [        "id = 1001",       
        #            "name = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",      
        #            "description = sasa"      ],      
        #      "入参": false,      "入参索引": null    }  ], 
        if not duplicate_code_flag:
            return func_var_list
        
        try:
            for struct_tmp in datastruct:
                for attr_ in struct_tmp.get("字段", []):
                    struct_attr_name_ss = attr_.get("名称", [])
                    if "::" in struct_attr_name_ss:
                        struct_attr_name = struct_attr_name_ss.split("::")
                        struct_name_tmp, attr_name_tmp = struct_attr_name[0], struct_attr_name[1]
                        if struct_name_tmp == struct_tmp.get("名称", "") and struct_name_tmp:
                            func_var_list.append([func_name, struct_attr_name_ss])
                    else:
                        func_var_list.append([func_name, struct_tmp.get("名称") + "::" + struct_attr_name_ss])
        except:
            pass
        return func_var_list
            

    def getPointerRefFuncName(self, ptr_func):
        self.logger.debug("获得函数指针代码: " + str(ptr_func))
        
        calls = self.db.get_func_reference(ptr_func)
        # self.logger.info("ptr_func", ptr_func)
        result_dict = {ptr_func: []}
        visited_vars = set()
        for caller in calls:
            func_name, scope = get_funcname_and_scope(caller[0])
            '''
            这里是要遍历调用的父函数code，是不知道参数个数的，所以直接默认99， 选择函数名相同的第一个
            '''
            code_list, scope_list = self.db.get_function_code(func_name, scope, 99)
            for code in code_list:
                if not code:
                    continue
                    # 提取赋值语句
                assignments = self.extract_assignments_from_code(code, ptr_func)
                for assignment in assignments:
                    # 解析赋值链
                    func_list, code_fragments = self.resolve_assignment(assignment, visited_vars)

                    # 添加找到的函数
                    result_dict[ptr_func].extend(func_list)

        self.logger.info("getPointerFunc_result_dict" + str(result_dict))

        return result_dict[ptr_func]

    def getFuncRefFuncName(self, func_name):
        
        
        return 
        
        
        
    
    
    def extract_assignments_from_code(self,code, ptr_func):
        """
        提取所有对ptr_func的赋值语句
        支持格式:
            ptr = ...
            ptr[i] = ...
            obj->ptr = ...
            obj->ptr[i] = ...
            ptr = setfunc()
        """
        patterns = [
            # 简单赋值
            re.compile(rf'\b{ptr_func}\s*=\s*[^;]+;'),
            # 数组元素赋值
            re.compile(rf'\b{ptr_func}\s*\[[^\]]*\]\s*=\s*[^;]+;'),
            # 结构体指针赋值
            re.compile(rf'\b\w+\s*->\s*{ptr_func}\s*=\s*[^;]+;'),
            # 结构体指针数组赋值
            re.compile(rf'\b\w+\s*->\s*{ptr_func}\s*\[[^\]]*\]\s*=\s*[^;]+;')
        ]

        assignments = []
        for pattern in patterns:
            matches = pattern.findall(code)
            assignments.extend(matches)

        return assignments

    def resolve_assignment(self, assignment, visited_vars):
        """
        递归解析赋值语句，返回函数列表和相关的代码片段
        """
        func_list = []
        code_fragments = []

        # 解析右侧表达式
        f = re.search(r'=\s*(.*?)\s*;', assignment)
        if not f:
            return func_list, code_fragments
        rhs = f.group(1).split('[')[0].split('->')[-1]

        # 情况1: 直接函数赋值
        if self.db.is_function(rhs):
            func_list.append(rhs)
            code_fragments.append(assignment)
            return func_list, code_fragments

        # 情况2: 数组初始化
        if rhs.startswith('{') and rhs.endswith('}'):
            funcs = rhs[1:-1].split(',')
            for f in funcs:
                f = f.strip()
                if self.db.is_function(f):
                    func_list.append(f)
            code_fragments.append(assignment)
            return func_list, code_fragments

        # 情况3: 变量引用 (需要递归查找)
        if rhs not in visited_vars:
            visited_vars.add(rhs)
            var_def = self.db.get_variable_definition(rhs)
            if var_def:
                # 添加变量定义代码
                var_code = f"{var_def['definition']} = {var_def['initializer']}"
                code_fragments.append(var_code)

                # 递归解析初始值
                if var_def['initializer']:
                    new_funcs, new_code = self.resolve_assignment(
                        f"{rhs} = {var_def['initializer']}",
                        visited_vars
                    )
                    func_list.extend(new_funcs)
                    code_fragments.extend(new_code)

        return func_list, code_fragments