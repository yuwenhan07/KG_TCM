# 中医药知识图谱系统

本项目旨在构建一个基于中医药数据的知识图谱，并提供可视化和问答功能的 Web 界面，实现用户输入症状后自动推荐相关中药配方。

![webui](pic/webui.png)
---

## 📁 项目结构

```
.
├── build/
│   ├── Crawler/
│   │   └── tcm_crawler.py
│   ├── data/
│   │   ├── cleaned_data/
│   │   ├── combine.py
│   │   ├── crawled_data_raw/
│   │   ├── data_clean.py
│   │   ├── TCM.json
│   │   └── tcm_knowledge_graph_1.json
│   ├── KG_build.py
│   └── TCM.dump
├── pic/
│   ├── headache1.png
│   ├── headache2.png
│   ├── headache3.png
│   ├── webui.png
│   └── 中医药知识图谱系统.png
├── readme.md
├── requirements.txt
├── Script/
│   └── answer.py
└── UI/
    ├── app_answer.py
    ├── app_inference.py
    ├── app_origin.py
    ├── app.py
    ├── lib/
    │   ├── bindings/
    │   ├── tom-select/
    │   └── vis-9.1.2/
    ├── static/
    │   └── graph.html
    └── templates/
        ├── index_answer.html
        ├── index_combine.html
        ├── index.html
        └── index_inference.html
```

---

## 🚀 核心功能

- 🔍 用户输入症状，系统返回推荐中药配方
- 🌐 图谱可视化展示症状与中药的关系网络
- 🤖 集成大模型自动生成治疗建议（通过 `answer.py` 实现）
- 📊 多版本界面支持：包括图谱查询、推荐建议、推理模式等

---

## 🛠 技术栈

- 后端：Python, Flask
- 图谱构建与可视化：NetworkX, PyVis
- 前端：HTML, CSS, JavaScript
- 大模型接入：通过子进程调用本地或远程模型脚本

---

## 🔧 使用方法

1. 启动 Neo4j 服务：

   请确保本地已安装并运行 Neo4j 图数据库，可通过以下命令启动：

   ```bash
   neo4j start
   ```

   默认服务地址为：`bolt://localhost:7687`，用户名密码配置请在代码中调整。

2. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

3. （可选）重新构建知识图谱：

   ```bash
   cd build
   python KG_build.py
   ```

4. 启动服务：
   
   ```bash
   cd UI
   python app_answer.py  # 启动包含模型建议的版本
   python app_inference.py  # 启动推理增强版本
   python app.py            # 启动统一入口版本
   ```
   ```bash
   cd UI
   python app_origin.py  # 启动不包含模型建议的版本
   ```

5. 访问 Web 页面：

   ```
   http://localhost:7687
   ```

---
![图像示例](pic/中医药知识图谱系统.png)

---

## 📌 注意事项

- 本项目为教学和科研用途，所提供建议不可直接用于临床医疗。
- 若需接入自定义大模型，请根据 `Script/answer.py` 接口进行调整。
- 若需使用不同界面版本，请根据需要启动 UI 目录下对应的 app 脚本

---

本系统融合中医药知识图谱与大语言模型能力，为症状与药方间的关联探索提供智能交互方式。
