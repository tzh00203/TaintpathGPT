# llm_client.py
import os
import time
import json
import requests
from llm_prompt import *


PROMPT_ENDING = "返回的结果应当是直接可以json.loads的格式，不要带其它任何多余内容"
class LLMClient:
    def __init__(self, ai_url, api_key, database_path):
        self.ai_url = ai_url
        self.api_key = api_key
        self.database_path = database_path
        self.last_log_name = ""

        # 确保日志目录存在
        log_dir = os.path.join(database_path, "llm_log")
        if not os.path.exists(log_dir):
            os.mkdir(log_dir)

    def save_llm_log(self,type,father_funcname,funcname, user_input, content, reason):
        file_time = time.strftime("%Y%m%d%H%M_%S", time.localtime())
        funcname = funcname.replace(" ", "_").replace("/", "_").replace(":", "_").replace("<", "_").replace(">", "_").replace("=", "_").replace("*", "_").replace("?", "_").replace("|", "_")
        father_funcname = father_funcname.replace(" ", "_").replace("/", "_").replace(":", "_").replace("<", "_").replace(">", "_").replace("=", "_").replace("*", "_").replace("?", "_").replace("|", "_")
        log_name = os.path.join(self.database_path, "llm_log", f"llm_rsp_{file_time}_{father_funcname}_{funcname}_{type}.txt")
        #print("save_llm_log file_time", log_name)
        with open(log_name, 'wb+') as f:
            f.write(("prompt:\n%s" % (user_input)).encode('utf-8'))
            f.write(("content:\n%s" % (content)).encode('utf-8'))
            f.write(("reasoning_content:\n%s" % (reason)).encode('utf-8'))

        return log_name

    def llm_request(self, user_input, type,father_funcname,funcname, model="qwen", func_tools=None, stream=False):
        """
        发送 LLM 请求，返回 (content, reasoning_content)，
        并记录日志。如果发生错误（例如返回结果截断或 JSON 格式错误），
        则根据错误类型添加提示后重试请求。
        """
        HEADERS = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        # user_input = request.json.get("content", "")
        # if not user_input:
        #     return jsonify({"error": "Content is required"}), 400

        # 记录当前用户输入
        message = [{"role": "user", "content": user_input[:100000] + PROMPT_ENDING}]
        # print(chat_history)
        data_llm = {
            # "model": "gpt-5-mini" if model == "gpt" else "qwen",
            "messages": message,  # 发送带有历史信息的对话
            #"max_tokens": 90000,
            "top_p": 0.95,
            "temperature": 0.6,
            "ignore_eos": False,
            "stream": False
        }
        # print(data_llm)
        print("user_input:",user_input)
        print("--------------------------------------{}-------------------------------------".format(type))
        response = requests.post(self.ai_url, headers=HEADERS, json=data_llm, stream=False)
      
        result = ""
        if stream:
            for line in response.iter_lines():
                if not line or not line.startswith(b"data:"):
                    continue
                data = line[len(b"data: "):]
                print("[*] " + line.decode("utf-8"))
                if data == b"[DONE]":
                    break
                try:
                    line_json = json.loads(data)
                    delta = line_json["choices"][0]["delta"].get("content")
                    if delta:
                        result += delta
                except json.JSONDecodeError:
                    self.log("[WARN] Failed to decode streaming JSON chunk")
                    continue
        else:
            print(response.text)
            data = response.json()
            result = data["choices"][0]["message"]["content"]
        print(result)

        try:
            if result.find("</think>") != -1:
                reason, content = result.split("</think>")
                content = self.get_json_from_llm_rsp(content)

                print("content:", content)
                print("reason:", reason)
                logname = self.save_llm_log(type,father_funcname,funcname, user_input, content, reason)

                # reason,content = evaluate_process(user_input, content, reason)
                return (content, reason,logname)
            elif result.find("</think>") == -1 and "gpt" in model:
                result_part1_str = result.split("data:")[1]
                result_json = json.loads(result_part1_str)
                # print(result_json)
                content = result_json["choices"][0]["delta"]["content"]
                logname = self.save_llm_log(type,father_funcname,funcname, user_input, result, "")

                return (content, "", logname)
            elif result.find("</think>") == -1 and "qwen" in model:
                # print(result)
                # exit(1)
                result_part1_str = result.split("data:")[1]
                result_json = json.loads(result_part1_str)
                print(result_json)
                content = result_json["choices"][0]["delta"]["content"]
                logname = self.save_llm_log(type,father_funcname,funcname, user_input, result, "")

                return (content, "", logname)
            else:
                exit(1)
                return self.llm_request(user_input,type,father_funcname,funcname)
        except Exception as e:
            print("llm request error:", e, e.__traceback__.tb_lineno)
            exit(1)
            return self.llm_request(user_input,type,father_funcname,funcname)


    def get_json_from_llm_rsp(self, content):
        """
        尝试从 LLM 返回内容中提取 JSON 数据
        """
        if len(content) < 6:
            return ""
        start_flag = content.find("```json")
        if start_flag == -1:
            return content
        end_flag = content.find("```", start_flag + 7)
        if start_flag != -1 and end_flag != -1:
            json_str = content[start_flag + 7:end_flag].strip("\n")
            json_str = json_str.replace("\\\"", "")
            json_str = json_str.replace("\"offset\":", "\"偏移\":")
            json_str = json_str.replace("\"смещение\":", "\"偏移\":")
            json_str = json_str.replace("\"сообщение\":", "\"说明\":")
            return json_str
        return ""

    def evaluate_process(self,last_question, last_content, last_reasoning_content,father_funcname,func_name):
        org_last_question = last_question
        while 1:  # 确保这次请求大模型按任务要求输出正确的结果才退出该函数
            prompt = evaluate_prompt(org_last_question, last_content, last_reasoning_content)

            if prompt == -1: #因长度限制无法评估， 返回评估结果为正确
                rsp_json = {}
                rsp_json["结果"] = "success"
                rsp_json["原因说明"] = ""
                return rsp_json

            # print("evaluate_prompt:",prompt)
            while 1:  # 确保这次请求返回正确格式的结果才退出循环
                rsp = self.llm_request(prompt, "evaluate req",father_funcname,func_name)
                if rsp[0] != "":
                    try:
                        rsp_json = json.loads(rsp[0])
                        if "结果" not in rsp_json.keys() or "原因说明" not in rsp_json.keys():
                            print("evaluate_process:mistaking tasks")
                        else:
                            break
                    except json.decoder.JSONDecodeError as e:
                        print("evaluate_process:rsp_json = json.loads(rsp[0]) error:", e)
                else:
                    print("evaluate_process json_str is null")

            # 大模型2评估大模型1执行任务的结果是对的，返回原来正确的结果，并退出该函数
            if rsp_json.get("结果", "").lower() == "success":
                return rsp_json
            else:
                # 大模型2评估大模型1执行任务的结果是错误的情况，需要让大模型1按大模型2推理的错误原因，重新执行原任务
                prompt = re_request_prompt(org_last_question, last_content, last_reasoning_content,
                                           rsp_json.get("原因说明", ""))
                print("re_request_prompt:", prompt)
                while 1:
                    rsp = self.llm_request(prompt, "re findbug request",father_funcname,func_name)
                    json_str = self.get_json_from_llm_rsp(rsp[0])

                    if json_str != "":
                        try:
                            tmp_json = json.loads(json_str)
                            last_content = json_str
                            last_reasoning_content = rsp[1]
                            break
                        except json.decoder.JSONDecodeError as e:
                            print("evaluate_process:tmp_json = json.loads(rsp[0]) error:", e)

