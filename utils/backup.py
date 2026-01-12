DEFAULT = "DEFAULT"

LLM_local_path_dict = {
    "weak LLM": "/data/public/model/Qwen2.5-32B-Instruct",
    "NLP-LLM": "/data/public/model/Qwen2.5-32B-Instruct",
    "reasoning LLM": "/data/public/model/Qwen2.5-32B-Instruct",
    "SQL LLM": "/data/public/model/Qwen2.5-32B-Instruct",
    DEFAULT: "/data/public/model/Qwen2.5-32B-Instruct",
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
    