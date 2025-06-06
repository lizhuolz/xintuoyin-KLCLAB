    
import requests
import json

def curl_backend(query: str, mode: str = "hybrid") -> str:
    url = "http://localhost:9621/query"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "query": query,
        "mode": mode,
        "only_need_context": "true"
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status() # 抛出请求异常（如状态码不是200）
        return response.text
    except requests.RequestException as e:
        return f"请求出错: {e}"

import json
import re
from jinja2 import Template
def extract_json_from_string(text):
    result = {}
    
    # 使用正则表达式找出所有以 -----...----- 开头的字段
    field_pattern = r"-----(.*?)-----\s*```json\n(.*?)```"
    matches = re.findall(field_pattern, text, re.DOTALL)
    
    for field, json_str in matches:
        field = field.strip()  # 移除可能的空白字符
        try:
            json_data = json.loads(json_str)
            result[field] = json_data
        except json.JSONDecodeError as e:
            result[field] = f"Error decoding JSON for {field}: {str(e)}"
    
    return result


def RAG_backend(query: str):
    result = curl_backend(query)
    prompt = """
【用户提问】  
> {{query}}

【RAG召回结果】
{{RAG}}  
"""
    Template(prompt).render(query=query, RAG=extract_json_from_string(eval(result)['response'])['Sources'])
    return 
