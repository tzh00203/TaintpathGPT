import requests
import json
from utils.mylogger import MyLogger
from models.llm import LLM
from models.remote_config import API_URL, API_KEY
from pprint import pprint

api_url = API_URL
api_key = API_KEY

class QwenAPIRemote:
    def __init__(self, model_name, logger: MyLogger, **kwargs):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        if logger:
            self.log = lambda msg: logger.log(msg)
        else:
            self.log = lambda msg: print(msg)

    def predict(self, prompts, batch_size=0, no_progress_bar=True, **kwargs):
        """
        prompts: str or List[str]
        batch_size: ignored here, kept for interface compatibility
        Returns a string (single prompt) or list of strings (batch)
        """
        # 如果是单条 prompt，转成列表
        is_single = False
        if isinstance(prompts, str):
            prompts = [prompts]
            is_single = True

        results = []
        for prompt in prompts:
            try:
                answer = self._call_api(prompt, stream=False, **kwargs)
                results.append(answer)
            except Exception as e:
                self.log(f"[ERROR] Failed to get response for prompt: {e}")
                results.append("")

        if is_single:
            return results[0]
        return results

    def _call_api(self, prompt, stream=False, temperature=0.7, top_p=0.9):
        """use Qwen API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": "gpt-5",
            "messages":prompt,
            "temperature": temperature,
            "top_p": top_p,
            "stream": stream
        }

        self.log(f"   ==> Sending request to remote Qwen API: {self.api_url}")
        answer = ""
        with requests.post(self.api_url, headers=headers, json=payload, stream=stream, timeout=300) as resp:
            if resp.status_code != 200:
                self.log(f"   ==> Qwen API request failed ({resp.status_code}): {resp.text}")
                raise RuntimeError(f"Qwen API request failed ({resp.status_code})")

            self.log(f"   ==> Qwen API request succeeded ({resp.status_code})")

            if stream:
                for line in resp.iter_lines():
                    if not line or not line.startswith(b"data:"):
                        continue
                    data = line[len(b"data: "):]
                    if data == b"[DONE]":
                        break
                    try:
                        line_json = json.loads(data)
                        delta = line_json["choices"][0]["delta"].get("content")
                        if delta:
                            answer += delta
                    except json.JSONDecodeError:
                        self.log("[WARN] Failed to decode streaming JSON chunk")
                        continue
            else:
                data = resp.json()
                answer = data["choices"][0]["message"]["content"]
        return answer