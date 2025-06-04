import requests
from bs4 import BeautifulSoup
import json
import re
from collections import defaultdict
import time
import os # 导入os模块用于文件系统操作
from openai import OpenAI # 导入OpenAI库，DeepSeek API兼容OpenAI接口

# --- 配置参数 ---
BASE_URL = "https://www.901020.com/fangji/"
START_ID = 1
END_ID = 2561 # 请注意，爬取2561个页面可能需要较长时间，并消耗API额度
OUTPUT_FILE = "tcm_knowledge_graph.json" # 最终聚合的知识图谱文件
DATA_FOLDER = "crawled_data" # 存放每个页面单独JSON的文件夹
REQUEST_DELAY = 0.1 # 每个请求之间的延迟（秒），建议设置，避免对服务器造成过大压力


# DeepSeek API 配置
DEEPSEEK_API_KEY = "API" # <<<<<<< 请在这里填入您的DeepSeek API Key >>>>>>>
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat" # 或 "deepseek-v2" 等您想使用的模型

# 初始化DeepSeek客户端
deepseek_client = None
if DEEPSEEK_API_KEY == "YOUR_DEEPSEEK_API_KEY" or not DEEPSEEK_API_KEY:
    print("警告: DeepSeek API Key 未设置。请在代码中填入您的DEEPSEEK_API_KEY。")
    print("在未设置API Key的情况下，组成部分和功能主治将无法通过LLM解析，将返回空列表。")
else:
    try:
        deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    except Exception as e:
        print(f"DeepSeek API 客户端初始化失败: {e}")
        print("请检查您的API Key和网络连接。组成部分和功能主治将无法通过LLM解析。")
        deepseek_client = None


# 定义节点类型和关系类型
NODE_TYPES = {'方名', '功能主治', '别名', '剂量', '来源', '方剂', '处方', '中药名'}
RELATION_TYPES = {'prescription type', 'dose', 'from', 'another name', 'composition', 'include', 'functions'}

# 将HTML中的标题映射到内部概念名称
SECTION_MAP = {
    "方剂名": "方名",
    "出处": "来源",
    "组成": "处方",
    "功效": "功能主治_raw", # 标记为原始文本，待LLM处理
    "主治": "功能主治_raw", # 标记为原始文本，待LLM处理
    "别名": "别名",
}

# 全局列表，用于存储所有提取到的三元组（最终聚合用）
all_triples = []
# 使用defaultdict来统计方剂名出现次数，用于处理重复方剂名（如：仙遗粮汤1, 仙遗粮汤2）
formula_name_counts = defaultdict(int)

# --- LLM集成：用于解析“组成”部分 ---
def extract_composition_with_llm(composition_text: str) -> list:
    """
    使用DeepSeek V3大模型API解析中药组成文本。
    它应接收原始的组成文本，并返回一个元组列表：
    [(中药名, 剂量文本), ...]
    """
    if not deepseek_client:
        return []

    system_prompt = (
        "你是一位专业的中药方剂分析助手。你的任务是从用户提供的中药组成文本中，"
        "准确地提取出每味中药的名称及其对应的剂量。请确保提取的剂量是原始文本中描述的完整剂量信息（包括单位和括号内的数值，如'四两（120g）'）。"
        "如果文本中某个剂量适用于多味中药（例如'A、B、C 各一钱'），请将该剂量分别赋给每味中药。"
        "如果某味中药没有明确的剂量，请使用'适量'作为其剂量。"
        "请以一个JSON对象的形式返回结果，该对象必须包含一个名为 'herbs_data' 的键，其值是一个JSON数组。"
        "数组中的每个对象都应包含'herb_name'和'dosage'两个键。"
        "例如：{\"herbs_data\": [{\"herb_name\": \"人参\", \"dosage\": \"3g\"}, {\"herb_name\": \"黄芪\", \"dosage\": \"5g\"}]}"
        "请严格遵守JSON格式，不要包含任何额外说明或解释。"
    )
    user_prompt = f"请从以下中药组成文本中提取中药名和剂量：\n\n{composition_text}"

    try:
        response = deepseek_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        response_content = response.choices[0].message.content
        parsed_data = json.loads(response_content)
        
        if 'herbs_data' not in parsed_data or not isinstance(parsed_data['herbs_data'], list):
            return []

        extracted_list = []
        for item in parsed_data['herbs_data']:
            if isinstance(item, dict) and 'herb_name' in item and 'dosage' in item:
                extracted_list.append((item['herb_name'], item['dosage']))
        return extracted_list

    except json.JSONDecodeError as e:
        print(f"LLM响应解析为JSON失败: {e}")
        print(f"原始LLM响应: {response_content}")
        return []
    except Exception as e:
        print(f"调用DeepSeek API时发生错误: {e}")
        print(f"原始组成文本: {composition_text}")
        return []

