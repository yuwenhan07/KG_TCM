# -*- coding = utf-8 -*-
"""
    author: Wenhan Yu
    time: 2025/5/27

    project name: Knowledge_Graph_Custom
    file name: KG_build.py
    function:
        通用知识图谱构建脚本，支持权重处理
"""

import json
from py2neo import Graph, Node, Relationship


def generateGraph_Node(graph, label, name):
    """
        创建知识图谱节点
    :param graph: Graph()
    :param label: 节点label
    :param name: 节点name
    :return: Node 对象
    """
    node = Node(label, name=name)
    graph.create(node)
    return node


def generateGraph_Relation(graph, node_1, relation, node_2, weight=None):
    """
        连接知识图谱关系，支持可选的权重属性
    :param graph: Graph()
    :param node_1: 头实体节点
    :param relation: 关系类型
    :param node_2: 尾实体节点
    :param weight: 可选的权重
    :return:
    """
    if weight is not None:
        r = Relationship(node_1, relation, node_2, weight=weight)
    else:
        r = Relationship(node_1, relation, node_2)
    graph.create(r)


def create_graph_custom():
    """
        创建通用知识图谱，根据JSON结构构建，支持关系权重
    :return:
    """
    # === 连接Neo4j数据库
    connect_graph = Graph("bolt://localhost:7687", auth=("neo4j", "1qaz2wsx"), name="TCM-2")
    connect_graph.run("MATCH (n) DETACH DELETE n")  # 清空旧图谱

    dict_nodes = {}  # 缓存已创建节点，避免重复创建

    with open("./data/TCM.json", "r", encoding="utf-8") as fr:
        data = json.load(fr)
        for ele in data:
            node_1 = ele["node_1"]
            relation = ele["relation"]
            node_2 = ele["node_2"]
            weight = ele.get("weight")  # 可选字段

            # 解析 label 和 name
            label1, name1 = node_1.split("\t")
            label2, name2 = node_2.split("\t")

            # 获取或创建节点1
            if node_1 not in dict_nodes:
                node_1_g = generateGraph_Node(connect_graph, label1, name1)
                dict_nodes[node_1] = node_1_g
            else:
                node_1_g = dict_nodes[node_1]

            # 获取或创建节点2
            if node_2 not in dict_nodes:
                node_2_g = generateGraph_Node(connect_graph, label2, name2)
                dict_nodes[node_2] = node_2_g
            else:
                node_2_g = dict_nodes[node_2]

            # 创建关系（带权重）
            generateGraph_Relation(connect_graph, node_1_g, relation, node_2_g, weight)


if __name__ == '__main__':
    create_graph_custom()