from agent import Agent, User, Conversation
user0 = User(0)
conv0 = user0.start_conversation(0)
UserList = {0:user0}
ConversationList = {0:conv0}

from fastapi import FastAPI, Request
from pydantic import BaseModel
import asyncio

app = FastAPI()

# 请求格式
class Query(BaseModel):
    user_id: str
    conver_id: str
    message: str

# 假设你已有这个客服函数
async def chatbot_response(conversation: Conversation, message: str) -> str:
    # 异步调用 LLM 或其他逻辑
    response = await conversation.handle_message(message)
    return response

@app.post("/chat")
async def chat(query: Query):
    try:
        user = UserList[query.user_id]
    except:
        user = User(query.user_id)

    try:
        conversation = ConversationList[query.conver_id]
    except:
        conversation = user.start_conversation(0)
    
    response = await chatbot_response(conversation, query.message)
    return {"response": response}





##########


