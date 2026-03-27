# 研招公告可见性收口交接文档（2026-03-25）

本文档用于把 2026-03-25 这一轮“公告门户可见性 / 监控命中 / 历史脏数据过滤”收口工作转交给后续 AI 或开发者继续推进。

## 1. 本轮目标

这一轮不是做新页面，而是收紧后端里“什么算研招公告”的判定，避免两类问题继续污染线上结果：

- 栏目级/院系级公告明明命中了 `site_section`，却因为元数据重算把 `site_section_id` 清掉，导致高级监控命中失败。
- 普通新闻、工会通知、行政公开等历史内容，只因为正文里出现了“研招”“研究生招生”等字样，就被误当成可见研招公告。

## 2. 本轮已完成

### 2.1 判定规则收紧

- 新增“URL 看起来像研招站”的启发式判断。
- 新增“标题/摘要/正文看起来像研招公告”的启发式判断。
- 新增负向语义拦截：
  - `不属于研招`
  - `不属于研究生招生`
  - `不是研招`
  - `与研究生招生无关`
- 默认公告可见性从“缺元数据也放行”改为“缺少研招门户证据时默认隐藏”，但院系显式作用域仍然放行。

### 2.2 scope 元数据保留

- `site_section_id / site_section_name` 现在被视为“范围命中元数据”，在 upsert / crawler finalize / backfill 时都会保留。
- 这样栏目级监控 target 的 `scope_type=section` 不会再因为门户元数据清洗丢失 scope。

### 2.3 标签合并规则修正

- 显式传入的 `system_tags` 现在是权威输入，不再被自动推断结果继续放大。
- `channel_label` 仍可补充到 `tags`，但只有在两种情况下才前置：
  - 来源于维护过的 `site_section`
  - 来源于显式 payload
- 对纯文本自动推断出的 label，不再强行打乱原始标签顺序。

### 2.4 backfill 能力补齐

- `backend/scripts/backfill_announcement_portal_metadata.py`
  现在支持在没有 `site_section` 关联时，仅凭 URL + 标题/正文推断研招公告元数据。
- backfill 在 commit 后会主动清搜索缓存。
- backfill 结果里新增：
  - `inferred_without_section`

### 2.5 测试补齐

- 新增/修正了以下覆盖方向：
  - 栏目级 scope-only 监控命中
  - 手工内容通过 `site_section_name` 反查 `site_section_id`
  - 非研招历史详情页不会被 backfill 提升
  - 无栏目关联的研招历史页可通过 URL + 标题推断
  - 搜索默认隐藏未归档普通历史新闻
  - `available_system_tags` 与 `tags` 顺序符合现行规则

## 3. 关键文件

- `backend/app/services/announcement_portal.py`
  - 研招门户元数据推断
  - 可见性判定
  - 标签合并规则
- `backend/app/services/content.py`
  - 内容 upsert 时的 announcement extra 归一化
- `backend/app/services/crawler.py`
  - 抓取入库时的 announcement extra finalize
- `backend/app/services/announcement_portal_backfill.py`
  - 存量内容回填逻辑
- `backend/scripts/backfill_announcement_portal_metadata.py`
  - 生产或本地补跑入口
- `backend/tests/test_search.py`
- `backend/tests/test_premium_monitoring_hits.py`
- `backend/tests/test_announcement_portal_backfill.py`

## 4. 已验证结果

本轮代码在仓库根目录执行：

```bash
npm run test:backend
```

结果：

- `214 passed`

## 4.1 生产执行记录

已在生产机执行正式回填：

```bash
cd /root/code/kaoyan-miniapp-mvp
backend/.venv/bin/python backend/scripts/backfill_announcement_portal_metadata.py --overwrite
```

执行结果：

- `scanned=468`
- `updated=468`
- `matched=438`
- `skipped_no_section=30`
- `inferred_without_section=28`

执行后已验证：

- `http://127.0.0.1:8000/api/v1/health`
- `https://api.gewujl.cloud/api/v1/health`

均返回：

- `status=ok`
- `db=up`
- `redis=down`

其中 `redis=down` 是当前系统的既有降级状态，不是本轮回填引入的新问题。

## 5. 上线后建议做的事情

### 5.1 先做一次存量回填

这轮逻辑不仅影响新入库内容，也影响旧公告是否应该继续可见。生产已经完成一次全量 `--overwrite` 回填；如果后续继续调整规则，建议先做 dry-run，再决定是否重新覆盖：

