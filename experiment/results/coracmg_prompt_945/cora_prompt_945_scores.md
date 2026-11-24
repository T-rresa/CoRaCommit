# CoRaCMG-prompt rerun (single exemplar, first 500)

- scored samples: 945
- prompt tokens: 2,893,173
- completion tokens: 20,185
- estimated cost (CNY, input 2/M, output 3/M): ¥5.85

| Setting | n | BLEU (GLEU) | ROUGE-L | METEOR | CIDEr (scorer) | CIDEr (eval print) |
|---|---:|---:|---:|---:|---:|---:|
| new: CoRaCMG prompt + 1 exemplar | 945 | 17.98 | 29.68 | 28.28 | 1.4434 | 14.43 |
| current: CoRaCommit (same ids) | 945 | 6.73 | 20.94 | 21.41 | 0.6279 | 6.28 |
| CoRaCMG paper (reference) | paper (different data/model) | 17.42 | 29.10 | 28.76 |  | 13.32 |

Notes:
- CoRaCMG reported values use DeepSeek-R1 and ApacheCM-10K; the rerun uses DeepSeek-V3.2 and the first 500 samples.
- CIDEr_scorer is the CiderScorer output; CoRaCMG eval.py prints it ×10, shown as CIDEr_eval_print.
