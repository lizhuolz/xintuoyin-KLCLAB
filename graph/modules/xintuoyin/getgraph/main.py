import argparse, atexit, re, shutil, subprocess, tempfile, time
from pathlib import Path
from unittest import result
from urllib import response
from click import prompt
from openai import OpenAI
from docling.document_converter import (
    DocumentConverter,
    ImageFormatOption,
    InputFormat,
)
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
)
import os,json
import pandas as pd
from openpyxl import load_workbook



#所有的文件
category_list = ['研发项目汇总表','研发费用加计扣除优惠明细表','研发支出辅助帐汇总表','研发支出辅助帐-项目名称','企业研发项目情况表','企业研发活动及相关情况表','委托合同','委托费用明细表','项目立项决议书','项目立项报告','项目计划任务书','鉴定意见','科技部门登记合同','检索记录','论证记录','调研记录','成果附件','结题报告','研发人员名单','人员人工费用明细表','社保补缴','人员工时记录','直接投入费用明细','材料领用','燃料领用','动力消耗明细','设备租金费用明细表','设备工时记录','设备折旧费用明细表','无形资产工时记录','无形资产摊销费用明细表','新产品设计费','其他费用明细表','补充养老保险费用明细','补充医疗保险费用明细','职工福利费用明细','发票']
OTHER_CATEGORY = "other"
CATEGORY_ALIASES = {
    "鉴定建议": "鉴定意见",
    "验收意见": "鉴定意见",
    "专家评审报告": "鉴定意见",
    "调研报告": "调研记录",
    "调研纪要": "调研记录",
    "调研材料": "调研记录",
}

#真正有主键的文件
really_key_file = ['研发人员名单','研发项目汇总表','研发支出辅助帐汇总表','企业研发项目情况表']

#用户上传的文件，自动识别文件类别，支持各种非规则化文件格式，提取所要求的各种信息与关键字
upload_file = ['委托合同','项目立项决议书','项目立项报告','项目计划任务书','鉴定意见','科技部门登记合同','检索记录','论证记录','调研记录','成果附件','结题报告','发票']

#以工号为主键
worker_id_key_file = ['人员人工费用明细表','社保补缴','人员工时记录','补充养老保险费用明细','补充医疗保险费用明细','职工福利费用明细']

#以无形资产为主键
intangible_asset_key_file = ['无形资产工时记录','无形资产摊销费用明细表']

#以设备编号为主键
device_key_file = ['设备租金费用明细表','设备工时记录','设备折旧费用明细表']

#表格文件，自动识别文件类别，然后在存储表格原始信息在前端图谱展示的文件
xlsx_file = ["研发费用加计扣除优惠明细表","研发支出辅助帐-项目名称","企业研发活动及相关情况表",'直接投入费用明细','材料领用','燃料领用','动力消耗明细','新产品设计费','其他费用明细表','委托费用明细表']

xlsx_file = xlsx_file + worker_id_key_file + intangible_asset_key_file + device_key_file

#自动识别文件类别，可以提取每行的内容，识别其中的业务主键，有多少行样本就生成多少的对应节点
other_xlsx_file = [file for file in category_list if file not in xlsx_file + upload_file]

ENTITY_GROUP_MAP = {
    "负责人": 1, "参与人员": 1, "项目成员": 1, "协作接口人": 1, "专家姓名": 1,
    "负责人（姓名、单位、联系方式）": 1, "项目负责人": 1, "负责技术落地指导": 1,
    "开票人": 1, "复核人": 1, "收款人": 1, "主持人": 1,
    "记录人": 1, "参与调研人员": 1, "项目联系人": 1, "姓名": 1, "法定代表人（签章）：": 1,
    "甲方（委托方）": 2, "乙方（受托方）": 2, "协作单位": 2, "专家名单": 2,
    "单位/职称": 2, "购买方（名称、纳税人识别号、地址电话、开户行及账号）": 2,
    "销售方（名称、纳税人识别号、地址电话、开户行及账号）": 2, "委托方/受托方信息": 2,
    "执行单位/团队": 2,
    "项目名称": 3, "成果名称": 3, "调研主题": 3, "论证事项": 3, "发票类型": 3,
    "项目名称（商品或服务名称）": 3,
    "不可抗力": 4, "项目单位": 4,
    "部门（如：AI 研发部、前端团队、数据中心）": 4
}


def get_entity_group(entity_key):
    return ENTITY_GROUP_MAP.get(entity_key, 4)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
PDF_EXTENSIONS = {".pdf"}
TEXT_EXTENSIONS = {".txt"}
LEGACY_XLS_EXTENSIONS = {".xls"}
SPREADSHEET_EXTENSIONS = {".xlsx"} | LEGACY_XLS_EXTENSIONS
TABULAR_EXTENSIONS = SPREADSHEET_EXTENSIONS | {".csv"}
IMAGE_OCR_GPU_MIN_FREE_MB = int(os.getenv("IMAGE_OCR_GPU_MIN_FREE_MB", "4096"))
IMAGE_DIRECT_OCR_MIN_TEXT_LEN = int(os.getenv("IMAGE_DIRECT_OCR_MIN_TEXT_LEN", "20"))
LEGACY_XLS_CACHE = {}
TEMP_DIRS_TO_CLEAN = []


class MarkdownDocument:
    def __init__(self, markdown_text: str):
        self._markdown_text = markdown_text

    def export_to_markdown(self) -> str:
        return self._markdown_text


class SimpleConversionResult:
    def __init__(self, markdown_text: str):
        self.document = MarkdownDocument(markdown_text)


def _register_temp_dir(path: str):
    TEMP_DIRS_TO_CLEAN.append(path)


def _cleanup_temp_dirs():
    for path in TEMP_DIRS_TO_CLEAN:
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass


atexit.register(_cleanup_temp_dirs)


