# P2-tool 泄露受控结果（495 条）

## 1. 设置

| 项 | 值 |
|---|---|
| 测试集 | 495 条严格 P2（22 个 held-out repo，去掉 2 条 P2a） |
| 检索 | pool-only CodeBERT + temporal + prefixed issue + exact hash；top-5 |
| Prompt | 工具默认 prompt：Conventional + Angular style（optional body） |
| Exemplars | 从 `top5_p2_strict_495.jsonl` 注入；工具 prompt 的 6000 字符 cap 会截断 |
| 模型 | SiliconFlow `deepseek-ai/DeepSeek-V3.2` |
| 参数 | temperature=0, max_tokens=1024 |
| 成功 | 495/495，0 失败 |
| 空输出 / 残留标签 | 0 / 0 |

## 2. 结果

### 2.1 CoRaCMG 指标口径

| Setting | n | BLEU (GLEU) | ROUGE-L | METEOR | CIDEr (eval print) |
|---|---:|---:|---:|---:|---:|
| **P2-tool** | 495 | **8.13** | **22.14** | **20.69** | **7.94** |
| Old CoRaCommit / P3（同 495） | 495 | 7.57 | 21.32 | 21.94 | 6.54 |
| CoRaCMG 论文（参考） | ApacheCM-10K | 17.42 | 29.10 | 28.76 | 13.32 |

P2-tool vs old CoRaCommit（同 495）：

- BLEU **+0.56**
- ROUGE-L **+0.82**
- METEOR **−1.25**
- CIDEr **+1.40**

### 2.2 Table 3 口径

| Setting | n | BLEU | ROUGE-L | METEOR | CIDEr |
|---|---:|---:|---:|---:|---:|
| **P2-tool** | 495 | **5.76** | **22.14** | **20.70** | **0.5424** |
| Old CoRaCommit / P3（同 495） | 495 | 5.68 | 21.32 | 21.93 | 0.4497 |

P2-tool vs old CoRaCommit（同 495）：

- BLEU **+0.08**
- ROUGE-L **+0.82**
- METEOR **−1.23**
- CIDEr **+0.093**

## 3. 输出格式

| 来源 | 多行比例 | 平均行数 | 平均词数 | Conventional-like |
|---|---:|---:|---:|---:|
| P2-tool | 26.5% | 1.83 | 17.16 | 98.4% |
| Reference（同 495） | 0% | 1.00 | 9.07 | 9.1% |
| Old CoRaCommit | 40.6% | 2.29 | 24.0 | 99.4% |

P2-tool 比旧 CoRaCommit 短一些、多行比例低一些，但仍比 reference 长。

## 4. Token 与成本（实际）

| 项 | 值 |
|---|---:|
| Prompt tokens | 1,538,637 |
| Completion tokens | 16,789 |
| Total tokens | 1,555,426 |
| 平均输入/条 | 3,108 |
| 平均输出/条 | 33.9 |
| 列表价成本 | **¥3.13**（输入 ¥2/M，输出 ¥3/M） |
| 按之前 ¥12/945 single-exemplar 校准 | 约 **¥6.4** |

## 5. 关键发现

### 5.1 泄露控制没有让结果崩掉

P2-tool 相比旧 CoRaCommit 同 495 条：

- Table 3 口径：BLEU/ROUGE/CIDEr 略升，METEOR 略降；
- CoRaCMG 口径：BLEU/ROUGE/CIDEr 略升，METEOR 略降。

在严格 repo-disjoint + temporal + issue + exact-hash 过滤下，检索仍然有正向作用；没有出现“去掉泄漏后性能大幅下降”的情况。

### 5.2 但仍远低于 CoRaCMG prompt diagnostic

之前 CoRaCMG prompt + 1 exemplar 的 945 条结果是：

- BLEU 17.98、ROUGE 29.68、METEOR 28.28、CIDEr 14.43。

P2-tool（工具 prompt + top-5）只有 8.13/22.14/20.69/7.94（CoRaCMG 口径）。  
这说明：

- **prompt/输出格式仍是最大的差异来源**；
- 泄露控制本身不是“分数低”的主要原因；
- 工具默认 Conventional prompt 会让输出更长、多行，从而拉低词面指标。

### 5.3 工具 prompt 实际只用了 3–5 个 exemplars

`PromptBuilder` 限制：

- 每个 exemplar diff 最多 2000 字符；
- 所有 exemplar diff 合计最多 6000 字符。

实际分布：

| 实际放入的 exemplars | query 数 |
|---:|---:|
| 3 | 275 |
| 4 | 152 |
| 5 | 68 |

所以严格来说，P2-tool 是 **“top-5 候选，但 prompt 实际使用 3–5 个”**。  
如果论文写 “top-5 exemplars”，需要说明这个截断；或者调整 prompt cap 后再跑一组真正的 top-5。

### 5.4 P3 旧数据的 caveat

旧 CoRaCommit 的 `merged_aligned_945_scored_hf.jsonl` 是在 `finalMatches` bug 期间生成的，`example_ids` 全空，很可能 **没有真正使用 retrieval**。  
因此：

- P2-tool vs 旧 CoRaCommit 不能严格称为“leakage-controlled vs unrestricted retrieval”；
- 它更像“有 retrieval vs 旧的无/不确定 retrieval”；
- 如果要干净的 leakage 对照，需要用修复后的 retrieval 重跑 P3（full-corpus + self-exclusion，top-5，同 495 条），成本约 ¥3。

## 6. 建议

1. **主结果可以报 P2-tool**：严格 P2 下 495 条，检索仍有正向作用。
2. **P3 需要重跑**：旧 P3 不可靠；重跑同 495 条的 full-corpus/self-exclusion 版本，才能做干净的 leakage 对照。
3. **P2 的 prompt 说明要写清**：工具默认 prompt 实际只放入 3–5 个 exemplars，不是完整 5 个。
4. **CoRaCMG prompt diagnostic 单独报告**：它说明差距主要来自 prompt/格式，不应和 P2-tool 混为同一张表。
5. 如果要在论文里主张 “top-5”，建议把 `MAX_EXAMPLES_DIFF_CHARS` 从 6000 提高，或把 prompt 改成 message-only exemplars；否则写 “up to 5, actual 3–5”。

## 7. 文件

- 输出：`experiment/outputs/leakage/p2_tool_495.jsonl`
- 汇总：`experiment/outputs/leakage/p2_tool_495.summary.json`
- CoRaCMG 口径：`experiment/results/p2_495/p2_tool_495_scores_coracmg.csv` / `.md`
- Table 3 口径：`experiment/results/p2_495/p2_tool_495_scores_table3.csv` / `.md`
- 测试集/top5：`experiment/outputs/leakage/leakage_test_495.jsonl`、`top5_p2_strict_495.jsonl`
- 脚本：`experiment/scripts/run_p2_tool_generation.py`、`score_p2_tool_table3.py`、`score_coracmg_prompt_results.py`