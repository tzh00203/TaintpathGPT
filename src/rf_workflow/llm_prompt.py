##coding=utf-8

TOKEN_MAX=90000

def evaluate_prompt(original_question,original_rsp,original_reasoning):
    '''
    评估上一个任务请求的结果是否返回正确
    :param original_question: 上一个任务请求提示词
    :param original_rsp: 上一个任务的返回
    :param original_reasoning: 上一个任务的推理过程
    :return:
    '''
    if len(original_question)+len(original_rsp) + len(original_reasoning) < TOKEN_MAX+1000:
        pass
    elif len(original_question)+len(original_rsp)  < TOKEN_MAX+1000:
        original_reasoning = original_reasoning[:TOKEN_MAX+1000 - len(original_question) - len(original_rsp)]
    elif len(original_question)  < TOKEN_MAX+1000:  # 此时无法评估结果，返回错误
        return -1


    prompt = '''你是一个评估程序，评估某一个任务的推理分析的结果是否正确：
    【任务要求】
        请评估以下任务分析是否正确和返回的最终结果是否正确，如果先前分析结果是错误的，请给出错误原因的详细总结。以下是原任务：
            "prompt:"后边是原任务输入，"content:"后是原任务输出，”reasoning_content:“后是原任务推理过程，
            prompt:\'\'\'%s\'\'\',content:\'\'\'%s\'\'\',reasoning_content:\'\'\'%s\'\'\'。
    【输出要求】
        标准化JSON格式,按以下json 格式进行输出：
        {"结果":"success"/"fail","原因说明":...}
    ''' % (original_question,original_rsp,original_reasoning)
    return prompt

def re_request_prompt(original_question,original_rsp,original_reasoning,fail_reason):
    '''
    根据上一个任务错误原因来重新发起请求
    :param original_question: 上一个任务请求提示词
    :param original_rsp: 上一个任务的返回
    :param original_reasoning: 上一个任务的推理过程
    :param fail_reason: 上一个任务的错误原因
    :return:
    '''
    if len(original_question)+len(fail_reason)+len(original_rsp) + len(original_reasoning) < TOKEN_MAX+1000:
        pass
    elif len(original_question)+len(fail_reason)+len(original_rsp)  < TOKEN_MAX+1000:
        original_reasoning = original_reasoning[:TOKEN_MAX+1000 - len(original_question) - len(original_rsp)]
    elif len(original_question)+len(fail_reason)  < TOKEN_MAX+1000:
        original_reasoning = ""
        original_rsp = ""
    elif len(original_question)  < TOKEN_MAX+1000:  # 此时无法评估结果，返回当前结果
        original_reasoning = ""
        original_rsp = ""
        fail_reason = ""

    prompt = '''以下任务存在结果错误，错误原因是\'\'\'%s\'\'\',请重新分析这个任务，并按原任务要求输出结果。以下是原任务：
    "prompt:"后边是原任务输入，"content:"后是原任务输出，”reasoning_content:“后是原任务推理过程，
    prompt:\'\'\'%s\'\'\',content:\'\'\'%s\'\'\',reasoning_content:\'\'\'%s\'\'\'。
    ''' % (fail_reason,original_question,original_rsp,original_reasoning)
    return prompt


def check_dict_strlen(mydict):
    #print("in check_dict_strlen")
    strlen=0
    for i in mydict:
        strlen+=len(mydict[i])
    #print(strlen)
    return strlen

