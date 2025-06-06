import torch
from ollama import chat
from ollama import ChatResponse
import ollama


DEFAULT = "DEFAULT"

ollama_LLM_path_dict = {
    "weak-LLM": "qwen2.5:32b",
    "NLP-LLM": "qwen2.5:32b",
    "reasoning-LLM": "qwen2.5:32b",
    "SQL-LLM": "qwen2.5:32b",
    DEFAULT: "qwen2.5:32b",
}

def query_LLM_ollama(llm_name, query, only_return_response=True):
    llm_path = ollama_LLM_path_dict.setdefault(llm_name, ollama_LLM_path_dict[DEFAULT])
    if isinstance(query, str):
        raw_response = ollama.generate(model=llm_path, prompt=query)
        if only_return_response:
            return raw_response['response']
        else:
            raise NotImplementedError
    elif isinstance(query, list) and isinstance(query[0], str):
        raise NotImplementedError
    elif isinstance(query, list) and isinstance(query[0], dict):
        response: ChatResponse = chat(model=llm_path, messages=query)
        raw_response = response['message']['content']
        if only_return_response:
            return raw_response
        else:
            raise NotImplementedError


vllm_LLM_path_dict = {
    "weak LLM": {"base_url": "http://localhost:8000/v1", "api_key": "token-abc123", "model":"/data1/public/models/Qwen2.5-32B-Instruct"},
    "NLP-LLM": {"base_url": "http://localhost:8000/v1", "api_key": "token-abc123", "model":"/data1/public/models/Qwen2.5-32B-Instruct"},
    "reasoning LLM": {"base_url": "http://localhost:8000/v1", "api_key": "token-abc123", "model":"/data1/public/models/Qwen2.5-32B-Instruct"},
    "SQL LLM": {"base_url": "http://localhost:8000/v1", "api_key": "token-abc123", "model":"/data1/public/models/llama-3-sqlcoder-8b"},
    "SQL seletor": {"base_url": "http://localhost:8000/v1", "api_key": "token-abc123", "model":"/data1/public/models/Qwen2.5-14B-Instruct"},
    DEFAULT: {"base_url": "http://localhost:8000/v1", "api_key": "token-abc123", "model":"/data1/public/models/Qwen2.5-32B-Instruct"},
}


from vllm import LLM, SamplingParams
from openai import OpenAI
def query_LLM_vllm(llm_name, query, only_return_response):
    llm_path = vllm_LLM_path_dict.setdefault(llm_name, vllm_LLM_path_dict[DEFAULT]).copy()
    model_name = llm_path.pop("model")
    client = OpenAI(**llm_path)

    if isinstance(query, str):
        resposne = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": query}
            ]
        )
    elif isinstance(query, list) and isinstance(query[0], str):
        raise NotImplementedError
    elif isinstance(query, list) and isinstance(query[0], dict):
        resposne = client.chat.completions.create(
            model=model_name,
            messages=query
        )
    response = response.choices[0].message.content
    if only_return_response:
        return resposne
    else: 
        return query + resposne
    

LLM_local_path_dict = {
    "weak LLM": "/data1/public/models/Qwen2.5-32B-Instruct",
    "NLP-LLM": "/data1/public/models/Qwen2.5-32B-Instruct",
    "reasoning LLM": "/data1/public/models/Qwen2.5-32B-Instruct",
    "SQL LLM": "/data1/public/models/Qwen2.5-32B-Instruct",
    DEFAULT: "/data1/public/models/Qwen2.5-32B-Instruct",
}

def load_LLM(llm_name, context):
    llm_path = LLM_local_path_dict.setdefault(llm_name, LLM_local_path_dict[DEFAULT])

    if llm_path in context['LLM/model'].keys() and llm_path in context['LLM/tokenizer'].keys():
        return
    
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch 
    model = AutoModelForCausalLM.from_pretrained(
        llm_path,
        device_map = "cuda:0",
        torch_dtype = torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(llm_path)

    context['LLM/model'][llm_path] = model
    context['LLM/tokenizer'][llm_path] = tokenizer


context = {
    'LLM/model': {},
    'LLM/tokenizer': {},
}
import torch
def query_LLM_hf(llm_name, query, only_return_response=True):
    global context;
    llm_path = LLM_local_path_dict.setdefault(llm_name, LLM_local_path_dict[DEFAULT])
    load_LLM(llm_name, context)
    model = context['LLM/model'][llm_path] 
    tokenizer = context['LLM/tokenizer'][llm_path] 

    generation_kwargs = {
        "max_new_tokens": 128,
        'min_length': -1, 
        "top_k": 0.0,
        "top_p": 0.95, 
        "do_sample": True,
        "temperature": 0.7,
        "pad_token_id": tokenizer.eos_token_id,
        "begin_suppress_tokens": [tokenizer.eos_token_id],
        "no_repeat_ngram_size": 5
    }
    generation_kwargs = {
        "max_new_tokens": 2000,
        "do_sample": False,
    }


    if isinstance(query, str):
        message = [{"role":"user", "content":query}]
    elif isinstance(query, list) and isinstance(query[0], str):
        raise NotImplementedError
    elif isinstance(query, list) and isinstance(query[0], dict):
        message = query
    
    input = tokenizer.apply_chat_template(
        message,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to(model.device)
    with torch.no_grad():
        output = model.generate(input, **generation_kwargs)
    response = tokenizer.decode(output[0])   ### bug here

    raw_input = tokenizer.apply_chat_template(
        message,
        tokenize=False,
        add_generation_prompt=True,
    )
    raw_response = response.replace(raw_input, "")

    if only_return_response:
        return raw_response
    else:
        return response



def query_LLM_backend(llm_name, query, only_return_response=True):
    try:
        return query_LLM_vllm(llm_name, query, only_return_response)
    except:
        try:
            return query_LLM_ollama(llm_name, query, only_return_response)
        except:
            return query_LLM_hf(llm_name, query, only_return_response)