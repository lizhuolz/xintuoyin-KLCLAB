
from ray import nodes


def get_entity_attr(file_category, result_dict):
    edges = [] # {"source": "Transformer", "target": "Attention Mechanism", "relation": "uses"},
    nodes_attr = []

    if file_category == '项目立项报告':

        entitys_attributes = {
            "项目名称": ["日期","项目周期","资金来源","项目阶段","经费预算情况","预期目标","项目创新性","政策/行业依据","问题痛点量化"],
            "参与人员": [],
            "负责人": []
        }

    #key包括实体和属性，筛选一下
    for key,value in result_dict.items():
        if key in entitys_attributes and value != None and value != "":
            #实体
            edges.append({"source": file_category, "target": value, "relation": key})
    
    for entity, attributes in entitys_attributes.items():
        if entity in result_dict:
            entity_value = result_dict[entity]
            for attr in attributes:
                if attr in result_dict:
                    attr_value = result_dict[attr]
                    if attr_value != None and attr_value != "":
                        nodes_attr.append({"entity": entity_value, "attribute": attr, "value": attr_value})
            
            
    # Add more file categories and their processing logic here as needed.

    return edges, nodes_attr