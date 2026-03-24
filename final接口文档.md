# 重要！所有的返回字段遵守以下规则
{
  "code":0/1 # 0成功 1失败
  "msg": #成功就写对应功能成功 失败就写对应功能失败
  "data":
    {
      "...":...
    }
}

# 有很多接口的返回字段我没有全部写出来，根据经验和后端的功能，以及各种后端接口之间的配合，最好利用现有的逻辑和字段返回合理的消息和字段，一定要包含code和msg

# 对话界面接口
## 1. 初始化并获取新会话ID
- get 后端生成当前时间戳给前端
- 返回
{
  "code":0
  "msg":"新建对话成功"
  "data":{
    "conversation_id": "1774340847229"
  }
	
}

## 2. 发送对话接口
- POST
- 传入conversation_id
- 返回
{
  "code":0
  "msg":"发送对话成功"
  "data"{

  }
}
目前历史记录中一次完整的对话的json是
{
  "role": "user",
  "content": "1"
},
{
  "role": "assistant",
  "content": "请提供更多信息或上下文，以便我能够更好地帮助您。您是想要解读某个特定文件的内容吗？如果是，请提供相关的细节或问题。"
}
改成一个{
  "code":0
  "msg":"发送对话成功"
  "data":{
    "message_index":0 # 第几轮对话
    "question":"1"
    "files":[] # 列表形式，存文件的名字
    "web_search":bool # 是否开启联网
    "db_version": # 数据库选择哪个
    "answer":"..."
    "resource": # 参考来源
      {
        "link":参考链接
        "title" 标题
        "content"内容摘要
      }
    "recommend_answer"：# 推荐回答，3个
    }
    "feedback": like/dislike/None
}的形式，同时把这个消息存到history_storage中，以{conversation_id}.json命名，建议改为history_storage/2026-03-19/{conversation_id}.json，可以一天一个文件夹
## 3 展示标题
- get 对话的第0个问题的字符串作为标题
## 4. 点击标题进入对话
- GET  conversation_id
- 返回该conversation_id的message_index=0的question的字符串
## 5. 上传文件接口
- POST 这个接口目前还没有实现 /upload
- 实现计划：接受文件，把文件名字放进刚才对话的body中的file列表字段，这个文件存放到一个目录下，计划维护在/{conversation_id}/message_index/中 如果有更好的实现方式也可以
- 也就是说 前端给文件后 后端的字段要写两个 一个file_id 一个url 这个url就可以是/{conversation_id}/message_index，然后消息中的files列表有了file的名字之后，自动和当前的message_index和conversation_id拼一起去给后端大模型
- 
## 6. 选择数据库接口
- 未实现，和消息字段中的db_version联动
<!-- ## 7. 待办：获取系统用户信息 -->

