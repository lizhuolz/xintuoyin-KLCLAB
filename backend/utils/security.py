import os
from typing import Tuple, Dict, Any, List
# 引入 LLM Guard 组件
from llm_guard.vault import Vault
from llm_guard import scan_prompt, scan_output
from llm_guard.input_scanners import (
    Anonymize, BanSubstrings, Gibberish, InvisibleText, 
    PromptInjection, Secrets, TokenLimit, Toxicity
)
from llm_guard.output_scanners import NoRefusal, Deanonymize, BanTopics

# 初始化 Vault (单例模式)
_VAULT = Vault()

# 定义输入防御层 (Input Scanners)
_INPUT_SCANNERS = [
    BanSubstrings(
        substrings=[
            "炸弹", "生化武器", "自杀", "ignore previous instructions"
        ],
        match_type="str",
        case_sensitive=False
    ),
    PromptInjection(threshold=0.8), # 调高阈值，减少误报
    InvisibleText(),
    Secrets(redact_mode="partial"),
    Anonymize(vault=_VAULT),
    # TokenLimit(limit=4000), # 放宽长度限制
    Toxicity(threshold=0.8), # 调高阈值
    Gibberish(threshold=0.8), # 调开阈值，防止技术类乱码误判
]

_HIGH_RISK_PROMPT_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous instructions",
    "system prompt",
    "developer message",
    "reveal the prompt",
    "jailbreak",
    "忽略之前的指令",
    "忽略以上指令",
    "忽略系统提示",
    "系统提示词",
    "开发者消息",
    "越狱",
    "绕过限制",
]


def _contains_high_risk_prompt_injection(text: str) -> bool:
    lowered = (text or "").lower()
    return any(pattern in lowered for pattern in _HIGH_RISK_PROMPT_INJECTION_PATTERNS)


# 定义输出防御层 (Output Scanners)
_OUTPUT_SCANNERS = [
    NoRefusal(),
    BanTopics(topics=["explosives", "weapons"], threshold=0.8), # 调高阈值
    Deanonymize(vault=_VAULT)
]

def check_input_safety(text: str) -> Tuple[str, bool, str]:
    """
    检查输入安全性
    Returns: (sanitized_prompt, is_valid, error_msg)
    """
    try:
        sanitized_prompt, results_valid, results_score = scan_prompt(_INPUT_SCANNERS, text)

        invalid_scanners = [name for name, is_valid in results_valid.items() if not is_valid]
        if invalid_scanners:
            # 仅 PromptInjection 命中且不包含明显越权/绕过意图时，按误报放行。
            if invalid_scanners == ["PromptInjection"] and not _contains_high_risk_prompt_injection(text):
                score = results_score.get("PromptInjection", 0)
                print(f"[Security] PromptInjection false positive ignored (score={score}): {text[:120]}")
                return sanitized_prompt, True, ""

            errors = []
            for scanner_name in invalid_scanners:
                score = results_score.get(scanner_name, 0)
                errors.append(f"{scanner_name} (score: {score})")
            return text, False, f"输入包含违规内容，已被防火墙拦截: {', '.join(errors)}"

        return sanitized_prompt, True, ""
    except Exception as e:
        print(f"Safety check error (Input): {e}")
        # 出错时默认放行，避免阻断业务，但记录日志
        return text, True, "" 

def check_output_safety(prompt: str, response: str) -> Tuple[bool, str]:
    """
    检查输出安全性 (用于审计或拦截)
    Returns: (is_valid, warning_msg)
    """
    try:
        _, out_valid, _ = scan_output(_OUTPUT_SCANNERS, prompt, response)
        if any(not is_valid for is_valid in out_valid.values()):
            errors = [k for k, v in out_valid.items() if not v]
            return False, f"输出内容可能违反安全策略: {', '.join(errors)}"
        return True, ""
    except Exception as e:
        print(f"Safety check error (Output): {e}")
        return True, ""
