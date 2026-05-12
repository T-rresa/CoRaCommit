import numpy as np
import faiss

# ------------------------
# 加载向量和 doc_ids
# ------------------------
vecs = np.load("E:/Projects/vs_code_plugins/auto_gen_message/resource/embeddings/codebert.vecs.npy")
doc_ids = np.load("E:/Projects/vs_code_plugins/auto_gen_message/resource/embeddings/codebert.doc_ids.npy")

vecs = vecs.astype("float32")  # FAISS要求float32
N, dim = vecs.shape
print(f"Loaded {N} vectors with dim={dim}")

# ------------------------
# 构建 FAISS 索引
# ------------------------
index = faiss.IndexFlatIP(dim)  # 内积，向量需要归一化才能作为余弦相似度
faiss.normalize_L2(vecs)       # 归一化向量
index.add(vecs)
print(f"FAISS index contains {index.ntotal} vectors")
faiss.write_index(index, "E:/Projects/vs_code_plugins/auto_gen_message/resource/faiss/codebert.index")  # 保存为二进制文件
