import os
from flask import Flask, render_template, request, jsonify
import subprocess
from pathlib import Path
import json

output_path = "/data1/liwu/xintuoyin-merged/runtime/external_workspace/output_graph.json"
app = Flask(__name__)

UPLOAD_FOLDER = os.path.join('/data1/liwu/xintuoyin-merged/runtime/external_workspace', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def normalize_graph(data):
    if isinstance(data, dict) and "nodes" in data and "links" in data:
        nodes = data.get("nodes", [])
        links = data.get("links", [])
    elif isinstance(data, list):
        edges = []
        nodes_attr = []
        for item in data:
            edges.extend(item.get("edges", []))
            nodes_attr.extend(item.get("nodes_attr", []))
        nodes = []
        links = []
        for n in nodes_attr:
            node = {
                "id": n.get("object"),
                "group": 1,
                "attrs": n.get("attribute", {})
            }
            for k, v in n.items():
                if k not in {"object", "attribute"}:
                    node[k] = v
            nodes.append(node)
        for e in edges:
            link = {
                "source": e.get("source"),
                "target": e.get("target"),
                "relation": e.get("relation")
            }
            for k, v in e.items():
                if k not in {"source", "target", "relation"}:
                    link[k] = v
            links.append(link)
    else:
        nodes = []
        links = []
    return deduplicate_graph({"nodes": nodes, "links": links})


def deduplicate_graph(graph):
    node_map = {}
    for node in graph.get("nodes", []):
        node_id = node.get("id")
        if not node_id:
            continue
        normalized = dict(node)
        if "attrs" not in normalized or not isinstance(normalized.get("attrs"), dict):
            normalized["attrs"] = {}
        if node_id not in node_map:
            node_map[node_id] = normalized
        else:
            if isinstance(normalized.get("attrs"), dict):
                node_map[node_id]["attrs"].update(normalized["attrs"])
            for k, v in normalized.items():
                if k == "attrs":
                    continue
                if v is not None:
                    node_map[node_id][k] = v

    link_map = {}
    for link in graph.get("links", []):
        source = link.get("source")
        target = link.get("target")
        relation = link.get("relation")
        if not source or not target or relation is None:
            continue
        key = f"{source}|||{target}|||{relation}"
        normalized = dict(link)
        if key not in link_map:
            link_map[key] = normalized
        else:
            for k, v in normalized.items():
                if v is not None:
                    link_map[key][k] = v

    return {"nodes": list(node_map.values()), "links": list(link_map.values())}


def read_graph():
    file = Path(output_path)
    if not file.exists():
        return {"nodes": [], "links": []}
    try:
        with file.open('r', encoding='utf-8') as f:
            data = json.load(f)
        return normalize_graph(data)
    except Exception as e:
        print(f"Error reading graph: {e}")
        return {"nodes": [], "links": []}


def save_graph(graph):
    normalized = deduplicate_graph(graph)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(normalized, f, ensure_ascii=False, indent=4)
    return normalized


def merge_graph(base_graph, incoming_graph):
    merged = {
        "nodes": list(base_graph.get("nodes", [])) + list(incoming_graph.get("nodes", [])),
        "links": list(base_graph.get("links", [])) + list(incoming_graph.get("links", []))
    }
    return deduplicate_graph(merged)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "未接收到文件"}), 400
    
    files = request.files.getlist('file')
    saved_files = []
    preprocess_results = []
    
    # 记录当前已有的图谱作为基础
    current_graph = read_graph()

    for file in files:
        if file.filename:
            # 保持中文文件名
            path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(path)
            saved_files.append(file.filename)
            
            # 为了防止多个文件互相覆盖输出结果，可以使用临时文件，或者依然用原来的路径但每次处理完就合并
            # 这里我们使用一个临时输出路径来存放单个文件提取的结果
            temp_output_path = f"/data1/liwu/xintuoyin/getgraph/graph_data/temp_output_{file.filename}.json"
            
            cmd = [
                "python",
                "/data1/liwu/xintuoyin/getgraph/main.py",
                "--input_file_path", path,
                "--output_file_path", temp_output_path,
                "--api_base", "http://localhost:8000/v1",
                "--model_path", "/data1/public/models/Qwen2.5-32B-Instruct",
                "--prompt_txt_path", "/data1/liwu/xintuoyin/getgraph/prompt",
            ]
            print("执行预处理命令:", " ".join(cmd))
            try:
                completed = subprocess.run(
                    cmd, check=True, capture_output=True, text=True
                )
                print(f"[{file.filename}] 预处理完成，输出结果保存在:", temp_output_path)
                
                # 读取新提取出的单文件图谱并合并到 current_graph
                temp_file = Path(temp_output_path)
                if temp_file.exists():
                    try:
                        with temp_file.open('r', encoding='utf-8') as f:
                            incoming_data = json.load(f)
                        incoming_graph = normalize_graph(incoming_data)
                        current_graph = merge_graph(current_graph, incoming_graph)
                        # 删除临时文件
                        os.remove(temp_output_path)
                    except Exception as e:
                        print(f"合并提取结果失败 [{file.filename}]: {e}")
                
                preprocess_results.append({
                    "file": file.filename,
                    "status": "ok",
                    "stdout": completed.stdout,
                    "stderr": completed.stderr
                })
            except subprocess.CalledProcessError as e:
                print(f"[{file.filename}] 预处理出错:", e.stderr)
                preprocess_results.append({
                    "file": file.filename,
                    "status": "failed",
                    "stdout": e.stdout,
                    "stderr": e.stderr
                })           

    # 所有文件处理并合并完成后，一次性保存最终图谱
    save_graph(current_graph)
    
    return jsonify({
        "status": "success",
        "message": f"成功处理并合并了 {len(saved_files)} 个文件",
        "files": saved_files,
        "results": preprocess_results
    })

