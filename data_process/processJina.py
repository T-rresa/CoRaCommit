import numpy as np
import pickle

with open("E:\Projects/vs_code_plugins/auto_gen_message/resource/embeddings/jina_diff_index_fixed.pkl", "rb") as f:
    jina = pickle.load(f)

emb = jina["embeddings"]
N = emb.shape[0]

doc_ids = np.arange(N)

np.save("E:\Projects/vs_code_plugins/auto_gen_message/resource/embeddings/jina.vecs.npy", emb.astype("float32"))
np.save("E:\Projects/vs_code_plugins/auto_gen_message/resource/embeddings/jina.doc_ids.npy", doc_ids)   

print("Jina migrated:", emb.shape)