# --- LLM集成：用于解析“功能主治”部分 ---
def extract_functions_with_llm(functions_text: str) -> list:
    """
    使用DeepSeek V3大模型API解析功能主治文本。
    它应接收原始的功效/主治文本，并返回一个字符串列表，每个字符串是一个独立的功效或主治条目。
    """
    if not deepseek_client:
        return []

    system_prompt = (
        "你是一位专业的中药方剂分析助手。你的任务是从用户提供的功能主治文本中，"
        "准确地提取出所有独立的功效和主治条目。请将每个条目视为一个独立的短语或句子。"
        "请以一个JSON对象的形式返回结果，该对象必须包含一个名为 'functions_list' 的键，其值是一个JSON数组。"
        "数组中的每个元素都应是一个表示独立功效或主治的字符串。"
        "例如：{\"functions_list\": [\"疏风清热\", \"活血散瘀\", \"除湿解毒\"]}"
        "请严格遵守JSON格式，不要包含任何额外说明或解释。"
    )
    user_prompt = f"请从以下功能主治文本中提取功效和主治条目：\n\n{functions_text}"

    try:
        response = deepseek_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        response_content = response.choices[0].message.content
        parsed_data = json.loads(response_content)
        
        if 'functions_list' not in parsed_data or not isinstance(parsed_data['functions_list'], list):
            return []

        extracted_list = []
        for item in parsed_data['functions_list']:
            if isinstance(item, str) and item.strip():
                extracted_list.append(item.strip())
        return list(set(extracted_list)) # 去重并返回
    
    except json.JSONDecodeError as e:
        print(f"LLM响应解析为JSON失败 (功能主治): {e}")
        print(f"原始LLM响应: {response_content}")
        return []
    except Exception as e:
        print(f"调用DeepSeek API时发生错误 (功能主治): {e}")
        print(f"原始功能主治文本: {functions_text}")
        return []

# --- 辅助函数：添加三元组 ---
def add_triple(node1_type: str, node1_name: str, relation: str, node2_type: str, node2_name: str, target_list: list):
    """
    向指定列表添加一个三元组，并检查节点类型和关系类型的有效性。
    同时打印新添加的三元组。
    """
    if node1_type not in NODE_TYPES or node2_type not in NODE_TYPES:
        return
    if relation not in RELATION_TYPES:
        return

    new_triple = {
        "node_1": f"{node1_type}\t{node1_name}",
        "relation": relation,
        "node_2": f"{node2_type}\t{node2_name}"
    }
    target_list.append(new_triple)
    
    print(json.dumps(new_triple, ensure_ascii=False, indent=2))
    print("-" * 30)