@app.route('/get_graph')
def get_graph():
    return jsonify(read_graph())


@app.route('/graph/node', methods=['POST'])
def create_node():
    payload = request.get_json(silent=True) or {}
    node_id = payload.get("id")
    if not node_id:
        return jsonify({"error": "节点 id 不能为空"}), 400

    graph = read_graph()
    if any(n.get("id") == node_id for n in graph["nodes"]):
        return jsonify({"error": f"节点 {node_id} 已存在"}), 409

    node = dict(payload)
    if "attrs" not in node or not isinstance(node.get("attrs"), dict):
        node["attrs"] = {}
    graph["nodes"].append(node)
    graph = save_graph(graph)
    return jsonify({"status": "success", "node": node, "graph": graph})


@app.route('/graph/node/<path:node_id>', methods=['PUT'])
def update_node(node_id):
    payload = request.get_json(silent=True) or {}
    graph = read_graph()
    target = None
    for node in graph["nodes"]:
        if node.get("id") == node_id:
            target = node
            break
    if target is None:
        return jsonify({"error": f"节点 {node_id} 不存在"}), 404

    new_id = payload.get("id", node_id)
    if new_id != node_id and any(n.get("id") == new_id for n in graph["nodes"]):
        return jsonify({"error": f"节点 {new_id} 已存在"}), 409

    merged_attrs = dict(target.get("attrs", {}))
    incoming_attrs = payload.get("attrs")
    if isinstance(incoming_attrs, dict):
        merged_attrs.update(incoming_attrs)

    for k, v in payload.items():
        if k == "attrs":
            continue
        target[k] = v
    target["id"] = new_id
    target["attrs"] = merged_attrs

    if new_id != node_id:
        for link in graph["links"]:
            if link.get("source") == node_id:
                link["source"] = new_id
            if link.get("target") == node_id:
                link["target"] = new_id

    graph = save_graph(graph)
    return jsonify({"status": "success", "node": target, "graph": graph})


@app.route('/graph/node/<path:node_id>', methods=['DELETE'])
def delete_node(node_id):
    graph = read_graph()
    before_node_count = len(graph["nodes"])
    graph["nodes"] = [n for n in graph["nodes"] if n.get("id") != node_id]
    if len(graph["nodes"]) == before_node_count:
        return jsonify({"error": f"节点 {node_id} 不存在"}), 404
    graph["links"] = [
        l for l in graph["links"]
        if l.get("source") != node_id and l.get("target") != node_id
    ]
    graph = save_graph(graph)
    return jsonify({"status": "success", "deleted_node": node_id, "graph": graph})


