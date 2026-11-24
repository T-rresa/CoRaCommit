# P2-tool 5-exemplar 结果（495 条）

## 1. 设置

| 项 | 值 |
|---|---|
| 测试集 | 495 条严格 P2（22 held-out repo，去掉 2 条 P2a） |
| 检索 | pool-only + temporal + prefixed issue + exact hash；top-5 |
| Prompt | 工具默认 prompt（Conventional + Angular style） |
| Exemplar cap | **已关闭**（不再 2000/6000 字符截断） |
| 实际 exemplars | **495/495 条都放入 5 个** |
| 模型 | SiliconFlow `deepseek-ai/DeepSeek-V3.2` |
| 参数 | temperature=0, max_tokens=1024 |
| 成功 | 495/495，0 失败 |
| 空输出 / 残留标签 | 0 / 0 |

## 2. 结果

### 2.1 CoRaCMG 指标口径

| Setting | n | BLEU (GLEU) | ROUGE-L | METEOR | CIDEr (eval print) |
|---|---:|---:|---:|---:|---:|
| **P2-tool 5ex** | 495 | **8.74** | **23.18** | **20.99** | **8.63** |
| P2-tool capped 3–5ex | 495 | 8.13 | 22.14 | 20.69 | 7.94 |
| Old CoRaCommit / P3（同 495） | 495 | 7.57 | 21.32 | 21.94 | 6.54 |
| CoRaCMG 论文（参考） | ApacheCM-10K | 17.42 | 29.10 | 28.76 | 13.32 |

5ex vs capped：

- BLEU **+0.61**
- ROUGE-L **+1.04**
- METEOR **+0.30**
- CIDEr **+0.69**

### 2.2 Table 3 口径

| Setting | n | BLEU | ROUGE-L | METEOR | CIDEr |
|---|---:|---:|---:|---:|---:|
| **P2-tool 5ex** | 495 | **6.21** | **23.22** | **20.98** | **0.6081** |
| P2-tool capped 3–5ex | 495 | 5.76 | 22.14 | 20.70 | 0.5424 |
| Old CoRaCommit / P3（同 495） | 495 | 5.68 | 21.32 | 21.93 | 0.4497 |

5ex vs capped：

- BLEU **+0.45**
- ROUGE-L **+1.08**
- METEOR **+0.28**
- CIDEr **+0.066**

5ex vs old P3：

- BLEU **+0.53**
- ROUGE-L **+1.90**
- METEOR **−0.95**
- CIDEr **+0.158**

## 3. 输出格式

| 来源 | 多行比例 | 平均行数 | 平均词数 | Conventional-like |
|---|---:|---:|---:|---:|
| P2-tool 5ex | 20.6% | 1.69 | 15.75 | 98.2% |
| P2-tool capped | 26.5% | 1.83 | 17.16 | 98.4% |
| Reference | 0% | 1.00 | 9.07 | 9.1% |

5 个完整 exemplars 让输出略短一些，但仍比 reference 长。

## 4. Token 与成本（实际）

| 项 | 值 |
|---|---:|
| Prompt tokens | 4,215,078 |
| Completion tokens | 36,241 |
| Total tokens | 4,251,319 |
| 平均输入/条 | 8,515 |
| 平均输出/条 | 73.2 |
| 列表价成本 | **¥8.54** |
| 按之前 ¥12/945 single-exemplar 校准 | 约 **¥18** |

对比 capped 版本：输入 tokens 从 1.54M 增到 4.22M（约 2.7×），成本从 ¥3.13 增到 ¥8.54（列表价）。

## 5. 解释

1. **5 个完整 exemplars 确实比 capped 3–5 好**：BLEU/ROUGE/CIDEr 都提升，说明 exemplar 数量/完整 diff 有正向作用。
2. **但仍远低于 CoRaCMG prompt diagnostic**（17.98/29.68/28.28/14.43）：工具默认 Conventional prompt + optional body 仍是主要差距来源。
3. **P2-tool 5ex 相比旧 P3 仍有提升**：BLEU/ROUGE/CIDEr 上升，METEOR 略降；与 capped 版本的趋势一致。
4. **旧 P3 仍不可靠**：旧 CoRaCommit 数据是在 `finalMatches` bug 期间生成的，`example_ids` 全空，可能没有真正用 retrieval。P2-tool vs 旧 P3 不能严格称为 leakage-controlled vs unrestricted retrieval；要干净对照需要重跑 P3（约 ¥3）。

## 6. 建议

- 如果论文要主张 “top-5 exemplars”，用这组 5ex 结果，并在论文里说明已关闭 exemplar 截断；或者把生产默认改成可配置。
- 如果论文要报告工具默认行为，用 capped 版本（3–5 exemplars），并明确说明截断。
- 最佳呈现：一张表同时给 **capped（默认）** 和 **5ex（完整 top-5）**，说明 exemplar 数量的影响。
- CoRaCMG prompt diagnostic 单独报告，说明 prompt/格式是更大的因素。
- 若要干净的 leakage 对照，补跑 P3（full-corpus top-5，固定检索，495 条，约 ¥3）。

## 7. 文件

- 输出：`experiment/outputs/leakage/p2_tool_495_5ex.jsonl`
- 汇总：`experiment/outputs/leakage/p2_tool_495_5ex.summary.json`
- CoRaCMG 口径：`experiment/results/p2_495/p2_tool_495_5ex_scores_coracmg.csv` / `.md`
- Table 3 口径：`experiment/results/p2_495/p2_tool_495_5ex_scores_table3.csv` / `.md`
- 备份（capped 版本）：`_backups/20261120_p2_tool_495_capped/`
- 脚本：`experiment/scripts/run_p2_tool_generation.py`（`--no-exemplar-cap`）