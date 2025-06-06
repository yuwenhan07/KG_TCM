from flask import Flask, request, render_template
from neo4j import GraphDatabase
from pyvis.network import Network
import os
import subprocess
import json
import markdown
from markupsafe import Markup

# Initialize Flask app
app = Flask(__name__)

# Register markdown filter for rendering markdown in templates
@app.template_filter('markdown')
def markdown_filter(text):
    return Markup(markdown.markdown(text))

# Neo4j database connection
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "1qaz2wsx"))

# Query Neo4j and build a graph
def build_graph(symptom):
    with driver.session() as session:
        # query = """
        #     MATCH (fj:方剂)-[:包含]->(fn:方名)-[:功能主治]->(gn:功能主治)
        #     WHERE gn.name CONTAINS $symptom
        #     MATCH (fn)-[:配方]->(cf:处方)-[:中药组成]->(herb:中药名)
        #     RETURN fj, fn, gn, cf, herb
        # """
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

            id_fj = add_node(fj, "方剂")
            id_fn = add_node(fn, "方名")
            id_gn = add_node(gn, "功能主治")
            id_cf = add_node(cf, "处方")
            id_herb = add_node(herb, "中药名")

            add_edge(id_fj, id_fn, "包含")
            add_edge(id_fn, id_gn, "功能主治")
            add_edge(id_fn, id_cf, "配方")
            add_edge(id_cf, id_herb, "中药组成")

        query = """
            MATCH (fj:方剂)-[:包含]->(fn:方名)-[:功能主治]->(gn:功能主治)
            WHERE gn.name CONTAINS $symptom
            MATCH (fn)-[:配方]->(cf:处方)-[r:中药组成]->(herb)
            OPTIONAL MATCH (fn)-[:功能主治]->(hgn:功能主治)
            RETURN fn.name AS formula_name, herb.name AS herb_name, r.weight AS weight, collect(DISTINCT hgn.name) AS herb_gn
        """
        data_result = session.run(query, symptom=symptom)
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
        # 构建大模型回复
        if table_data:
            unique_facts = set()
            for item in table_data:
                line = f"{item['方名']}：{item['中药功能主治'] or '暂无说明'}"
                unique_facts.add(line)
            facts = "\n".join(unique_facts)
            user_question = f"我最近出现了症状：{symptom}，可以用哪些中药治疗？"
            prompt = "请根据以下中药方名和主治功能，给出中药建议：\n"+facts+"\n用户问题："+user_question
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
            model_reply = "未找到相关方剂和中药信息，建议您尝试更通用的症状描述。"
        # print(f"Model reply: {model_reply}")
        return model_reply

# Route to render graph from symptom input
@app.route('/', methods=['GET', 'POST'])
def index():
    graph_path = None
    table_data = None
    model_reply = None
    if request.method == 'POST':
        symptom = request.form.get('symptom')
        if symptom:
            graph_path, table_data= build_graph(symptom)
    return render_template('index_answer.html', graph_path=graph_path, table_data=table_data)

@app.route('/suggest', methods=['POST'])
def suggest():
    symptom = request.form.get('symptom')
    if symptom:
        graph_path, table_data = build_graph(symptom)
        model_reply = suggest_treatment(table_data, symptom)
        return f"<div style='white-space: pre-wrap; line-height: 1.6;'>{markdown_filter(model_reply)}</div>"
    else:
        return "请提供症状描述。", 400

# Start the Flask app
if __name__ == '__main__':
    os.makedirs("static", exist_ok=True)
    app.run(debug=True)