@app.route('/graph/link', methods=['POST'])
def create_link():
    payload = request.get_json(silent=True) or {}
    source = payload.get("source")
    target = payload.get("target")
    relation = payload.get("relation")
    if not source or not target or relation is None:
        return jsonify({"error": "source、target、relation 不能为空"}), 400

    graph = read_graph()
    exists = any(
        l.get("source") == source and l.get("target") == target and l.get("relation") == relation
        for l in graph["links"]
    )
    if exists:
        return jsonify({"error": "该关系已存在"}), 409

    existing_node_ids = {n.get("id") for n in graph["nodes"]}
    if source not in existing_node_ids:
        graph["nodes"].append({"id": source, "group": 1, "attrs": {}})
    if target not in existing_node_ids:
        graph["nodes"].append({"id": target, "group": 1, "attrs": {}})

    link = dict(payload)
    graph["links"].append(link)
    graph = save_graph(graph)
    return jsonify({"status": "success", "link": link, "graph": graph})


@app.route('/graph/link', methods=['PUT'])
def update_link():
    payload = request.get_json(silent=True) or {}
    old_source = payload.get("old_source")
    old_target = payload.get("old_target")
    old_relation = payload.get("old_relation")
    if not old_source or not old_target or old_relation is None:
        return jsonify({"error": "old_source、old_target、old_relation 不能为空"}), 400

    graph = read_graph()
    target_link = None
    for link in graph["links"]:
        if (
            link.get("source") == old_source and
            link.get("target") == old_target and
            link.get("relation") == old_relation
        ):
            target_link = link
            break
    if target_link is None:
        return jsonify({"error": "待修改关系不存在"}), 404

    for field in ("source", "target", "relation"):
        if field in payload:
            target_link[field] = payload[field]
    for k, v in payload.items():
        if k not in {"old_source", "old_target", "old_relation", "source", "target", "relation"}:
            target_link[k] = v

    source = target_link.get("source")
    target = target_link.get("target")
    relation = target_link.get("relation")
    if not source or not target or relation is None:
        return jsonify({"error": "更新后 source、target、relation 不能为空"}), 400

    existing_node_ids = {n.get("id") for n in graph["nodes"]}
    if source not in existing_node_ids:
        graph["nodes"].append({"id": source, "group": 1, "attrs": {}})
    if target not in existing_node_ids:
        graph["nodes"].append({"id": target, "group": 1, "attrs": {}})

    graph = save_graph(graph)
    return jsonify({"status": "success", "link": target_link, "graph": graph})


@app.route('/graph/link', methods=['DELETE'])
def delete_link():
    payload = request.get_json(silent=True) or {}
    source = payload.get("source")
    target = payload.get("target")
    relation = payload.get("relation")
    if not source or not target or relation is None:
        return jsonify({"error": "source、target、relation 不能为空"}), 400

    graph = read_graph()
    original_count = len(graph["links"])
    graph["links"] = [
        l for l in graph["links"]
        if not (l.get("source") == source and l.get("target") == target and l.get("relation") == relation)
    ]
    if len(graph["links"]) == original_count:
        return jsonify({"error": "待删除关系不存在"}), 404
    graph = save_graph(graph)
    return jsonify({"status": "success", "deleted_link": {"source": source, "target": target, "relation": relation}, "graph": graph})


@app.route('/graph/merge', methods=['POST'])
def merge_graph_api():
    payload = request.get_json(silent=True) or {}
    incoming_data = payload.get("graph")
    merge_file_path = payload.get("file_path")

    if incoming_data is None and not merge_file_path:
        return jsonify({"error": "请提供 graph 或 file_path"}), 400

    if incoming_data is None and merge_file_path:
        file = Path(merge_file_path)
        if not file.exists():
            return jsonify({"error": f"文件不存在: {merge_file_path}"}), 400
        try:
            with file.open('r', encoding='utf-8') as f:
                incoming_data = json.load(f)
        except Exception as e:
            return jsonify({"error": f"读取待合并文件失败: {e}"}), 400

    current = read_graph()
    incoming = normalize_graph(incoming_data)
    merged = merge_graph(current, incoming)
    merged = save_graph(merged)

    return jsonify({
        "status": "success",
        "base_node_count": len(current.get("nodes", [])),
        "base_link_count": len(current.get("links", [])),
        "incoming_node_count": len(incoming.get("nodes", [])),
        "incoming_link_count": len(incoming.get("links", [])),
        "merged_node_count": len(merged.get("nodes", [])),
        "merged_link_count": len(merged.get("links", [])),
        "graph": merged
    })


@app.route('/graph/clear', methods=['POST'])
def clear_graph_api():
    cleared = save_graph({"nodes": [], "links": []})
    return jsonify({
        "status": "success",
        "message": "图谱已清空",
        "graph": cleared
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