```bash
cd /root/code/kaoyan-miniapp-mvp
./.venv/bin/python backend/scripts/backfill_announcement_portal_metadata.py --overwrite --dry-run
```

如果 dry-run 结果符合预期，再执行：

```bash
cd /root/code/kaoyan-miniapp-mvp
./.venv/bin/python backend/scripts/backfill_announcement_portal_metadata.py --overwrite
```

如果担心一次性覆盖过大，可以先按学校分批：

```bash
./.venv/bin/python backend/scripts/backfill_announcement_portal_metadata.py --school-name 某大学 --overwrite
```

### 5.2 线上人工 spot check

建议上线后至少人工抽查这三类数据：

1. 学校级研招站核心栏目
2. 学院通知栏目
3. 明显不是研招的普通新闻/行政公开页

重点确认：

- 学校级公告仍可搜索到
- 院系栏目监控 target 还能命中
- 普通历史新闻不会再混进公告检索和监控

## 6. 后续 AI 继续开发时的优先顺序

### 优先级 A：把规则从启发式推进到“可运营治理”

- 给后台增加“为什么这条被判定为可见/不可见”的解释字段。
- 给 backfill 或搜索面板补统计：
  - `core`
  - `supplemental`
  - `hidden_non_admissions_history`
- 给管理员一个批量抽样复核入口，减少纯规则黑盒。

### 优先级 B：把门户判定和栏目资产治理打通

- 当前仍是：
  - `site_section` 有证据时优先信资产
  - 没资产时退化到 URL/文本启发式
- 下一步可以把“推断命中的无栏目历史页”反向沉淀成治理候选资产，减少长期启发式漂移。

### 优先级 C：继续收紧误判

- 现在已拦截一批负向语义，但仍可能存在：
  - 新闻稿引用历史研招政策
  - 普通报道里提到复试/录取关键词
  - 非研招二级站 URL 恰好命中 `admission` / `graduate`
- 继续优化时，优先补测试，再改规则。

## 7. 给下一位 AI 的工作方式建议

接手时先读：

1. `docs/plan.md`
2. `docs/current_status_2026-03-18.md`
3. `docs/backend_and_crawler.md`
4. 本文档

接着执行：

```bash
git pull --ff-only origin main
npm run test:backend
```

如果要继续这一块，优先看：

- `backend/app/services/announcement_portal.py`
- `backend/app/services/content.py`
- `backend/app/routers/search.py`
- `backend/app/services/premium_monitoring.py`

## 8. 当前判断

这一轮已经把“明显错误的可见性放行”和“栏目 scope 丢失”这两个会直接影响搜索质量与会员监控命中的问题收住了。

还没有完成的不是代码正确性，而是运营层面的数据治理：

- 旧数据仍需要 backfill 重新分类
- 重点学校还需要人工抽样验证
- 后台还缺解释性和治理面板

## 9. 2026-03-26 follow-up

- The follow-up governance surface is now in place for announcements:
  - `GET /api/v1/admin/workflows`
  - `GET /api/v1/admin/workflows/{id}`
  - Admin UI workspace for workflow list/detail, bootstrap/rebuild, and content explain/reclassify
- Announcement runtime has been tightened further:
  - legal runtime entrypoints are now V2 workflows plus the legacy `family_discovery` handoff shell
  - announcement `retry-parse` runs through V2 `file_parse`
  - monitoring / notification surfaces consume persisted `content_classifications` only
- Remaining work after this handoff is operational rather than architectural:
  - manual smoke on the admin governance workspace
  - deployment / production data backfill when explicitly scheduled

## 10. 2026-03-27 CHSI foundation fanout update

- `announcement_catalog_refresh` no longer keeps CHSI school enrich inside one long `fetch_chsi_school_catalog` step.
- The CHSI phase now runs as:
  - `fetch_chsi_school_catalog`
  - `enqueue_chsi_school_enrich`
  - `enrich_chsi_school_snapshot` (per school)
  - `await_chsi_school_enrich`
  - `fetch_chsi_major_catalog`
- `await_chsi_school_enrich` is the only step that writes `school_catalog_snapshot.json`.
- Workflow detail for the barrier now surfaces `total_school_count`, `succeeded_school_count`, `failed_school_count`, `pending_school_count`, and `failed_schools`.
- If any per-school CHSI enrich child reaches terminal failure, the workflow stops at the barrier and does not continue into major / department / merge.
