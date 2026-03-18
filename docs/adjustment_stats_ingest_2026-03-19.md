# 调剂统计表接入说明（2026-03-19）

这份说明描述如何把外部调剂统计 Excel 转成当前项目可复用的数据产物。

## 来源

- 源文件样例：`23-25调剂统计数据.xlsx`
- 当前接入文件包含 `2023 / 2024 / 2025` 三个年份，共 `682750` 条调剂记录

## 当前用途

这份表不直接作为线上查询主库导入。当前先承担两个角色：

1. 生成重点学校/学院 seed
   - 用于补齐 `schools / departments / site_sections` 的优先目标
2. 生成调剂结构化摘要
   - 用于判断哪些学校、学院、专业方向应优先治理

## 生成脚本

脚本位置：

- [backend/scripts/build_adjustment_priority_targets.py](/Users/guhai/Documents/New%20project/gewujl/kaoyan-miniapp-mvp/backend/scripts/build_adjustment_priority_targets.py)

执行方式：

```bash
cd /Users/guhai/Documents/New project/gewujl/kaoyan-miniapp-mvp
./.venv/bin/python backend/scripts/build_adjustment_priority_targets.py \
  --input "/Users/guhai/Downloads/2018-2025调剂总表（未单分专业）/23-25调剂统计数据.xlsx" \
  --summary-output docs/data/adjustment_stats_2023_2025_summary.json \
  --targets-output docs/data/adjustment_priority_school_targets_2023_2025.json \
  --top-schools 60 \
  --top-departments 2
```

## 产物

1. 汇总摘要
- [docs/data/adjustment_stats_2023_2025_summary.json](/Users/guhai/Documents/New%20project/gewujl/kaoyan-miniapp-mvp/docs/data/adjustment_stats_2023_2025_summary.json)

2. 导入型重点学校 seed
- [docs/data/adjustment_priority_school_targets_2023_2025.json](/Users/guhai/Documents/New%20project/gewujl/kaoyan-miniapp-mvp/docs/data/adjustment_priority_school_targets_2023_2025.json)

## 后台导入接口

- `POST /api/v1/schools/import/adjustment-priority-targets`

这个接口会把生成好的 seed 导入到：

- `schools`
- `departments`

它不会自动创建 `site_sections`，但会把重点学校和学院预先建好，便于后续栏目治理。

## 当前结论

- 这份 Excel 更适合作为“调剂样本与优先级来源”，不适合直接当线上检索主表
- 当前 top 学校集中在：
  - 河北大学
  - 广西大学
  - 昆明理工大学
  - 燕山大学
  - 江苏大学
- 当前优先策略仍然是：
  - 先把这些高频学校变成站点资产
  - 再继续调优调剂查询与公告治理
