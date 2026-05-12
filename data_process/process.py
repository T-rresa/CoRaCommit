import pickle
import json

with open("E:\Projects/vs_code_plugins/auto_gen_message/resource/embeddings/jina_diff_index_fixed.pkl", "rb") as f:
    jina = pickle.load(f)

raw_items = jina["raw_items"]

# 生成全局 id
docs = []
for i, item in enumerate(raw_items):
    item["_id"] = i
    docs.append(item)

# 存成唯一文本库
with open("E:\Projects/vs_code_plugins/auto_gen_message/resource/docs.jsonl", "w", encoding="utf-8") as f:
    for d in docs:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")

print("Saved docs.jsonl:", len(docs))
