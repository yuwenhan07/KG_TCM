from flask import Flask, request, render_template
from neo4j import GraphDatabase
from pyvis.network import Network
import os
import subprocess
import json
import markdown
from markupsafe import Markup

# 初始化 Flask 应用
app = Flask(__name__)

# 注册 markdown 过滤器以在模板中渲染 markdown 内容
@app.template_filter('markdown')
def markdown_filter(text):
    return Markup(markdown.markdown(text))

# 连接 Neo4j 图数据库
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "1qaz2wsx"))

# 查询 Neo4j 并构建图谱
def build_graph(symptom):
    import re
    match = re.match(r"(.*)和(.*)可以一起服用吗？", symptom.strip())
    with driver.session() as session:
        if match:
            formula1 = match.group(1).strip()
            formula2 = match.group(2).strip()
            query = """
            MATCH (fn:方名)
            WHERE fn.name IN [$formula1, $formula2]
            OPTIONAL MATCH (fn)<-[:包含]-(fj:方剂)
            OPTIONAL MATCH (fn)-[:功能主治]->(gn:功能主治)
            OPTIONAL MATCH (fn)-[:配方]->(cf:处方)-[:中药组成]->(herb:中药名)
            RETURN DISTINCT fj, fn, gn, cf, herb
            """
            result = list(session.run(query, formula1=formula1, formula2=formula2))
        else:
            query = """
            MATCH (fj:方剂)-[:包含]->(fn:方名)-[:功能主治]->(gn:功能主治)
            WHERE gn.name CONTAINS $symptom
            MATCH (fn)-[:配方]->(cf:处方)
            WITH DISTINCT fj, fn, gn, cf
            MATCH (cf)-[:中药组成]->(herb:中药名)
            RETURN fj, fn, gn, cf, herb
            """
            result = list(session.run(query, symptom=symptom))

        if not result:
            return None, []

        net = Network(height='600px', width='100%', directed=True)
        net.set_options('''
            {
            "nodes": {
                "font": {
                "size": 18,
                "bold": true
                }
            },
            "edges": {
                "font": {
                "size": 10
                }
            }
            }
        ''')
        nodes = set()
        edges = set()

        def add_edge(source, target, label):
            edge_key = (source, target, label)
            if edge_key not in edges:
                edges.add(edge_key)
                net.add_edge(source, target, label=label)

        for record in result:
            fj = record['fj']
            fn = record['fn']
            gn = record['gn']
            cf = record['cf']
            herb = record['herb']

            def add_node(obj, label):
                node_id = obj.element_id
                if node_id not in nodes:
                    nodes.add(node_id)
                    color_map = {
                        "方剂": "#C6EB87",
                        "方名": "#87EBC1",
                        "功能主治": "#EE90A1",
                        "处方": "#FFD700",
                        "中药名": "#69B2FF"
                    }
                    net.add_node(
                        node_id,
                        label=obj['name'],
                        title=obj['name'],
                        color=color_map.get(label, "#D3D3D3")
                    )
                return node_id

            if fn:
                id_fn = add_node(fn, "方名")
            if fj:
                id_fj = add_node(fj, "方剂")
                add_edge(id_fj, id_fn, "包含")
            if gn:
                id_gn = add_node(gn, "功能主治")
                add_edge(id_fn, id_gn, "功能主治")
            if cf:
                id_cf = add_node(cf, "处方")
                add_edge(id_fn, id_cf, "配方")
            if herb:
                id_herb = add_node(herb, "中药名")
                add_edge(id_cf, id_herb, "中药组成")

        if match:
            data_result = session.run("""
            MATCH (fn:方名)
            WHERE fn.name IN [$formula1, $formula2]
            MATCH (fn)-[:配方]->(cf:处方)-[r:中药组成]->(herb)
            OPTIONAL MATCH (fn)-[:功能主治]->(hgn:功能主治)
            RETURN fn.name AS formula_name, herb.name AS herb_name, r.weight AS weight, collect(DISTINCT hgn.name) AS herb_gn
            """, formula1=formula1, formula2=formula2)
        else:
            data_result = session.run("""
            MATCH (fj:方剂)-[:包含]->(fn:方名)-[:功能主治]->(gn:功能主治)
            WHERE gn.name CONTAINS $symptom
            MATCH (fn)-[:配方]->(cf:处方)-[r:中药组成]->(herb)
            OPTIONAL MATCH (fn)-[:功能主治]->(hgn:功能主治)
            RETURN fn.name AS formula_name, herb.name AS herb_name, r.weight AS weight, collect(DISTINCT hgn.name) AS herb_gn
            """, symptom=symptom)

        table_data = [{
            "方名": record["formula_name"],
            "中药": record["herb_name"],
            "剂量": record["weight"],
            "中药功能主治": "；".join(record["herb_gn"]) if record["herb_gn"] else ""
        } for record in data_result]

        graph_path = os.path.join("static", "graph.html")
        net.write_html(graph_path)
        return graph_path, table_data

def suggest_treatment(table_data, symptom):
        # 构建大语言模型的回复
        if table_data:
            unique_facts = set()
            for item in table_data:
                line = f"{item['方名']}：{item['中药功能主治'] or '暂无说明'}"
                unique_facts.add(line)
            facts = "\n".join(unique_facts)
            user_question = f"查看这两个中药的名称与主治功能：{symptom}"
            prompt = "请根据以下中药方名和主治功能，回答问题：\n"+facts+"\n用户问题："+user_question
            script_path = "../Script/answer.py"
            try:
                result = subprocess.run(
                    ["python", script_path, prompt],
                    env=dict(os.environ, MKL_THREADING_LAYER="GNU"),
                    capture_output=True,
                    text=True
                )
                model_reply = result.stdout.strip() if result.returncode == 0 else "模型生成失败，请稍后再试。"
            except Exception as e:
                model_reply = f"生成回复出错：{e}"
        else:
            model_reply = "未找到相关方剂和中药信息，建议您尝试更通用的药物名称。"
        # print(f"Model reply: {model_reply}")
        return model_reply

# 路由：根据用户输入的症状渲染图谱
@app.route('/', methods=['GET', 'POST'])
def index():
    graph_path = None
    table_data = None
    model_reply = None
    if request.method == 'POST':
        symptom = request.form.get('symptom')
        if symptom:
            graph_path, table_data= build_graph(symptom)
    return render_template('index_inference.html', graph_path=graph_path, table_data=table_data)

@app.route('/suggest', methods=['POST'])
def suggest():
    symptom = request.form.get('symptom')
    if symptom:
        graph_path, table_data = build_graph(symptom)
        model_reply = suggest_treatment(table_data, symptom)
        return f"<div style='white-space: pre-wrap; line-height: 1.6;'>{markdown_filter(model_reply)}</div>"
    else:
        return "请提供症状描述。", 400

# 启动 Flask 应用
if __name__ == '__main__':
    os.makedirs("static", exist_ok=True)
    app.run(debug=True)