# --- Helper function to extract formula name, sources, and aliases from the name string ---
def extract_formula_name_and_related_info(name_content: str):
    """
    Takes the raw content after 【方剂名】 and separates:
    - The pure formula name
    - Embedded source information
    - Embedded alias information
    Returns (cleaned_name, extracted_sources_list, extracted_aliases_list).
    """
    cleaned_name = name_content.strip()
    extracted_sources = []
    extracted_aliases = []

    # Step 1: Remove trailing punctuation from the whole string first
    cleaned_name = re.sub(r'[。，；：！？]$', '', cleaned_name)
    
    # Step 2: Extract source based on "出自/见于/载于"
    source_match_1 = re.match(r'^(.*?)(?:[，,]\s*(?:出自|见于|载于)\s*)(.*)$', cleaned_name)
    if source_match_1:
        cleaned_name = source_match_1.group(1).strip()
        source_part = source_match_1.group(2).strip()
        source_part = re.sub(r'[。，；：！？]$', '', source_part)
        if source_part:
            extracted_sources.append(source_part)

    # Step 3: Extract and classify trailing bracketed content (sources or aliases)
    temp_name = cleaned_name
    while True:
        # This regex captures the part *before* the last bracketed content, and the bracketed content itself.
        # It handles both 【...】 and (...)
        trailing_bracketed_info_match = re.match(r'^(.*?)\s*((?:【[^】]*?】|$$[^)]\*?$$)(?:\s*.*?)*)$', temp_name)
        if trailing_bracketed_info_match:
            name_part = trailing_bracketed_info_match.group(1).strip()
            bracketed_raw_content = trailing_bracketed_info_match.group(2).strip()

            # Clean the raw bracketed content: remove outer brackets
            cleaned_bracketed_content = re.sub(r'^(?:【([^】]*?)】|$$([^)]\*?)$$)$', r'\1\2', bracketed_raw_content).strip()

            # Determine if it's a source or an alias based on keywords
            is_source = False
            # Strong indicators for source
            if re.search(r'(?:《.*?》|卷|方论|医宗|医方|秘方|金匮|伤寒|外科|正宗|大全|入门|宝鉴|心法|要诀|集|论|方|书)$', cleaned_bracketed_content):
                is_source = True
            # Explicit alias indicator
            elif re.search(r'^(?:又名|别名)', cleaned_bracketed_content): 
                is_source = False # It's an alias
            # If it contains "来源" or "出处" but not "又名", lean towards source
            elif re.search(r'(?:来源|出处)', cleaned_bracketed_content) and not re.search(r'又名|别名', cleaned_bracketed_content):
                 is_source = True

            if is_source:
                # Further clean source: remove internal tags like 【来源】
                final_source_part = re.sub(r'【.*?】|$$.\*?$$', '', cleaned_bracketed_content).strip()
                final_source_part = re.sub(r'^(?:来源|出处)\s*', '', final_source_part).strip()
                if final_source_part:
                    extracted_sources.append(final_source_part)
            else:
                # It's likely an alias. Clean up "又名" and quotes.
                alias_part = re.sub(r'^(?:又名|别名)\s*', '', cleaned_bracketed_content).strip()
                alias_part = re.sub(r'[“”‘’]', '', alias_part).strip()
                
                individual_aliases_in_group = re.split(r'[、，]\s*(?![^（）]*[）])', alias_part)
                for alias_item in individual_aliases_in_group:
                    alias_item = alias_item.strip()
                    if alias_item:
                        extracted_aliases.append(alias_item)
            
            temp_name = name_part
        else:
            break

    cleaned_name = temp_name
    cleaned_name = re.sub(r'[。，；：！？]$', '', cleaned_name)
    
    final_extracted_source_str = "；".join(sorted(list(set(s for s in extracted_sources if s))))
    final_extracted_aliases_list = sorted(list(set(a for a in extracted_aliases if a)))

    return cleaned_name, final_extracted_source_str, final_extracted_aliases_list


