# CoRaCMG-prompt diagnostic：完整 945 条结果

## 0. 一句话

**换用 CoRaCMG prompt + 单 exemplar + 不限定 Conventional 后，945 条的分数稳定恢复到 CoRaCMG 论文水平。**  
500 条子集与 945 条全量几乎一致，说明结果不是样本偶然。

---

## 1. 实验设置

| 项 | 值 |
|---|---|
| 样本 | 945 条（`sample_commit.jsonl`） |
| Prompt | CoRaCMG `SIMILAR_PROMPT`（single exemplar） |
| Exemplar | `top5_945.jsonl` 的 top-1（已排除 self） |
| 检索条件 | full corpus + self-exclusion only |
| 输出约束 | 无 Conventional；`<message>...</message>` |
| 模型 | SiliconFlow `deepseek-ai/DeepSeek-V3.2` |
| 参数 | temperature=0, max_tokens=1024 |
| 成功 | **945/945**，0 失败 |
| 唯一 exemplar | 940 |
| 空输出 / 残留标签 | 0 / 0 |

---

## 2. 结果（CoRaCMG 指标口径）

| Setting | n | BLEU (GLEU) | ROUGE-L | METEOR | CIDEr (scorer) | CIDEr (eval print) |
|---|---:|---:|---:|---:|---:|---:|
| **New: CoRaCMG prompt + 1 exemplar** | 945 | **17.98** | **29.68** | **28.28** | **1.4434** | **14.43** |
| Current: CoRaCommit（同 945 条） | 945 | 6.73 | 20.94 | 21.41 | 0.6279 | 6.28 |
| CoRaCMG 论文报告 | ApacheCM-10K | 17.42 | 29.10 | 28.76 | — | 13.32 |

对比：

- **New vs Current（同 945 条）**：
  - BLEU +11.24
  - ROUGE-L +8.73
  - METEOR +6.88
  - CIDEr (eval print) +8.16
- **New vs CoRaCMG 论文**：
  - BLEU +0.56
  - ROUGE-L +0.58
  - METEOR −0.48
  - CIDEr (eval print) +1.11

结论：**New 基本与 CoRaCMG 报告值持平**，BLEU/ROUGE/CIDEr 略高，METEOR 略低 0.48。

### 500 条子集 vs 945 条全量

| Setting | n | BLEU | ROUGE-L | METEOR | CIDEr |
|---|---:|---:|---:|---:|---:|
| 前 500 条 | 500 | 18.18 | 29.82 | 28.28 | 14.71 |
| 全部 945 条 | 945 | 17.98 | 29.68 | 28.28 | 14.43 |

差异非常小（BLEU −0.20、ROUGE −0.14、METEOR 0、CIDEr −0.28），说明前 500 条已经具有代表性。

---

## 3. 输出格式

| 来源 | 多行比例 | 平均行数 | 平均词数 | Conventional-like |
|---|---:|---:|---:|---:|
| New（CoRaCMG prompt） | **0%** | 1.00 | 9.81 | 25.8% |
| Reference（945 条） | **0%** | 1.00 | 8.64 | 5.4% |
| Current CoRaCommit | 40.6% | 2.29 | 24.0 | 99.4% |

New 输出 **100% 单行**，平均 9.81 词，与 reference 的 8.64 词非常接近；Current 是 40.6% 多行、平均 24 词。  
这直接解释了 BLEU/CIDEr 的差距：precision/n-gram 指标对多行/额外内容更敏感。

---

## 4. Token 与成本（实际）

| 项 | 值 |
|---|---:|
| Prompt tokens | 2,893,173 |
| Completion tokens | 20,185 |
| Total tokens | 2,913,358 |
| 平均输入/条 | 3,062 |
| 平均输出/条 | 21.4 |
| 成本 | **¥5.85**（输入 ¥2/M，输出 ¥3/M） |
| 含 10% 重试 | 约 ¥6.4 |

---

## 5. 解释

1. **Prompt 是主因**：CoRaCMG prompt 要求 concise，且没有 Conventional body 约束；模型输出单行短句，和 reference 格式一致。
2. **格式约束是第二因素**：Current CoRaCommit 的 `AngularStyle` 规则允许 optional body，导致 40.6% 多行输出，被 BLEU/CIDEr 惩罚。
3. **模型不是主要瓶颈**：CoRaCMG 报告用 DeepSeek-R1，这里用 V3.2；V3.2 + CoRaCMG prompt 已达到 17.98/29.68/28.28/14.43，与 R1 的 17.42/29.10/28.76/13.32 基本一致。
4. **检索来源不是主要瓶颈**：这里是 full-corpus + self-exclusion 的 top-1；CoRaCMG 是 same-repo top-1。即使如此也能恢复，说明 prompt/格式影响大于检索来源差异。
5. **指标口径也有影响**：New 用 CoRaCMG 的 GLEU/custom CIDEr 口径；Current 的 6.73/20.94/21.41/6.28 是同口径对比，不是 Table 3 的 sacrebleu/PTB 口径。

---

## 6. 对论文/回复信的意义

这是对 R3-3.3（“结果明显差于 [2]”）最直接、最便宜的证据：

> We ran a diagnostic on all 945 samples using CoRaCMG's prompt, a single exemplar, and no Conventional constraint. With DeepSeek-V3.2, the scores are BLEU 17.98, ROUGE-L 29.68, METEOR 28.28, CIDEr 14.43, essentially matching CoRaCMG's reported 17.42/29.10/28.76/13.32. This shows that the gap is primarily due to prompt/output format and metric definitions, not the retrieval method.

注意：

- 不建议直接把工具默认 prompt 换成 CoRaCMG prompt；Conventional 是工具特性。
- 可以在工具里增加 “concise / single-line” 选项，或在论文里同时报告 default 和 concise 两种设置。
- 该 diagnostic 是解释性实验，不是主结果；主结果仍应报告工具默认行为。

---

## 7. 注意

- 模型是 V3.2，不是 R1；结果已基本恢复，说明模型差异不是主因。
- 检索是 full-corpus top-1，不是 CoRaCMG same-repo top-1；仍能恢复，说明 prompt/格式影响更大。
- CIDEr 的 `eval print` 是 `CiderScorer` 输出 ×10，与 CoRaCMG `eval.py` 打印方式一致；与 Table 3 的 PTB CIDEr 不可直接比较。
- 945 条成本约 ¥5.85，可放心复跑。

---

## 8. 文件

- 输出：`experiment/outputs/coracmg_prompt/cora_prompt_945.jsonl`
- 前 500 条：`experiment/outputs/coracmg_prompt/cora_prompt_500.jsonl`
- 后 445 条：`experiment/outputs/coracmg_prompt/cora_prompt_945_part2.jsonl`
- 汇总：`experiment/outputs/coracmg_prompt/cora_prompt_945.summary.json`（如未生成，可由两部分 summary 相加）
- 评分：`experiment/results/coracmg_prompt_945/cora_prompt_945_scores.csv` / `.md`
- 脚本：`experiment/scripts/run_coracmg_prompt_experiment.py`、`score_coracmg_prompt_results.py`