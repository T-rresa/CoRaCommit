import numpy as np
import pickle

with open("E:\Projects/vs_code_plugins/auto_gen_message/resource/embeddings/codebert_diff_index.pkl", "rb") as f:
    cb = pickle.load(f)

emb = cb["embeddings"]
N = emb.shape[0]

np.save("E:\Projects/vs_code_plugins/auto_gen_message/resource/embeddings/codebert.vecs.npy", emb.astype("float32"))
np.save("E:\Projects/vs_code_plugins/auto_gen_message/resource/embeddings/codebert.doc_ids.npy", np.arange(N))  

print("CodeBERT migrated:", emb.shape)
