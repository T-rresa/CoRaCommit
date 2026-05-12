import numpy as np
import pickle
from backend.app.embedding.bm25 import BM25Index
import BM25
with open("E:\Projects/vs_code_plugins/auto_gen_message/resource/bm25/bm25_diff_index.pkl", "rb") as f:
    old = pickle.load(f)

bm25 :BM25= old["bm25"]

bm25_index = BM25Index(
    tf=bm25.tf,
    df=bm25.df,
    idf=bm25.idf,
    doc_len=bm25.doc_len,
    avgdl=bm25.avgdl,
    k1=bm25.k1,
    b=bm25.b,
)

with open("E:\Projects/vs_code_plugins/auto_gen_message/resource/bm25/bm25.index.pkl", "wb") as f:
    pickle.dump(bm25_index, f)

print("BM25 migrated")