# --- 主爬虫函数 ---
def scrape_tcm_formula_data():
    # 1. 创建数据文件夹
    os.makedirs(DATA_FOLDER, exist_ok=True)

    # 2. 加载已爬取的数据和已处理的ID，用于断点续爬和最终聚合
    processed_ids = set()
    global formula_name_counts
    
    print(f"正在加载 '{DATA_FOLDER}' 中已爬取的数据...")
    for filename in os.listdir(DATA_FOLDER):
        if filename.endswith(".json"):
            try:
                page_id = int(filename.replace(".json", ""))
                with open(os.path.join(DATA_FOLDER, filename), 'r', encoding='utf-8') as f:
                    loaded_triples = json.load(f)
                    all_triples.extend(loaded_triples)

                    for triple in loaded_triples:
                        if "方名\t" in triple["node_2"] and triple["relation"] == "include":
                            full_formula_name = triple["node_2"].split('\t')[1]
                            raw_name = re.sub(r'\d+$', '', full_formula_name)
                            formula_name_counts[raw_name] += 1
                processed_ids.add(page_id)
            except (ValueError, json.JSONDecodeError) as e:
                print(f"警告: 无法加载或解析文件 {filename}: {e}")
    
    print(f"已加载 {len(all_triples)} 条现有三元组。已处理页面ID数量: {len(processed_ids)}")
    print(f"当前方剂名计数（用于编号）: {dict(formula_name_counts)}")


    for i in range(START_ID, END_ID + 1):
        page_output_file = os.path.join(DATA_FOLDER, f"{i}.json")

        if i in processed_ids:
            print(f"跳过已爬取页面: {BASE_URL}{i}.html (数据已存在于 {page_output_file})")
            continue

        url = f"{BASE_URL}{i}.html"
        
        time.sleep(REQUEST_DELAY)

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            print(f"正在爬取: {url}...") 
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                pass 
            else:
                print(f"HTTP错误 {url}: {e}")
            continue
        except requests.exceptions.RequestException as e:
            print(f"获取 {url} 时发生错误: {e}")
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        
        main_content_div = soup.find('div', class_='content')
        if not main_content_div:
            main_content_div = soup.find('div', class_='article-content')
        if not main_content_div:
            main_content_div = soup.body

        formula_blocks = []
        current_block_p_tags = []
        
        all_p_tags_in_content = main_content_div.find_all('p', recursive=False)

        for p_tag in all_p_tags_in_content:
            full_p_text_for_block_check = p_tag.get_text(strip=True)
            if re.match(r'【方剂名】', full_p_text_for_block_check):
                if current_block_p_tags:
                    formula_blocks.append(current_block_p_tags)
                current_block_p_tags = [p_tag]
            elif current_block_p_tags:
                current_block_p_tags.append(p_tag)
        
        if current_block_p_tags:
            formula_blocks.append(current_block_p_tags)

        if not formula_blocks:
            formula_blocks = [main_content_div.find_all('p')]
            
            if not formula_blocks[0]:
                continue

        # --- 第一遍遍历，统计每个方剂名下的组成数量 ---
        formula_composition_counts_on_this_page = defaultdict(int)
        temp_formula_name_raw_for_counting_this_page = defaultdict(int) 

        for block_idx_temp, block_p_tags_temp in enumerate(formula_blocks):
            temp_formula_name = ""
            has_composition_section = False
            for p_tag_temp in block_p_tags_temp:
                full_p_text_temp = p_tag_temp.get_text(strip=True)
                match_temp = re.match(r'【(.*?)】\s*(.*)', full_p_text_temp)
                if match_temp:
                    header_name_raw_temp = match_temp.group(1).strip()
                    content_temp = match_temp.group(2).strip()
                    if header_name_raw_temp == "方剂名":
                        name_only_temp, _, _ = extract_formula_name_and_related_info(content_temp)
                        
                        if name_only_temp:
                            raw_name_candidate = name_only_temp
                            temp_formula_name_raw_for_counting_this_page[raw_name_candidate] += 1
                            current_total_count = formula_name_counts[raw_name_candidate] + temp_formula_name_raw_for_counting_this_page[raw_name_candidate]
                            if current_total_count > 1:
                                temp_formula_name = f"{raw_name_candidate}{current_total_count}"
                            else:
                                temp_formula_name = raw_name_candidate
                    elif header_name_raw_temp == "组成":
                        has_composition_section = True
            
            if temp_formula_name and has_composition_section:
                formula_composition_counts_on_this_page[temp_formula_name] += 1
        # --- 结束第一遍遍历 ---

        current_formula_composition_index_on_page = defaultdict(int)
        current_page_triples = []

        # --- 第二遍遍历：提取数据并构建三元组 ---
        for block_idx, block_p_tags in enumerate(formula_blocks):
            formula_data = {}
            current_formula_name_raw = ""

            for p_tag in block_p_tags:
                full_p_text = p_tag.get_text(strip=True)
                match = re.match(r'【(.*?)】\s*(.*)', full_p_text)
                
                if match:
                    header_name_raw = match.group(1).strip()
                    content = match.group(2).strip()
                    
                    key = SECTION_MAP.get(header_name_raw)

                    if key:
                        if key == "方名":
                            formula_name_candidate, extracted_source_from_name, extracted_aliases_from_name = extract_formula_name_and_related_info(content)
                            
                            if formula_name_candidate:
                                current_formula_name_raw = formula_name_candidate
                                formula_name_counts[current_formula_name_raw] += 1
                                if formula_name_counts[current_formula_name_raw] > 1:
                                    formula_data[key] = f"{current_formula_name_raw}{formula_name_counts[current_formula_name_raw]}"
                                else:
                                    formula_data[key] = current_formula_name_raw
                                
                                # 将提取到的来源信息添加到formula_data中
                                if extracted_source_from_name:
                                    if "来源" in formula_data:
                                        existing_sources = [s.strip() for s in re.split(r'[；，]', formula_data["来源"]) if s.strip()]
                                        new_sources = [s.strip() for s in re.split(r'[；，]', extracted_source_from_name) if s.strip()]
                                        for ns in new_sources:
                                            if ns and ns not in existing_sources:
                                                formula_data["来源"] += f"；{ns}"
                                    else:
                                        formula_data["来源"] = extracted_source_from_name
                                
                                # 将提取到的别名信息添加到formula_data中（临时存储，待统一处理）
                                if extracted_aliases_from_name:
                                    if "别名" not in formula_data:
                                        formula_data["别名"] = []
                                    formula_data["别名"].extend(extracted_aliases_from_name)
                                    formula_data["别名"] = list(set(formula_data["别名"])) # 确保列表中的别名是唯一的
                            else:
                                continue
                        elif key == "功能主治_raw": # 特殊处理功能主治的原始文本
                            if "功能主治_raw_texts" not in formula_data:
                                formula_data["功能主治_raw_texts"] = []
                            formula_data["功能主治_raw_texts"].append(content)
                        else:
                            # 对于非方剂名（如【出处】），也进行一次清理，确保没有冗余标签
                            if key == "来源":
                                cleaned_content_source = re.sub(r'【.*?】|$$.\*?$$', '', content).strip()
                                cleaned_content_source = re.sub(r'^(?:来源|出处)\s*', '', cleaned_content_source).strip()
                                if cleaned_content_source:
                                    if "来源" in formula_data:
                                        existing_sources = [s.strip() for s in re.split(r'[；，]', formula_data["来源"]) if s.strip()]
                                        new_sources = [s.strip() for s in re.split(r'[；，]', cleaned_content_source) if s.strip()]
                                        for ns in new_sources:
                                            if ns and ns not in existing_sources:
                                                formula_data["来源"] += f"；{ns}"
                                    else:
                                        formula_data[key] = cleaned_content_source
                            else:
                                formula_data[key] = content
            
            if not formula_data.get("方名"):
                continue

            formula_name = formula_data["方名"]
            
            add_triple("方剂", "方剂", "include", "方名", formula_name, current_page_triples)

            if "来源" in formula_data and formula_data["来源"]:
                add_triple("方名", formula_name, "from", "来源", formula_data["来源"], current_page_triples)

            # --- 统一处理别名 ---
            if "别名" in formula_data and formula_data["别名"]:
                if isinstance(formula_data["别名"], list): # 从方剂名中提取的别名
                    all_aliases_to_process = formula_data["别名"]
                else: # 从【别名】字段提取的别名
                    aliases_text = formula_data["别名"]
                    all_aliases_to_process = re.split(r'[、，]\s*(?![^（）]*[）])', aliases_text)
                
                unique_aliases = set()
                for alias_entry in all_aliases_to_process:
                    cleaned_alias = alias_entry.strip()
                    cleaned_alias = re.sub(r'[。，；：！？]$', '', cleaned_alias)
                    if cleaned_alias:
                        unique_aliases.add(cleaned_alias)

                for alias in sorted(list(unique_aliases)):
                    add_triple("方名", formula_name, "another name", "别名", alias, current_page_triples)

            # --- 统一处理功能主治（使用LLM） ---
            if "功能主治_raw_texts" in formula_data and formula_data["功能主治_raw_texts"]:
                combined_functions_text = " ".join(formula_data["功能主治_raw_texts"]).strip()
                if combined_functions_text:
                    extracted_functions = extract_functions_with_llm(combined_functions_text)
                    for func_item in extracted_functions:
                        add_triple("方名", formula_name, "functions", "功能主治", func_item, current_page_triples)

            if "处方" in formula_data and formula_data["处方"]:
                composition_text = formula_data["处方"]
                
                current_formula_composition_index_on_page[formula_name] += 1
                
                if formula_composition_counts_on_this_page[formula_name] == 1:
                    prescription_node_name = formula_name
                else:
                    prescription_node_name = f"{formula_name}_组成_{current_formula_composition_index_on_page[formula_name]}"

                add_triple("方名", formula_name, "prescription type", "处方", prescription_node_name, current_page_triples)
                
                extracted_herbs_dosages = extract_composition_with_llm(composition_text)
                
                for herb_name, dosage_text in extracted_herbs_dosages:
                    if herb_name:
                        add_triple("处方", prescription_node_name, "composition", "中药名", herb_name, current_page_triples)
                        if dosage_text:
                            add_triple("中药名", herb_name, "dose", "剂量", dosage_text, current_page_triples)

        if current_page_triples:
            with open(page_output_file, 'w', encoding='utf-8') as f:
                json.dump(current_page_triples, f, ensure_ascii=False, indent=2)
            print(f"已保存页面 {i} 的数据到 {page_output_file}")
        else:
            print(f"页面 {i} 未提取到有效数据，未生成单独文件。")


    # 最终将所有聚合的三元组保存到总文件
    final_all_triples = []
    final_formula_name_counts = defaultdict(int)
    for filename in os.listdir(DATA_FOLDER):
        if filename.endswith(".json"):
            try:
                with open(os.path.join(DATA_FOLDER, filename), 'r', encoding='utf-8') as f:
                    loaded_triples = json.load(f)
                    final_all_triples.extend(loaded_triples)
                    for triple in loaded_triples:
                        if "方名\t" in triple["node_2"] and triple["relation"] == "include":
                            full_formula_name = triple["node_2"].split('\t')[1]
                            raw_name = re.sub(r'\d+$', '', full_formula_name)
                            final_formula_name_counts[raw_name] += 1
            except (ValueError, json.JSONDecodeError) as e:
                print(f"警告: 无法加载或解析文件 {filename} 用于最终聚合: {e}")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_all_triples, f, ensure_ascii=False, indent=2)
    print(f"\n数据爬取完成。已将 {len(final_all_triples)} 个三元组保存到 {OUTPUT_FILE}")
    print(f"最终方剂名计数: {dict(final_formula_name_counts)}")


# --- 运行爬虫 ---
if __name__ == "__main__":
    scrape_tcm_formula_data()