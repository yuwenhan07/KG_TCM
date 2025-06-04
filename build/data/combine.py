import os
import json

def combine_json_files(input_dir, output_file):
    combined_data = []
    
    for filename in os.listdir(input_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(input_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                combined_data.extend(data)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Combined {len(combined_data)} entries into {output_file}")

if __name__ == '__main__':
    input_dir = '/home/yuwenhan/ywh-code-files/2025-spring/KG/data/cleaned_data'
    output_file = '/home/yuwenhan/ywh-code-files/2025-spring/KG/data/TCM.json'
    combine_json_files(input_dir, output_file)