def network_recvfunc_code_s(code, arg_list, datastruct_list, global_var_list,ext_info):
    #print("in network_recvfunc_code_s")
    # 如果超过token大小
    build_arg_dict = {"code": code, "arg_list": arg_list, "datastruct_list": datastruct_list,
                      "global_var_list": global_var_list,"ext_info": ext_info}
    arg_priority = ["datastruct_list", "global_var_list", "arg_list"]
    build_str_dict = {
        "code": ",这是一个处理函数，\n",
        "arg_list": ",是这个函数的参数说明,\n",
        "datastruct_list": ",是函数涉及的数据结构,\n",
        "global_var_list": ",是函数涉及的变量,\n",
        "ext_info":",是额外信息,\n"
    }

    for i in range(0, len(arg_priority)):
        if (check_dict_strlen(build_arg_dict) > TOKEN_MAX):
            build_arg_dict.pop(arg_priority[i])
            #print("pop " + arg_priority[i])
        else:
            break
    prompt_pre = ""
    #print(build_arg_dict)
    for i in build_arg_dict:
        if (len(build_arg_dict[i]) > 4):  # 针对[] ,{}
            prompt_pre += build_arg_dict[i] + build_str_dict[i]

    prompt_pre += "请分析并完成以下任务："

    # TODO: agent输出函数指针变量/值得传递需要考虑更多场景
    prompt = prompt_pre + '''
    【任务分解】
    1. 函数分析
       a.关注参数说明中攻击者可控的字段如何传递，如果攻击者可控字段直接复制到新变量，在新变量的说明中添加"受攻击者控制",禁止将其它字段随便添加“受攻击者控制”的标签，长度字段只有来着攻击者可控的缓冲区中取值的才认为是“受攻击者控制”
       b.详细分析函数中的检查条件，将检查条件和变量说明关联，在对应的数据结构字段说明中添加检查条件，变量之间传递值的情况下，检查条件也要传递给新的变量
       c.检查条件只能来自代码中的判断条件，数组元素个数不能作为变量的检查条件，禁止添加到说明中
       d.在输出结果中，列出所有受攻击者可控影响的数据结构字段和受函数中对变量大小的检查条件影响的数据结构字段，在字段说明中添加是否攻击者可控和详细的检查条件
       e.输出的数据结构名称和字段名称都要和输入保持一致，不用忽略特殊字符，例如'_'
       f.分析函数的局部变量，在输出结果中添加全部的局部变量，并在说明中添加可能的取值范围，推理过程中给出取值范围的原因
         *需要注意，局部变量对应值只记录被后续调用的，被覆盖的值不做记录，输出到一个列表中，值必须来源于代码，即使是其他变量，其他解释性放到说明中, 没有的话设为空list
       g.对分析的*函数局部变量*判断是否为传入的参数，若初始值来源于入参，是的话要标记出入参True和入参索引，函数代码中的输入参数也算是局部变量
       h.对分析的*函数局部变量*判断是否为结构体，若为结构体，则在输出的列表中加上使用的属性，*名称*为变量在结构体中的局部属性名，*类型*为该结构体的定义名称，*结构体*设置为True
       i.赋值语句右侧如果是内存分配函数，需要对左侧变量的增加分配内存大小的说明
       j.如果子函数的返回值导致函数退出，则子函数的内容也是检查条件，要将相关变量说明关联起来
       k.如果有内存分配操作，在变量说明中添加对应的分配内存大小
       l.输出的json请不要加入注释等其他非结构体数据，需要输出的内容能够直接被json.loads解析； 其他结构体字段未受攻击者控制或未被检查条件影响，不需要输出在json中

    2.提取子函数调用操作。详细分析给出的函数代码和目标数据结构，在提供的调用函数列表中找到函数中所有和目标数据结构有关的函数调用，以下是详细要求：
       a.不要忽略每一行的注释信息，如果这一行存在间接调用函数，那么注释中的信息就是该间接调用的函数
       b.若输入的*函数涉及的变量*的字段是包含真实函数指针的结构体，该真实函数也需要输出到*函数调用*,不用考虑其是否为间接调用
       c.分析代码中所有的子函数调用，在推理过程中列出，包括相同名称的子函数调用，所有情况下的子函数都要给出，不要有遗漏
       d.分析函数调用的参数、输出，在输出中添加进函数调用列表里，包括函数名称、函数调用代码行、代码行序号、参数信息,和调试、日志打印、锁、内存分配释放有关的函数禁止添加
       e.输出结果中将子函数参数和父函数参数或者其它数据结构的关系、子函数参数的值、检查条件都在参数说明中列出，
         *需要明确指出子函数调用时候的参数具体值，输出到参数列表字段`名称`中，代表传入的具体值；同时记录参数索引
       f.输出结果中函数调用代码行要完整输出，如果函数调用代码包含多行，将多行代码转化为一行，内容不做改变
       g.受检查条件影响的参数都要在参数说明中添加检查条件
       h.对于包含dlsym的函数，dlsym的第二个参数为实际的子函数，包含到子函数输出中
       i.函数名称去除'<'、'>'、 '('、 ')'部分字符串,保留基本函数名称
       k.关注赋值的变量是否值为函数变量指针


    【输出要求】
    • 标准化JSON格式：
    {
      "数据结构": [{
        "名称": ...,
        "字段": [
          {"名称": ..., "类型": ..., "说明": ...},
          ...
        ]
      }...],
      “函数局部变量”:[{"名称": ..., "类型": ..., "说明": ..., "值": [], "入参":True/False, "入参索引":int类型, "结构体":True/False}...],
      "函数调用": [
        {
          "函数名称": ...,
          "函数调用代码行":...,
          "代码行序号":...,
          "参数列表":[{"名称":...,"类型":...,"说明":"1st arg", "索引": ....}...]
        }
      ]
    }'''
    return prompt


