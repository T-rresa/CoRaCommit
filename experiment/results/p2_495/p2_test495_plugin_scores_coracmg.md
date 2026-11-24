# Other plugins on the 495 P2 test set (CoRaCMG metrics)

| Setting | n | BLEU (GLEU) | ROUGE-L | METEOR | CIDEr (scorer) | CIDEr (eval print) |
|---|---:|---:|---:|---:|---:|---:|
| AI Commit | 495 | 3.21 | 11.40 | 17.39 | 0.0016 | 0.02 |
| Auto Commit Message | 495 | 4.12 | 5.73 | 1.30 | 0.3000 | 3.00 |
| CoRaCommit (old run) | 495 | 7.57 | 21.26 | 21.94 | 0.6542 | 6.54 |
| Commit Sage | 495 | 5.18 | 14.26 | 18.98 | 0.0194 | 0.19 |
| P2-tool 5ex | 495 | 8.74 | 23.20 | 20.99 | 0.8626 | 8.63 |
| CoRaCMG paper (reference) | ApacheCM-10K | 17.42 | 29.10 | 28.76 |  | 13.32 |

Notes:
- All rows except the CoRaCMG paper reference are on the same 495 strict P2 test ids.
- CoRaCommit (old run) is the legacy Table 3 output; its example_ids were empty, so it likely ran without retrieval.
- CIDEr_eval_print follows CoRaCMG eval.py (CiderScorer output x10).
