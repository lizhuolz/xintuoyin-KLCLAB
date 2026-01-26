import os
from openai import OpenAI

def get_client():
    # Prioritize DEEPSEEK_API_KEY, fallback to OPENAI_API_KEY, then raise error if missing
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com'
    
    if not api_key:
        raise RuntimeError('Missing API key. Please set DEEPSEEK_API_KEY or OPENAI_API_KEY in your environment.')
        
    # Set a 30-second timeout to prevent dead loops on network issues
    return OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)

def chat(messages, model='deepseek-chat', stream=False):
    client = get_client()
    
    # Debug: Print input messages
    print(f"DEBUG: Input messages: {messages}")

    try:
        resp = client.chat.completions.create(model=model, messages=messages, stream=stream, max_tokens=100)
        
        if stream:
            print("DEBUG: Stream object received")
            for part in resp:
                # Debug: Inspect raw part
                # print(f"DEBUG RAW PART: {part}") 
                delta = part.choices[0].delta
                content = getattr(delta, 'content', None)
                if content:
                    print(f"DEBUG CONTENT: {content[:10]}...") # Debug print
                    yield content
                else:
                    print("DEBUG: No content in delta")
        else:
            return resp.choices[0].message.content
    except Exception as e:
        err = f"API Error: {str(e)}"
        print(err)
        if stream:
            yield err
        else:
            return err
