# 中医药知识图谱系统

本项目基于中医药数据构建知识图谱，并提供可视化 Web 界面进行交互式查询。系统分为图谱构建模块和用户界面模块两部分。

## 📁 项目结构

```
.
├── build/                 # 图谱构建相关内容
│   ├── Crawler/           # 数据抓取模块
│   ├── data/              # 原始数据文件
│   ├── KG_build.py        # 图谱构建主程序
│   └── TCM-2.dump         # 图数据库或构建输出数据
├── readme.md              # 项目说明文件
└── UI/                    # 用户界面模块
    ├── app.py             # Flask 后端主程序
    ├── lib/               # 后端逻辑库
    ├── static/            # 前端静态资源（CSS/JS）
    └── templates/         # HTML 模板
```

## 🚀 功能简介

- 抓取中医药相关症状与药物数据
- 构建实体与关系组成的知识图谱
- 提供 Web 页面查询界面，用户输入症状，返回推荐中药
- 使用图谱可视化展示症状与药物之间的连接

## 🛠 技术栈

- 后端：Python, Flask
- 数据处理与图谱：networkx, pyvis, Neo4j（如有）
- 前端：HTML, CSS, JavaScript

## 🔧 使用方法

1. 安装依赖（可根据你的依赖文件调整）：
   ```bash
   pip install -r requirements.txt
   ```

2. 构建图谱（可选）：
   ```bash
   cd build
   python KG_build.py
   ```

3. 启动 Web 服务：
   ```bash
   cd UI
   python app.py
   ```

4. 访问浏览器：
   ```
   http://localhost:7687
   ```

## 📌 注意事项

- 本系统用于中医药知识的教学与研究，不可直接用于临床诊断。
- 若需拓展新数据或关系，请更新 `build/data/` 并修改 `KG_build.py`。


本项目构建了一个基于中医药数据的知识图谱系统，结合 Web 界面可视化和用户查询功能，帮助用户了解症状与相关中药的关联。

## 功能简介

- 支持用户输入症状，查询推荐中药配方
- 图谱可视化展示症状与中药之间的知识关系
- 使用 Flask 搭建后端服务，前端采用 HTML/CSS 实现交互界面

## 技术栈

- 后端：Python, Flask
- 前端：HTML, CSS, JavaScript (部分)
- 图谱引擎：基于 networkx 和 pyvis 实现图谱构建与可视化

## 使用方法

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 启动服务：
   ```bash
   python app.py
   ```

3. 在浏览器访问：
   ```
   http://localhost:7687
   ```

## 文件结构

- `app.py`：主后端程序
- `templates/`：前端 HTML 模板
- `static/`：静态资源
- `data/`：中医药症状与中药数据文件
- `graph/`：知识图谱构建脚本与中间结果

## 说明

本系统仅供中医药教学与研究用途，不可作为临床诊断依据。
