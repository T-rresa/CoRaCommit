# compare_experiment_data

本目录按实验数据生命周期进行了整理：

- `inputs/raw/`：原始插件输出或原始实验结果
- `inputs/aligned/`：与 945 条有效样本对齐后的中间结果
- `outputs/plugin_comparison/`：插件对比实验的评分表和导出结果
- `outputs/recommendation/`：模型推荐实验生成结果
- `outputs/system_test_reports/`：系统测试报告
- `scripts/`：实验与测试脚本
- `configs/`：脚本配置模板与评分配置

## 使用顺序

1. 基于 `configs/recommendation_experiment_config.example.json` 准备推荐生成配置，并使用 `scripts/run_recommendation_generation_experiment.py` 生成多模型候选输出。
2. 使用 `scripts/run_model_recommendation_experiment.py` 回放模型推荐策略。
3. 使用 `configs/score_config.json` 和 `scripts/score_merged.py` 计算插件对比实验指标。
4. 使用 `scripts/summarize_scored_results.py` 汇总插件对比实验结果。
5. 基于 `configs/system_test_config.example.json` 准备系统测试配置，并使用 `scripts/run_system_test_suite.py` 生成系统测试报告。