def eliminate_false_positives(code,father_code,arg_list,datastruct_list,global_var_list,result,result_reason):
    '''
    消除误报
    '''
    print("eliminate_false_positives")
    # 如果超过token大小
    build_arg_dict = {"code": code, "arg_list": arg_list, "datastruct_list": datastruct_list,
                      "var_list": global_var_list,
                      "father_code": father_code, "vul_descibe": result, "reason": result_reason}
    arg_priority = ["reason","datastruct_list", "var_list", "arg_list", "father_code", "arg_list"]
    build_str_dict = {
        "code": ",这是一个处理函数，\n",
        "arg_list": ",是这个函数的参数说明,\n",
        "var_list": ",是函数涉及的变量,\n",
        "datastruct_list": ",是函数涉及的数据结构,\n",
        "father_code": ",是处理函数的父函数,\n",
        "vul_descibe": ",这是漏洞描述,\n",
        "reason": ",这是推理过程,\n"
    }

    for i in range(0, len(arg_priority)):
        if (check_dict_strlen(build_arg_dict) > TOKEN_MAX):
            build_arg_dict.pop(arg_priority[i])
        else:
            break
    prompt_pre = ""
    for i in build_arg_dict:
        if (len(build_arg_dict[i]) > 4):
            prompt_pre += build_arg_dict[i] + build_str_dict[i]

    prompt = prompt_pre + '''
    请按以下要求评估这个漏洞是否存在误报:
    【评估要求】
        a.默认认为缓冲区长度字段和缓冲区实际长度一致
        b.默认认为数组元素个数字段和数组实际元素个数一致
        c.攻击者无法控制指针
        d.如果漏洞是在用户未提供的代码里，认为是误报
        如果漏洞描述和以上要求不一致，认为存在误报
    【输出要求】
    • 标准化JSON格式：{"是否误报":True/False}
    '''
    return prompt