# 历史记录接口
## 1. 展示所有历史记录
- 获取对话历史摘要列表
- GET 三个查询参数：查询的内容，起始时间，结束时间
- 返回符合要求的消息
- 和前面的展示标题类似，返回历史记录中存的所有字段
## 2. 批量删除历史对话
- 传入conversion_id的列表，批量删除
## 3. 展示历史对话详情
- 和点击标题进入对话类似 传入conversion_id，返回历史记录中存的所有字段
# 反馈接口
## 1. 提交用户反馈
- POST 传入
{
  "conversation_id"
  "message_index"
  "type":bool like/dislike
  "time":#上传时间
  "update_time":# 更新时间
  "state"：#状态 目前是赞还是踩还是NULL
  "reasons": {} #这个后续是选择点踩理由 必填
  "comment":# 这个是字符串评论
  "pictures":  # 图片名字列表
}
将反馈存入根目录中，目前是按照feedback/2026-03-19/fb_{conversation_id}_{message_index}来存储的
pictures看下面的上传图片接口
另外这个点赞和点踩的状态要同步给历史记录中的feedback字段（默认None），根据type和state判断当前是否赞或踩还是取消，方便前端显示赞和踩，
## 2. 点踩上传图片接口
- 点踩上传pictures的逻辑类似之前的上传文件，只不过换一个url和pictures字段名，只不过这里的图片名字可以自己定义，建议和反馈名字一样，但是有多个
## 3. 展示全部反馈页面
- GET 和展示全部历史记录类似 五个查询参数 反馈人name，反馈人企业，反馈类型，开始时间，结束时间 
## 4. 批量删除反馈
- 和批量删除历史对话功能类似
## 5. 获取单个反馈详情
- 和获取单个历史记录类似，传入拼成的反馈id：fb_{conversation_id}_{message_index} 展示该json中的所有字段
# 知识库
## 1. 新建知识库
- POST 传入三个参数 知识库名称， 知识库分类（企业知识库、部门知识库、个人知识库），向量模型 
- 向量模型的选择涉及到RAG的embedding模型，看一下代码，目前只有一个
- 返回创建成功消息
- 目前的实现方式是documents/{知识库分类}/{实体}/{知识库名称}，比如：documents/企业知识库/图湃（北京）医疗科技/测试/...
## 2. 从知识库中添加文档
- 在一个知识库中添加文件，POST 传入知识库的ID 和之前上传文件的接口类似，分析一下当前的实现方法，看是否有优化的地方
## 3. 从知识库中删除文档
- 和前面历史记录，反馈记录的删除类似，批量删除某一个知识库中的文件，传入知识库ID,文件名（或文件id？），文件url
## 4. 更新知识库
- 更新知识库的元数据，比如名字，添加备注，是否启用，选择哪些用户有权使用
## 5. 删除知识库
## 6. 展示知识库页面
- 和展示历史记录，反馈记录类似，
- GET 返回的是所有该用户创建的知识库的信息
目前是：
{
		"id": "ca2a9642", #这个id不知道怎么来的，不知道为什么不用时间戳 ,比如kb_{time}
		"name": "测试",
		"model": "openai",
		"category": "企业知识库",
		"owner_info": "图湃（北京）医疗科技/技术部",
		"physical_path": "企业知识库/图湃（北京）医疗科技/测试", # 
		"remark": "",
		"users": [
			name:
      phone:
      categoryName
		],
		"enabled": false, #是否启用
		"updatedAt": "2026/03/11 18:08:15",# 更新时间
		"fileCount": 0 #该知识库url下文件数量
	},
但我觉得有些字段多了，必要的有 知识库名称 使用人 文件数量 更新时间 是否启用 
## 7. 展示知识库详情页面
- 这个跟上一个的区别是，这个是在点击某一个知识库详情之后的，GET 传入知识库ID和URL 要返回该知识库中的所有文件名字，上传时间




# ！重要，当前有些功能是实现了的但是不够统一优雅，之前的前后端耦合度太高，需要重构一下，分类后端接口，字段统一，比如时间戳统一用str还是float；知识库方面的接口写的不够完善，如果有不懂的立刻向我提问而不是强行修改或融合现有代码，比如知识库的ID等方面细节
# 另外，部分接口涉及到了用户的个人信息，这个实现方式是由其他人的后端完成的，他们的实现方式是用一个token来认证，GET，Header请求参数为accessToken，参数值：{{accessTokenValue}} ，str类型，必填
{
	"code": 0,
	"msg": "成功",
	"data": {
		"fullName": "张美琴琴",//员工姓名
		"phones": "19923719837",//员工电话
		"headSculpture": "r-d-local/e1/head-sculpture/1762076149836.png",//员工头像
		"enableStatusName": null,
		"roleStatusName": null,
		"lockStatusName": null,
		"initStatusName": null,
		"existWorkStatusName": null,
		"returneeStatusName": null,
		"foreignStatusName": null,
		"talentPlanStatusName": null,
		"categoryName": null,
		"employmentMethodName": null,
		"channelLogoOpenStatus": null,//渠道logo打开状态   7777=否， 9999=是
		"channelLogoAnnexUrl": null//渠道logo图片地址
	},
	"timeStamp": 1762409348329
}这是返回字段，只需要员工姓名，员工电话，所属企业

