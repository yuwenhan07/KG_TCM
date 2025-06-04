import os
import json
import re
from statistics import mean

def parse_weight(text):
    """保留原始剂量字符串"""
    return text.strip()

def clean_file(file_path, output_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 1. 提取所有中药 -> 剂量 映射
    dose_map = {}
    for entry in data:
        if entry['relation'] == 'dose':
            herb_name = entry['node_1'].split('\t')[1]
            dose_text = entry['node_2'].split('\t')[-1]
            weight = parse_weight(dose_text)
            if weight:
                dose_map[herb_name] = weight

    # 2. 重构 composition 关系并附加 weight
    cleaned = []
    for entry in data:
        if entry['relation'] == 'composition':
            herb_name = entry['node_2'].split('\t')[1]
            new_entry = dict(entry)
            if herb_name in dose_map:
                new_entry['weight'] = dose_map[herb_name]
            cleaned.append(new_entry)
        elif entry['relation'] != 'dose':
            cleaned.append(entry)

    # 3. 输出
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f"✅ Cleaned: {file_path}")


def clean_all_files(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    for fname in os.listdir(input_dir):
        if fname.endswith('.json'):
            fpath = os.path.join(input_dir, fname)
            outpath = os.path.join(output_dir, fname)
            clean_file(fpath, outpath)


if __name__ == '__main__':
    input_dir = './crawled_data_raw'
    output_dir = './cleaned_data'
    clean_all_files(input_dir, output_dir)