def find_bug(code, arg_list,datastruct_list,global_var_list,father_code,father_arg_list,father_datastruct_list,father_global_var_list,bug_model,ext_info):
    '''
    根据给出的函数代码和全量数据结构，按照给出的内存漏洞模式来找漏洞
    :param code: 函数代码
    :param datastruct_json: 需要生成的数据结构列表，json字符串形式
    :return:
    '''
     #如果超过token大小
    build_arg_dict={"code":code,"arg_list":arg_list,"datastruct_list":datastruct_list,"global_var_list":global_var_list,
                    "father_code":father_code,"father_arg_list":father_arg_list,"father_datastruct_list":father_datastruct_list,
                    "father_global_var_list":father_global_var_list,"bug_model":bug_model,"ext_info":ext_info}
    arg_priority=["father_datastruct_list","father_global_var_list","father_arg_list","father_code","datastruct_list","global_var_list","arg_list"]
    build_str_dict={
                   "code":",这是一个处理函数，\n",
                   "arg_list":",是这个函数的参数说明,\n",
                   "datastruct_list":",是函数涉及的数据结构,\n",
                   "global_var_list":",是函数涉及的变量,\n",
                   "father_code":",是处理函数的父函数,\n",
                   "father_arg_list":",是父函数的参数说明,\n",
                   "father_datastruct_list":",是父函数涉及的数据结构,\n",
                   "father_global_var_list":",是父函数涉及的全局变量,\n",
                   "bug_model":",这是漏洞模型,\n",
                   "ext_info":",这是额外信息,\n"
                   }

    for i in range(0,len(arg_priority)):
        if(check_dict_strlen(build_arg_dict)>TOKEN_MAX):
            build_arg_dict.pop(arg_priority[i])
        else:
            break
    prompt_pre=""
    for i in build_arg_dict:
        if(len(build_arg_dict[i])>4):
            prompt_pre+=build_arg_dict[i]+build_str_dict[i]
    prompt_pre+="请分析并完成以下任务："

    prompt = prompt_pre+'''
    【内存漏洞前置知识】
       - 内存破坏漏洞包括内存越界读、越界写，如下漏洞模式:
        %s
    【任务分解】
       内存破坏漏洞分析。详细分析给出的处理函数代码和数据结构，判断处理函数中是否存在内存破坏漏洞以及具体漏洞类型，以下是详细要求：
        - 首先确定处理函数参数、函数内全局变量的数据结构，来辅助函数代码分析，将父函数代码和处理函数代码一同分析，主要看处理函数中是否存在漏洞。
        - 然后根据内存漏洞前置知识，按照给出的漏洞模式进行分析，判断是否存在已知的漏洞模式，详细说明漏洞原理和漏洞成因，并给出得出结论的置信度。
        - 如果存在不同的代码分支，每一个分支都要单独分析是否存在已知漏洞模式
        - 推理过程要非常详细，每一步说明推理原因，对于不确定的字段范围，不能假设，尤其是长度字段。
        - size\len\length字段默认认为攻击者不可控
        - 缓冲区指针排除是无效指针或者攻击者可控的情况
        - 默认假设缓冲区长度字段和缓冲区实际size是一致的，数组元素长度字段和数组实际数量一致
        - THE DEFAULT ASSUMPTION IS THAT THE MEMORY SIZE PASSED INTO THE FUNCTION MATCHES THE ACTUAL MEMORY SIZE, AND THE NUMBER OF ARRAY ELEMENTS MATCHES THE ACTUAL NUMBER OF ARRAYS


    【输出要求】
    • 标准化JSON格式,按以下json 格式进行输出，要求是能够直接进行加载的，不能加注释等一类解释性非结构化数据：
    {
      "漏洞描述":...
      "是否确定漏洞": true,
      "置信度":"x%%",
    }（保证返回的json格式正确）
    
    • 只有确定为漏洞情况下，"是否确定漏洞"设置为true，其他情况下均为false。例如，如果无法完全确定是否是漏洞，"是否确定漏洞"设置为false。
    ''' %(bug_model)

    return prompt

bug_models = {
"p1":'''• 漏洞模式:memcpy(dst,src,length)，如果length大于src buffer的长度，则是内存越界读取;如果length大于dst buffer的长度，则是内存越界写。
            需要知道src buffer的长度小于length，才能确定是内存越界读，需要知道dst buffer的长度小于length，才能确定是内存越界写
''',
"p2":'''• 漏洞模式:for(int v1=0;v1<MAX_LENGTH;v1++){ buf_a[v1] = xxx; bbb = buf_b[v1]},如果v1大于等于buf_a的数组元素个数，则是内存越界写,
        如果v1大于等于buf_b数组的元素个数，则是内存越界读。需要知道buf_a数组元素个数小于等于v1,才能确定内存越界写，知道buf_b数组元素个数小于等于v1,才能确定内存越界读。
        重点关注存在数组的代码，检查数组下标是否超过数组范围
'''
}