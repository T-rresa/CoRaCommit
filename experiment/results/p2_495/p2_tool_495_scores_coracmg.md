# CoRaCMG-prompt rerun (single exemplar, first 500)

- scored samples: 495
- prompt tokens: 1,538,637
- completion tokens: 16,789
- estimated cost (CNY, input 2/M, output 3/M): ¥3.13

| Setting | n | BLEU (GLEU) | ROUGE-L | METEOR | CIDEr (scorer) | CIDEr (eval print) |
|---|---:|---:|---:|---:|---:|---:|
| P2-tool (495) | 495 | 8.13 | 22.14 | 20.69 | 0.7944 | 7.94 |
| Old CoRaCommit / P3 (same 495) | 495 | 7.57 | 21.32 | 21.94 | 0.6542 | 6.54 |
| CoRaCMG paper (reference) | paper (different data/model) | 17.42 | 29.10 | 28.76 |  | 13.32 |

Notes:
- CoRaCMG reported values use DeepSeek-R1 and ApacheCM-10K; the rerun uses DeepSeek-V3.2 and the first 500 samples.
- CIDEr_scorer is the CiderScorer output; CoRaCMG eval.py prints it ×10, shown as CIDEr_eval_print.
