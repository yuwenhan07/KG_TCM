import os
os.environ["CUDA_VISIBLE_DEVICES"] = "8,9"
from transformers import AutoModelForCausalLM, AutoTokenizer
import sys
import json

model_name = "/mnt/data/model/Qwen2.5-7B-Instruct"

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto"
)
tokenizer = AutoTokenizer.from_pretrained(model_name)

if len(sys.argv) > 1:
    prompt = sys.argv[1]
else:
    prompt = "Give me a short introduction to large language model."

messages = [
    {"role": "system", "content": "你是一个中医助手，善于根据知识图谱给出中药建议。"},
    {"role": "user", "content": prompt}
]

text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True
)
model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

generated_ids = model.generate(
    **model_inputs,
    max_new_tokens=512
)
generated_ids = [
    output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
]

response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
print(response)