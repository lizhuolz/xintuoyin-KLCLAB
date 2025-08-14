
# client.py
import requests
import json

def stream_query(query):
    # 设置请求URL和头部
    url = 'http://0.0.0.0:6000/chat'
    headers = {'Content-Type': 'application/json'}
    
    # 发送POST请求，开启流式接收
    response = requests.post(
        url,
        headers=headers,
        json={"user_id": "0", "conver_id": "0", "message": query},
        stream=True
    )
    
    # 处理流式响应
    for line in response.iter_lines():
        if line:
            # 解码SSE事件
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data:'):
                # 提取JSON数据
                data = decoded_line[5:].strip()
                try:
                    json_data = json.loads(data)
                    print(json_data['text'], end=' ', flush=True)
                except json.JSONDecodeError:
                    pass

if __name__ == '__main__':
    user_query = "2025年二月总工时最长的人员id是？"
    print("服务器回复: ", end='')
    stream_query(user_query)
    print()  # 最后换行