def _group_rapidocr_result(ocr_result):
    lines = []
    items = []

    for item in ocr_result or []:
        if len(item) < 2:
            continue
        box = item[0]
        text = str(item[1] or "").strip()
        if not box or not text:
            continue

        xs = [point[0] for point in box]
        ys = [point[1] for point in box]
        left = min(xs)
        right = max(xs)
        top = min(ys)
        bottom = max(ys)
        items.append(
            {
                "text": text,
                "left": left,
                "right": right,
                "top": top,
                "height": max(bottom - top, 1),
            }
        )

    if not items:
        return lines

    items.sort(key=lambda current: (current["top"], current["left"]))
    heights = sorted(item["height"] for item in items)
    median_height = heights[len(heights) // 2]
    line_threshold = max(10, int(median_height * 0.8))

    current_line = []
    current_top = None
    for item in items:
        if current_top is None or abs(item["top"] - current_top) <= line_threshold:
            current_line.append(item)
            if current_top is None:
                current_top = item["top"]
            else:
                current_top = (current_top + item["top"]) / 2
            continue

        lines.append(current_line)
        current_line = [item]
        current_top = item["top"]

    if current_line:
        lines.append(current_line)

    return lines


def _rapidocr_lines_to_text(ocr_result) -> str:
    rendered_lines = []

    for line in _group_rapidocr_result(ocr_result):
        ordered = sorted(line, key=lambda current: current["left"])
        parts = []
        previous_right = None
        previous_height = None

        for item in ordered:
            if previous_right is not None and previous_height is not None:
                gap = item["left"] - previous_right
                if gap > max(12, previous_height * 1.2):
                    parts.append(" ")
            parts.append(item["text"])
            previous_right = item["right"]
            previous_height = item["height"]

        rendered_line = "".join(parts).strip()
        if rendered_line:
            rendered_lines.append(rendered_line)

    return "\n".join(rendered_lines).strip()


def extract_image_text_with_rapidocr(source: str) -> str:
    from rapidocr_onnxruntime import RapidOCR

    reader = RapidOCR(use_cls=False)
    ocr_result, _ = reader(source)
    return _rapidocr_lines_to_text(ocr_result)


def extract_pdf_text_with_rapidocr(source: str) -> str:
    from rapidocr_onnxruntime import RapidOCR
    import pypdfium2 as pdfium

    reader = RapidOCR(use_cls=False)
    pdf = pdfium.PdfDocument(source)
    rendered_pages = []

    try:
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            bitmap = page.render(scale=2)
            pil_image = bitmap.to_pil()
            ocr_result, _ = reader(pil_image)
            page_text = _rapidocr_lines_to_text(ocr_result)
            if page_text:
                rendered_pages.append(f"[PAGE {page_index + 1}]\n{page_text}")
    finally:
        pdf.close()

    return "\n\n".join(rendered_pages).strip()


def read_text_file(source: str) -> str:
    encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk", "utf-16"]
    for encoding in encodings:
        try:
            return Path(source).read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return Path(source).read_text(encoding="utf-8", errors="ignore")


def convert_legacy_xls_to_xlsx(source: str) -> str:
    source_path = os.path.abspath(source)
    cached = LEGACY_XLS_CACHE.get(source_path)
    if cached and os.path.exists(cached):
        return cached

    soffice_path = shutil.which("soffice")
    if not soffice_path:
        raise RuntimeError("未找到 soffice，无法处理 .xls 文件")

    temp_dir = tempfile.mkdtemp(prefix="getgraph_xls_")
    _register_temp_dir(temp_dir)
    completed = subprocess.run(
        [
            soffice_path,
            "--headless",
            "--convert-to",
            "xlsx",
            "--outdir",
            temp_dir,
            source,
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "xls 转 xlsx 失败: "
            f"{completed.stderr.strip() or completed.stdout.strip() or '未知错误'}"
        )

    converted_path = os.path.join(temp_dir, f"{Path(source).stem}.xlsx")
    if not os.path.exists(converted_path):
        candidates = sorted(Path(temp_dir).glob("*.xlsx"))
        if not candidates:
            raise RuntimeError("xls 转 xlsx 失败: 未找到转换后的 xlsx 文件")
        converted_path = str(candidates[0])

    LEGACY_XLS_CACHE[source_path] = converted_path
    print(f"检测到 XLS 文件，已转换为 XLSX：{converted_path}")
    return converted_path

def select_image_ocr_device() -> str:
    try:
        import torch
    except Exception as exc:
        print(f"torch 不可用，图片 OCR 回退 CPU：{exc}")
        return AcceleratorDevice.CPU.value

    if not torch.cuda.is_available():
        print("未检测到可用 CUDA，图片 OCR 使用 CPU")
        return AcceleratorDevice.CPU.value

    best_device = None
    best_free_mb = -1

    for index in range(torch.cuda.device_count()):
        try:
            free_bytes, total_bytes = torch.cuda.mem_get_info(index)
            free_mb = int(free_bytes / 1024 / 1024)
            total_mb = int(total_bytes / 1024 / 1024)
            print(f"检测到 GPU {index}: free={free_mb}MB total={total_mb}MB")
            if free_mb > best_free_mb:
                best_free_mb = free_mb
                best_device = index
        except Exception as exc:
            print(f"读取 GPU {index} 显存信息失败：{exc}")

    if best_device is None:
        print("无法获取 GPU 显存信息，图片 OCR 使用 CPU")
        return AcceleratorDevice.CPU.value

    if best_free_mb < IMAGE_OCR_GPU_MIN_FREE_MB:
        print(
            f"当前最大可用显存仅 {best_free_mb}MB，小于阈值 "
            f"{IMAGE_OCR_GPU_MIN_FREE_MB}MB，图片 OCR 使用 CPU"
        )
        return AcceleratorDevice.CPU.value

    print(f"图片 OCR 选择 GPU {best_device}，当前空闲显存 {best_free_mb}MB")
    return f"cuda:{best_device}"


def build_image_converter(device: str) -> DocumentConverter:
    image_pipeline_options = PdfPipelineOptions(
        accelerator_options=AcceleratorOptions(device=device),
        ocr_options=RapidOcrOptions(
            lang=["english", "chinese"],
            use_cls=False,
        ),
    )
    return DocumentConverter(
        format_options={
            InputFormat.IMAGE: ImageFormatOption(
                pipeline_options=image_pipeline_options
            )
        }
    )


def build_converter_for_source(source: str) -> DocumentConverter:
    suffix = Path(source).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        return DocumentConverter()

    device = select_image_ocr_device()
    if device.startswith("cuda"):
        print(f"检测到图片文件，使用 GPU OCR 模式进行转换：{device}")
    else:
        print("检测到图片文件，使用 CPU OCR 模式进行转换")
    return build_image_converter(device)


def convert_source(source: str):
    suffix = Path(source).suffix.lower()

    if suffix in TEXT_EXTENSIONS:
        print("检测到 TXT 文件，使用 direct text 模式进行转换")
        return SimpleConversionResult(read_text_file(source))

    if suffix in LEGACY_XLS_EXTENSIONS:
        converted_source = convert_legacy_xls_to_xlsx(source)
        print("检测到 XLS 文件，使用转换后的 XLSX 继续解析")
        return DocumentConverter().convert(converted_source)

    if suffix not in IMAGE_EXTENSIONS and suffix not in PDF_EXTENSIONS:
        return DocumentConverter().convert(source)

    if suffix in IMAGE_EXTENSIONS:
        try:
            document_text = extract_image_text_with_rapidocr(source)
            if len(document_text) >= IMAGE_DIRECT_OCR_MIN_TEXT_LEN:
                print("检测到图片文件，使用 direct RapidOCR 模式进行转换")
                return SimpleConversionResult(document_text)
            print(
                f"direct RapidOCR 文本过短（{len(document_text)} 字），"
                "回退 Docling"
            )
        except Exception as exc:
            print(f"direct RapidOCR 处理失败，回退 Docling：{exc}")
    elif suffix in PDF_EXTENSIONS:
        try:
            document_text = extract_pdf_text_with_rapidocr(source)
            if len(document_text) >= IMAGE_DIRECT_OCR_MIN_TEXT_LEN:
                print("检测到 PDF 文件，使用 direct RapidOCR 模式进行转换")
                return SimpleConversionResult(document_text)
            print(
                f"PDF direct RapidOCR 文本过短（{len(document_text)} 字），"
                "回退 Docling"
            )
        except Exception as exc:
            print(f"PDF direct RapidOCR 处理失败，回退 Docling：{exc}")

    converter = build_converter_for_source(source)

    try:
        return converter.convert(source)
    except Exception as exc:
        message = str(exc)
        if "CUDA out of memory" not in message and "OutOfMemoryError" not in message:
            raise
        print(f"图片 OCR GPU 处理失败，回退 CPU 重试：{exc}")
        cpu_converter = build_image_converter(AcceleratorDevice.CPU.value)
        return cpu_converter.convert(source)

def normalize_category_name(raw_category: str) -> str:
    text = (raw_category or "").strip().strip("`")
    if not text:
        return ""
    if text.lower() == OTHER_CATEGORY:
        return OTHER_CATEGORY
    if text in category_list:
        return text
    return CATEGORY_ALIASES.get(text, text)


def match_category_in_text(text: str) -> str:
    haystack = (text or "").strip()
    if not haystack:
        return ""

    normalized = normalize_category_name(haystack)
    if normalized == OTHER_CATEGORY or normalized in category_list:
        return normalized

    for alias, target in CATEGORY_ALIASES.items():
        if alias in haystack:
            return target
    for cat in category_list:
        if cat in haystack:
            return cat
    return ""


def get_file_category(document_text: str, file_name: str = "") -> str:
    category_options = category_list + [OTHER_CATEGORY]
    file_name_hint = ""
    if file_name:
        file_name_hint = (
            f"文件名：{file_name}\n"
            "可结合文件名判断类别；若文件名与正文/OCR 内容存在轻微差异，以最匹配的标准类别为准。\n\n"
        )
    prompt = (
        "请根据以下内容判断该文件属于以下哪一类："
        f"{', '.join(category_options)}。"
        "注意同义表达需要映射到标准类别，例如：鉴定建议、验收意见、专家评审报告 -> 鉴定意见；"
        "调研报告、调研纪要 -> 调研记录。"
        f"如果内容与上述已知类别都不匹配，请返回 {OTHER_CATEGORY}。"
        "只需返回类别名称，不要返回其他内容。\n\n"
        f"{file_name_hint}"
        f"文件内容：\n{document_text}"
    )

    chat_response = create_chat_completion(
        model=args.model_path,
        messages=[
            {"role": "system", "content": "你是一个专业的信息提取助手"},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=int(os.getenv("GETGRAPH_CATEGORY_MAX_TOKENS", "64")),
        extra_body=DISABLE_THINKING_EXTRA_BODY,
        #response_format={"type": "json_object"}
    )


    response_text = chat_response.choices[0].message.content

    print("文件分类模型返回结果：")
    print(response_text.strip())

    raw = response_text.strip()
    if "</think>" in raw:
        raw = raw.split("</think>")[-1].strip()

    lines = [line.strip().strip("`") for line in raw.splitlines() if line.strip()]
    saw_other = False
    for line in reversed(lines):
        normalized = normalize_category_name(line)
        if normalized == OTHER_CATEGORY:
            saw_other = True
            continue
        if normalized in category_list:
            return normalized

    tail = lines[-1] if lines else raw
    matched = match_category_in_text(tail)
    if matched in category_list:
        return matched
    if matched == OTHER_CATEGORY:
        saw_other = True

    name_matched = match_category_in_text(Path(file_name).stem if file_name else "")
    if name_matched in category_list:
        return name_matched
    if saw_other:
        return OTHER_CATEGORY
    return OTHER_CATEGORY


def extract_json_candidate(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if not text:
        return text

    if "</think>" in text:
        text = text.split("</think>")[-1].strip()

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    json_match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", text)
    if json_match:
        return json_match.group().strip()
    return text


def unwrap_result_dict(result_dict):
    current = result_dict
    while isinstance(current, dict):
        if (
            isinstance(current.get("name"), str)
            and current.get("name")
            and "value" in current
        ):
            return {current["name"]: current.get("value")}
        if "content" in current and isinstance(current.get("content"), str):
            inner = extract_json_candidate(current.get("content", ""))
            try:
                current = json.loads(inner)
                continue
            except Exception:
                break
        if "data" in current and isinstance(current.get("data"), list):
            return current["data"]
        if "data_rows" in current and isinstance(current.get("data_rows"), list):
            return current["data_rows"]
        if "rows" in current and isinstance(current.get("rows"), list):
            return current["rows"]
        if "数据" in current and isinstance(current.get("数据"), list):
            return current["数据"]
        break
    return current


def _stringify_nullable(value):
    if value in [None, "", "null"]:
        return None
    return str(value).strip()


def _join_invoice_party_fields(value):
    if not isinstance(value, dict):
        text = _stringify_nullable(value)
        return text if text else None

    name = _stringify_nullable(value.get("名称"))
    tax_id = _stringify_nullable(value.get("纳税人识别号"))
    address_phone = _stringify_nullable(value.get("地址电话"))
    bank_account = _stringify_nullable(value.get("开户行及账号"))
    details = [item for item in [tax_id, address_phone, bank_account] if item]

    if name and details:
        return f"{name}（{'；'.join(details)}）"
    if name:
        return name
    if details:
        return "；".join(details)
    return None


def _join_invoice_line_items(items, field_name):
    values = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get(field_name)
        text = _stringify_nullable(value)
        if text:
            values.append(text)
    return "；".join(values) if values else None


def normalize_invoice_result(result_dict):
    if not isinstance(result_dict, dict):
        return result_dict

    normalized = dict(result_dict)
    field_aliases = {
        "购买方": "购买方（名称、纳税人识别号、地址电话、开户行及账号）",
        "销售方": "销售方（名称、纳税人识别号、地址电话、开户行及账号）",
        "备注栏": "备注栏（如项目编号；合同号；付款方式）",
    }

    for source_key, target_key in field_aliases.items():
        if target_key not in normalized and source_key in normalized:
            normalized[target_key] = normalized[source_key]

    for party_key in [
        "购买方（名称、纳税人识别号、地址电话、开户行及账号）",
        "销售方（名称、纳税人识别号、地址电话、开户行及账号）",
    ]:
        normalized_value = _join_invoice_party_fields(normalized.get(party_key))
        if normalized_value:
            normalized[party_key] = normalized_value

    line_items = normalized.get("明细")
    if isinstance(line_items, list):
        mappings = {
            "项目名称（商品或服务名称）": "项目名称",
            "规格型号": "规格型号",
            "单位": "单位",
            "数量": "数量",
            "单价": "单价",
            "金额（不含税）": "金额",
            "税率": "税率",
            "税额": "税额",
        }
        for target_key, item_key in mappings.items():
            if target_key not in normalized or normalized.get(target_key) in [None, "", "null"]:
                joined = _join_invoice_line_items(line_items, item_key)
                if joined:
                    normalized[target_key] = joined

    return normalized

def get_entity_attr(file_category, result_dict):
    edges = [] # {"source": "Transformer", "target": "Attention Mechanism", "relation": "uses"},
    nodes_attr = []

    def build_entity_id(entity_key, entity_value, attrs):
        if entity_key == "姓名" and entity_value not in [None, "", "null"]:
            worker_id = attrs.get("工号")
            if worker_id not in [None, "", "null"]:
                return f"{entity_value}-{worker_id}"
        return entity_value

    if file_category in xlsx_file:
        nodes_attr.append(
            {
                "object": file_category, 
                "type": "excel", 
                "table_html": result_dict, 
                "attribute": {} 
            }
        )
        return edges, nodes_attr

    elif file_category in upload_file:
        if file_category == '项目立项报告':
            entitys_attributes = {
                "项目名称": ["日期","项目周期","资金来源","项目阶段","经费预算情况","预期目标","项目创新性","政策/行业依据","问题痛点量化","替代方案对比",
                        "技术可行性","市场可行性","阶段节点","交付物验收标准","非经费资源清单","外部合作协议要点","科目细分比例","预算调整机制","风险类型","发生概率",
                        "影响程度","应对措施","经济效益","社会效益","查新报告结论","专家评审意见摘要","部门初审意见","表决结果"],
                "参与人员": [],
                "负责人": []
            }
        elif file_category == '委托合同':
            entitys_attributes = {
                "项目名称": [
                    "期限", "技术成果归属方", "价款、报酬、费用", "技术目标", "技术内容",
                    "费用类型", "违约责任", "保密义务", "争议解决", "验收标准",
                    "交付物清单", "知识产权", "风险承担", "合同变更", "生效条件", "附件效力"
                ],
                "甲方（委托方）": [],
                "乙方（受托方）": [],
                "不可抗力": [],
                "项目联系人": []
            }
        elif file_category == '项目立项决议书':
            entitys_attributes = {
                "项目名称": [
                    "日期", "项目目标", "项目预算", "项目周期", "项目内容", "实施计划",
                    "项目预期效益", "项目编号", "项目类型", "优先级", "所属部门/业务线",
                    "政策依据", "市场驱动因素", "问题痛点", "决策机构", "立项背景",
                    "决议编号", "人力投入", "设备/场地", "外部采购", "主要风险点",
                    "应对预案", "关键成果物（KPI）", "验收标准", "后续维护责任", "附件清单"
                ],
                "负责人": [],
                "项目成员": [],
                "协作单位": []
            }
        elif file_category == '项目计划任务书':
            entitys_attributes = {
                "项目名称": [
                    "日期", "项目周期", "负责人", "立项依据和目的意义", "主要内容、目标和关键技术",
                    "进度计划", "费用预算", "层级化任务结构", "责任人与时间绑定", "依赖关系标注",
                    "关键节点评审", "交付物标准模板", "阶段验收", "终验条件", "资源类型", "名称",
                    "可用时段", "负载率上限", "预防措施", "应急资源", "进度偏差率", "问题升级清单",
                    "变更申请单要素", "基线锁定规则", "团队KPI", "个人考核权重", "文档归档", "经验总结会"
                ],
                "协作接口人": []
            }
        elif file_category == '鉴定意见':
            entitys_attributes = {
                "项目名称": [
                    "日期", "项目周期", "意见/建议", "结论", "鉴定编号", "委托单位",
                    "鉴定级别", "创新程度分级", "技术指标比对", "成熟度等级",
                    "评审分组", "核心意见摘要", "分歧点", "表决结果", "标准文件",
                    "材料审查结论", "成果登记建议", "保密级别", "推广意见",
                    "需补充材料", "复验方式", "检测报告编号", "查新报告核心结论"
                ],
                "专家名单": [],
                "专家姓名": [],
                "单位/职称": []
            }  
        elif file_category == '科技部门登记合同': 
            entitys_attributes = {
                "项目名称": [
                    "合同编号", "签订日期", "委托方/受托方信息", "合同总金额", "付款方式（分期/一次性）",
                    "发票要求", "知识产权归属", "保密义务", "违约责任", "登记管理信息", "登记日期",
                    "合同类别", "监管要求", "验收备案要求", "财政资金使用合规性", "阶段验收节点",
                    "验收异议处理", "付款阶段", "比例", "支付条件", "逾期违约金计算方式", "使用范围限制",
                    "侵权责任划分", "涉密信息界定", "泄密举证责任", "诉前和解期", "执行地域", "可分割性",
                    "文本与语言"
                ]
            }    
        elif file_category == '检索记录':
            entitys_attributes = {
                "项目名称": [
                    "结果/结论", "检索词", "外部近似专利", "企业已有相关专利",
                    "项目的技术发展状况", "检索机构资质", "检索式", "分类号",
                    "检索日期", "数据库清单及范围", "检索人资质", "复核人信息",
                    "专利号", "权利要求相似度", "核心差异点", "法律状态",
                    "同族专利", "地域布局", "未覆盖范围", "数据滞后风险",
                    "深度检索方向", "专利规避方案", "报告用途", "版本控制",
                    "专利全文复印件", "查新报告", "结论"
                ]
            }
        elif file_category == '结题报告':
            entitys_attributes = {
                "项目名称": [
                    "项目编号",
                    "立项单位",
                    "立项时间",
                    "计划结题时间",
                    "实际结题时间",
                    "研究目标",
                    "主要研究内容",
                    "技术路线",
                    "采用的研究方法/实验方案、关键技术",
                    "任务完成情况（与计划对比）",
                    "阶段性成果",
                    "遇到的问题及解决方案",
                    "调整与变更记录",
                    "研究成果（论文、专利、软件著作权等）",
                    "成果应用情况、经济效益/社会效益",
                    "数据统计（实验数据、调研样本量等）",
                    "总经费",
                    "经费来源",
                    "实际支出明细",
                    "预算执行情况",
                    "经费结余说明",
                    "主要结论",
                    "创新点总结",
                    "后续研究建议",
                    "应用推广计划"
                ],
                "负责人（姓名、单位、联系方式）": [],
                "参与人员": []
            }
        elif file_category == '成果附件':
            entitys_attributes = {
                "成果名称": [
                    "转化结果",
                    "成果来源",
                    "转化说明",
                    "成果登记编号",
                    "成果分类",
                    "完成单位排序",
                    "备案编号",
                    "转化方式",
                    "审批文件",
                    "指标项",
                    "具体数值（近3年累计）",
                    "证明材料类型",
                    "行业带动效应",
                    "技术标准贡献",
                    "类型",
                    "编号",
                    "授权日期",
                    "法律状态",
                    "科技成果评价结论",
                    "行业奖项",
                    "检测报告",
                    "报告编号",
                    "用户使用报告",
                    "销售收入",
                    "利润",
                    "税收",
                    "新增利润",
                    "税务台账",
                    "完税证明",
                    "销售合同",
                    "专利授权号",
                    "软著授权号",
                    "创新创业大赛奖项",
                    "国家级/省部级科技奖"
                ],
                "项目负责人": [
                    "合作方核心条款",
                    "转化团队权责",
                    "阶段目标",
                    "资源需求"
                ],
                "负责技术落地指导": []
            }
        elif file_category == '发票':
            entitys_attributes = {
                "发票类型": [
                    "发票代码",
                    "发票号码",
                    "开票日期",
                    "发票状态",
                    "价税合计（总金额）",
                    "备注栏（如项目编号；合同号；付款方式）"
                ],
                "购买方（名称、纳税人识别号、地址电话、开户行及账号）": [],
                "销售方（名称、纳税人识别号、地址电话、开户行及账号）": [],
                "项目名称（商品或服务名称）": [
                    "规格型号",
                    "单位",
                    "数量",
                    "单价",
                    "金额（不含税）",
                    "税率",
                    "税额"
                ],
                "开票人": [],
                "复核人": [],
                "收款人": []
            }
        elif file_category == '调研记录':
            entitys_attributes = {
                "调研主题": [
                    "结论",
                    "调研目的",
                    "调研周期（起止时间）",
                    "调研对象（群体特征、样本量、选取方式）",
                    "调研方法（问卷调查、深度访谈、实地观察、文献研究等）",
                    "调研工具（问卷编号、访谈提纲版本、数据分析软件）",
                    "抽样方法（随机抽样/分层抽样）",
                    "样本分布（性别/年龄/地域等）",
                    "核心问题（调研问卷/访谈的关键问题）",
                    "统计结果（百分比、均值、频数等量化数据）",
                    "典型观点（受访者引言、开放式问题答案摘要）",
                    "关键发现（趋势、规律、异常数据）",
                    "主要结论（与调研目的对应）",
                    "问题归因分析",
                    "对策建议（具体措施、优先级、责任主体）",
                    "调研局限性说明",
                    "建议"
                ],
                "执行单位/团队": [],
                "负责人": [],
                "参与调研人员": []
            }
        elif file_category == '论证记录':
            entitys_attributes = {
                "论证事项": [
                    "结论",
                    "论证主题/议题名称",
                    "记录编号",
                    "论证时间（起始/结束时间）",
                    "地点（线下地址/线上会议链接）",
                    "论证依据（政策文件、数据报告、专家意见等）",
                    "讨论议题（分点列出）",
                    "各方观点摘要",
                    "关键论据（数据、案例、理论支撑）",
                    "表决结果（同意/反对/弃权票数）",
                    "最终结论",
                    "主要共识",
                    "分歧点说明",
                    "建议方案（具体措施、责任分工）",
                    "议程环节（如汇报、提问、讨论、表决）",
                    "时间节点（各环节起止时间）",
                    "争议问题及处理方式"
                ],
                "主持人": [],
                "记录人": [],
                "参与人员（姓名、单位、职务）": [
                    "参与人员（姓名、单位、职务）"
                ]
            }

        #key包括实体和属性，筛选一下
        for key,value in result_dict.items():
            if key in entitys_attributes and value != None and value != "" and value != "null":
                #实体
                edges.append({"source": file_category, "target": build_entity_id(key, value, result_dict), "relation": key})
        
        for entity, attributes in entitys_attributes.items():
            if entity in result_dict:
                entity_value = result_dict[entity]
                tmp_attributes = {}

                for attr in attributes:
                    if attr in result_dict:
                        attr_value = result_dict[attr]
                        if attr_value != None and attr_value != "" and attr_value != "null":
                            tmp_attributes[attr] = attr_value
                if len(tmp_attributes) > 0:
                    print("实体：", entity_value)
                    print("属性：", tmp_attributes)
                    if entity_value != None and entity_value != "" and entity_value != "null":
                        nodes_attr.append({"object": build_entity_id(entity, entity_value, result_dict), "attribute": tmp_attributes, "group": get_entity_group(entity)})
                    else:
                        nodes_attr.append({"object": file_category, "attribute": tmp_attributes, "group": 4})
                
        return edges, nodes_attr

    elif file_category in really_key_file:
        print("file_category:", file_category)
        if file_category == "研发项目汇总表":
            entitys_attributes = {
                "项目名称": [
                    "序号", "项目起止时间", "项目主要研究内容", "研发关键技术",
                    "预期目标", "总预算费用", "可加计扣除研发费用"
                ],
                "项目单位": [],
                "项目负责人": []
            }
        elif file_category == "研发人员名单":
            entitys_attributes = {
                "姓名": [
                    "性别",
                    "年龄",
                    "出生日期",
                    "联系电话",
                    "邮箱地址",
                    "籍贯 / 户籍所在地",
                    "职位（如：算法工程师、高级开发、技术负责人）",
                    "工号",
                    "入职日期",
                    "职级 / 级别（如：P6、T3、资深专家）",
                    "直属上级",
                    "技术方向（如：机器学习、区块链、云计算）",
                    "核心技能（如：Python、TensorFlow、微服务架构）",
                    "教育背景（学历 + 专业，如：计算机科学硕士）",
                    "项目经验（简述或关联项目 ID）",
                    "证书 / 资质（如：AWS 认证、PMP）",
                    "合同类型（全职 / 兼职 / 实习）",
                    "工作地点",
                    "紧急联系人",
                    "薪资等级（部分企业内部使用）"
                ],
                "部门（如：AI 研发部、前端团队、数据中心）": []
            }
        elif file_category == "研发支出辅助帐汇总表":
            entitys_attributes = {
                "项目名称": [
                    "项目编号",
                    "完成情况",
                    "支出类型",
                    "允许加计扣除金额合计",
                    "人员人工费用",
                    "直接投入费用",
                    "折旧费用",
                    "无形资产摊销",
                    "新产品设计费等",
                    "前五项 小计",
                    "其他相关费用合计",
                    "经限额调整后的其他相关费用",
                    "委托境内机构或个人进行研发活动所发生的费用",
                    "允许加计扣除的委托境内机构或个人进行研发活动所发生的费用",
                    "委托境外机构进行研发活动所发生的费用",
                    "经限额调整后的委托境外机构进行研发活动所发生的费用",
                    "资本化金额小计",
                    "费用化金额小计",
                    "其中：其他事项",
                    "金额合计"
                ],
                "法定代表人（签章）：": []
            }
        elif file_category == '企业研发项目情况表':
            entitys_attributes = {
                "项目名称": [
                    "表　　号：",
                    "统一社会信用代码",
                    "尚未领取统一社会信用代码的填原组织机构代码□□□□□□□□－□",
                    "制表机关：",
                    "文　　号：",
                    "单位详细名称：",
                    "有效期至：",
                    "序号",
                    "项目来源",
                    "项目开展形式",
                    "项目当年成果形式",
                    "项目技术经济目标",
                    "项目起始日期",
                    "项目完成日期",
                    "跨年项目当年所处主要进展阶段",
                    "项目研究开发人员（人）",
                    "项目人员实际工作时间（人月）",
                    "项目经费支出（千元）",
                    "其中：政府资金",
                    "*其中：用于科学原理的探索发现",
                    "*其中：企业自主开展",
                    "*其中：委托外单位开展",
                    "合计金额"
                ]
            }

        #key包括实体和属性，筛选一下
        main_key = None
        main_value = None
        if "项目名称" in result_dict and result_dict["项目名称"] not in [None, "", "null"]:
            main_key = "项目名称"
            main_value = build_entity_id(main_key, result_dict["项目名称"], result_dict)
        elif "姓名" in result_dict and result_dict["姓名"] not in [None, "", "null"]:
            main_key = "姓名"
            main_value = build_entity_id(main_key, result_dict["姓名"], result_dict)

        if main_key and main_value:
            # 主键链接到file_category
            edges.append({"source": file_category, "target": main_value, "relation": main_key})
            # 其他实体链接到主键
            for key, value in result_dict.items():
                if key != main_key and key in entitys_attributes and value not in [None, "", "null"]:
                    edges.append({"source": main_value, "target": build_entity_id(key, value, result_dict), "relation": key})
        else:
            for key,value in result_dict.items():
                if key in entitys_attributes and value != None and value != "" and value != "null":
                    #实体
                    edges.append({"source": file_category, "target": build_entity_id(key, value, result_dict), "relation": key})
        
        for entity, attributes in entitys_attributes.items():
            if entity in result_dict:
                entity_value = result_dict[entity]
                tmp_attributes = {}

                for attr in attributes:
                    if attr in result_dict:
                        attr_value = result_dict[attr]
                        if attr_value != None and attr_value != "" and attr_value != "null":
                            tmp_attributes[attr] = attr_value
                if len(tmp_attributes) > 0:
                    print("实体：", entity_value)
                    print("属性：", tmp_attributes)
                    if entity_value != None and entity_value != "" and entity_value != "null":
                        nodes_attr.append({"object": build_entity_id(entity, entity_value, result_dict), "attribute": tmp_attributes, "group": get_entity_group(entity)})
                    else:
                        nodes_attr.append({"object": file_category, "attribute": tmp_attributes, "group": 4})
                
        return edges, nodes_attr         
    

def get_prompt_2(prmot_txt_path: str, document_text: str) -> str:
    with open(prmot_txt_path, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    prompt_template = prompt_template + "\n\n现在请开始处理以下文件内容：\n{document_text}"

    prompt = prompt_template.replace("{document_text}", document_text)
    return prompt

def save_graph(output_file_path, file_path, file_category, edges, nodes_attr):
    # Load existing data or initialize new structure
    data = {"nodes": [], "links": []}
    if os.path.exists(output_file_path):
        try:
            with open(output_file_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and "nodes" in loaded and "links" in loaded:
                    data = loaded
                elif isinstance(loaded, list):
                    # Migration logic: Convert old list format to new format
                    for item in loaded:
                        f_path = item.get("file_path", "")
                        f_cat = item.get("file_category", "")
                        for n in item.get("nodes_attr", []):
                            node = {
                                "id": n.get("object"),
                                "group": n.get("group", 1),
                                "attrs": n.get("attribute", {}),
                                "file_path": f_path,
                                "file_category": f_cat
                            }
                            if "type" in n:
                                node["type"] = n["type"]
                            if "table_html" in n:
                                node["table_html"] = n["table_html"]
                            data["nodes"].append(node)
                        for e in item.get("edges", []):
                            data["links"].append({
                                "source": e.get("source"),
                                "target": e.get("target"),
                                "relation": e.get("relation"),
                                "file_path": f_path,
                                "file_category": f_cat
                            })
        except Exception as e:
            print(f"Error loading existing graph: {e}")
            data = {"nodes": [], "links": []}
    
    # Remove existing entries for the current file to support updates
    file_name = os.path.basename(file_path)
    data["nodes"] = [n for n in data["nodes"] if n.get("file_path") != file_name]
    data["links"] = [l for l in data["links"] if l.get("file_path") != file_name]

    # Persist the uploaded file/category itself as a node so link endpoints
    # always have a concrete node record in the stored graph.
    if file_category == OTHER_CATEGORY:
        file_node_id = file_name
    else:
        file_node_id = file_category or file_name
    file_node_attrs = {
        "文件名": file_name,
        "文件类别": file_category
    }
    file_node_found = False
    for n in nodes_attr:
        if n.get("object") == file_node_id:
            merged_attrs = dict(file_node_attrs)
            existing_attrs = n.get("attribute")
            if isinstance(existing_attrs, dict):
                merged_attrs.update(existing_attrs)
            n["attribute"] = merged_attrs
            if "group" not in n or n.get("group") is None:
                n["group"] = 4
            file_node_found = True
            break
    if not file_node_found:
        nodes_attr.append({
            "object": file_node_id,
            "attribute": file_node_attrs,
            "group": 4
        })

    # Ensure every edge endpoint has a concrete node record, even when the
    # entity has no extracted attributes.
    existing_node_ids = {
        n.get("object")
        for n in nodes_attr
        if isinstance(n, dict) and n.get("object") not in [None, ""]
    }
    for edge in edges:
        for endpoint_key in ("source", "target"):
            endpoint = edge.get(endpoint_key)
            if endpoint in [None, ""] or endpoint in existing_node_ids:
                continue
            inferred_group = get_entity_group(edge.get("relation")) if endpoint_key == "target" else 4
            nodes_attr.append({
                "object": endpoint,
                "attribute": {},
                "group": inferred_group
            })
            existing_node_ids.add(endpoint)
    
    # Add new entries
    for n in nodes_attr:
        node = {
            "id": n.get("object"),
            "group": n.get("group", 1),
            "attrs": n.get("attribute", {}),
            "file_path": file_name,
            "file_category": file_category
        }
        if "type" in n:
            node["type"] = n["type"]
        if "table_html" in n:
            node["table_html"] = n["table_html"]
        data["nodes"].append(node)
    
    for e in edges:
        data["links"].append({
            "source": e.get("source"),
            "target": e.get("target"),
            "relation": e.get("relation"),
            "file_path": file_name,
            "file_category": file_category
        })
        
    # Save back to file
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"Graph data saved to {output_file_path}")

def read_excel_with_merged_cells(source):
    workbook_source = source
    if Path(source).suffix.lower() in LEGACY_XLS_EXTENSIONS:
        workbook_source = convert_legacy_xls_to_xlsx(source)

    workbook = load_workbook(workbook_source, data_only=True)
    worksheet = workbook.worksheets[0]
    for merged_range in list(worksheet.merged_cells.ranges):
        min_col, min_row, max_col, max_row = merged_range.bounds
        merged_value = worksheet.cell(row=min_row, column=min_col).value
        worksheet.unmerge_cells(str(merged_range))
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                worksheet.cell(row=row, column=col, value=merged_value)

    rows = list(worksheet.values)
    if not rows:
        return pd.DataFrame()
    header = ["" if item is None else str(item) for item in rows[0]]
    data = rows[1:]
    return pd.DataFrame(data, columns=header)


def read_csv_with_fallback(source):
    encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk"]
    last_error = None
    for encoding in encodings:
        try:
            return pd.read_csv(source, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return pd.read_csv(source)


def read_tabular_file(source):
    suffix = Path(source).suffix.lower()
    if suffix in SPREADSHEET_EXTENSIONS:
        return read_excel_with_merged_cells(source)
    if suffix == ".csv":
        return read_csv_with_fallback(source)
    raise ValueError(f"不支持的表格文件格式: {suffix}")


def normalize_category_for_source(file_category, source_suffix):
    if file_category in xlsx_file and source_suffix not in TABULAR_EXTENSIONS:
        print(
            f"文件被分类为表格类 {file_category}，但源文件扩展名为 "
            f"{source_suffix or '[none]'}，按 {OTHER_CATEGORY} 处理"
        )
        return OTHER_CATEGORY
    return file_category

parser = argparse.ArgumentParser(description="Get Graph")
parser.add_argument('--input_file_path', type=str, required=True, help='Input file path')
parser.add_argument('--output_file_path', type=str, required=True, help='Output file path')
parser.add_argument('--api_base', type=str, default='http://127.0.0.1:62272/v1', help='Model name to use')
parser.add_argument('--model_path', type=str, default='Qwen3.5-27B', help='Model path')
parser.add_argument('--prompt_txt_path', type=str, default='', help='File category')
args = parser.parse_args()

# Set OpenAI's API key and API base to use vLLM's API server.
openai_api_key = "EMPTY"
openai_api_base = os.getenv("GETGRAPH_API_BASE") or args.api_base
if openai_api_base.rstrip("/") in {"http://10.249.40.204:62272/v1"}:
    openai_api_base = "http://127.0.0.1:62272/v1"
existing_no_proxy = os.getenv("NO_PROXY") or os.getenv("no_proxy") or ""
no_proxy_items = [item.strip() for item in existing_no_proxy.split(",") if item.strip()]
for item in ("127.0.0.1", "localhost", "10.249.40.204"):
    if item not in no_proxy_items:
        no_proxy_items.append(item)
os.environ["NO_PROXY"] = ",".join(no_proxy_items)
os.environ["no_proxy"] = os.environ["NO_PROXY"]

client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
    timeout=float(os.getenv("GETGRAPH_LLM_TIMEOUT", "120")),
)

DISABLE_THINKING_EXTRA_BODY = {"chat_template_kwargs": {"enable_thinking": False}}


def create_chat_completion(**kwargs):
    retry_count = int(os.getenv("GETGRAPH_LLM_RETRIES", "3"))
    retry_sleep = float(os.getenv("GETGRAPH_LLM_RETRY_SLEEP_SECONDS", "2"))
    retryable_status = {429, 500, 502, 503, 504}
    last_exc = None

    for attempt in range(1, retry_count + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            last_exc = exc
            status_code = getattr(exc, "status_code", None)
            is_retryable = status_code in retryable_status or "Error code: 502" in str(exc)
            if not is_retryable or attempt >= retry_count:
                raise
            print(f"LLM 调用失败，准备重试 {attempt}/{retry_count}: {exc}")
            time.sleep(retry_sleep * attempt)

    raise last_exc

source = args.input_file_path  # document per local path or URL
result = convert_source(source)
document_text = result.document.export_to_markdown()


file_category = get_file_category(document_text, os.path.basename(source))

source_suffix = Path(source).suffix.lower()
file_category = normalize_category_for_source(file_category, source_suffix)

if file_category == OTHER_CATEGORY:
    nodes_attr = [{
        "object": os.path.basename(source),
        "attribute": {},
        "group": 4,
        "type": OTHER_CATEGORY
    }]
    save_graph(args.output_file_path, args.input_file_path, file_category, [], nodes_attr)
    exit(0)

if file_category in xlsx_file and source_suffix in TABULAR_EXTENSIONS:
    mock_df = read_tabular_file(source)
    table_html_str = mock_df.to_html(index=False, classes="excel-table", border=0)

    edges, nodes_attr = get_entity_attr(file_category, table_html_str)

    save_graph(args.output_file_path, args.input_file_path, file_category, edges, nodes_attr)

    #退出程序
    exit(0)


prompt = get_prompt_2(args.prompt_txt_path + "/"+ file_category +"关键信息提取规则.txt", document_text)

chat_response = create_chat_completion(
    model=args.model_path,
    messages=[
        {"role": "system", "content": "你是一个专业的信息提取助手"},
        {"role": "user", "content": prompt},
    ],
    temperature=0,
    max_tokens=int(os.getenv("GETGRAPH_EXTRACTION_MAX_TOKENS", "4096")),
    response_format={"type": "json_object"},
    extra_body=DISABLE_THINKING_EXTRA_BODY,
)

response_text = chat_response.choices[0].message.content

print("模型返回结果：")
print(response_text)

raw_text = response_text.strip()
json_str = extract_json_candidate(raw_text)

result_dict = json.loads(json_str)
result_dict = unwrap_result_dict(result_dict)
if file_category == '发票':
    result_dict = normalize_invoice_result(result_dict)

# 如果是一个dict，且里面包含list，则认为是多条数据，需要转换为list
if isinstance(result_dict, dict):
    is_list = False
    for key, value in result_dict.items():
        if isinstance(value, list):
            is_list = True
            break
    
    if is_list:
        new_result_list = []
        max_len = 0
        for key, value in result_dict.items():
            if isinstance(value, list):
                if len(value) > max_len:
                    max_len = len(value)
        
        for i in range(max_len):
            item = {}
            for key, value in result_dict.items():
                if isinstance(value, list):
                    if i < len(value):
                        item[key] = value[i]
                    else:
                        item[key] = ""
                else:
                    item[key] = value
            new_result_list.append(item)
        result_dict = new_result_list

#如果返回的不是一个list，对每个dict都进行处理
if not isinstance(result_dict, list):
    edges, nodes_attr = get_entity_attr(file_category, result_dict)

    print("抽取的实体关系：")
    for edge in edges:
        print(edge)

    print("抽取的实体属性：")
    print(nodes_attr)


    save_graph(args.output_file_path, args.input_file_path, file_category, edges, nodes_attr)
#如果是一个list，则list中每个dict都进行处理，但在存储时不去重了
else:
    print("result_dict:", result_dict)
    all_edges = []
    all_nodes_attr = []
    for item in result_dict:
        edges, nodes_attr = get_entity_attr(file_category, item)

        print("抽取的实体关系：")
        for edge in edges:
            print(edge)
        all_edges.extend(edges)

        print("抽取的实体属性：")
        print(nodes_attr)
        all_nodes_attr.extend(nodes_attr)

    save_graph(args.output_file_path, args.input_file_path, file_category, all_edges, all_nodes_attr)
