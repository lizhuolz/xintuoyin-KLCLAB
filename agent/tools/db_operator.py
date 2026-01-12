import ast
import operator as op
from typing import Any, Dict
from langchain_core.tools import tool
@tool
def sql_tool(sql: str,param:str) -> str:
    """执行SQL查询。{SQL:sql查询代码,Param:sql查询参数 }"""
    if "V0" in sql:
        if  "energy" in sql or "power" in  sql:
            return "{'rowcount': 1,'fields': ['total_amount_11'],'data': [{'total_amount_11': Decimal('860.00000')}]}"    
        elif "invoice" in sql:
            return "{'rowcount': 1, 'fields': ['invoice_count', 'total_amount'], 'data': [{'invoice_count': 1, 'total_amount': Decimal('2100.00000')}]}"
        elif "special" in sql:
            return "{'rowcount': 1,'fields': ['total_special_income'],'data': [{'total_special_income': Decimal('36000.00000')}]}"
    
    elif "V1" in sql:
        if  "energy" in sql or "power" in  sql:
            return "{'rowcount': 1,'fields': ['total_amount_11'],'data': [{'total_amount_11': Decimal('861.00000')}]}"    
        elif "invoice" in sql:
            return "{'rowcount': 1, 'fields': ['invoice_count', 'total_amount'], 'data': [{'invoice_count': 1, 'total_amount': Decimal('2101.00000')}]}"
        elif "special" in sql:
            return "{'rowcount': 1,'fields': ['total_special_income'],'data': [{'total_special_income': Decimal('36001.00000')}]}"
    
        
    
    return "这是sql 查询demo，返回测试"