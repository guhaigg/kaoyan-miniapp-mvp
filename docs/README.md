# 格物简录文档总览

这份索引只做一件事：告诉你现在该看哪几份文档，哪些是长期有效，哪些只是阶段性记录。

当前结论：

- `docs/` 里文档确实偏多
- 但不是都同一层级
- 以后默认只看“当前有效文档”
- 旧阶段记录和一次性材料，统一按“历史/归档”处理，不再当主入口

## 1. 先读这 5 份

如果你刚接手项目，先读下面 5 份，足够建立当前全局认识：

1. [主路线图](./plan.md)
2. [当前进度（2026-03-18，最近更新到 2026-03-19）](./current_status_2026-03-18.md)
3. [注册登录架构（Portal 用户）](./auth_login_architecture.md)
4. [Backend and Crawler Spec](./backend_and_crawler.md)
5. [Deployment Handbook](./deployment.md)

## 2. 当前有效文档

这组文档默认视为当前 source of truth。

### 2.1 项目现状

- [主路线图](./plan.md)
- [当前进度（2026-03-18，最近更新到 2026-03-19）](./current_status_2026-03-18.md)
- [账号体系总结（2026-03-18）](./account_system_summary_2026-03-18.md)

### 2.2 核心架构

- [注册登录架构（Portal 用户）](./auth_login_architecture.md)
- [Backend and Crawler Spec](./backend_and_crawler.md)
- [通知实时链路（Outbox + SSE）](./notification_realtime_architecture_2026-03-17.md)
- [高校官网发现与公告情报管线方案（2026-03-18）](./school_notice_discovery_pipeline_2026-03-18.md)

### 2.3 开发与发布

- [Development Protocol](./development_protocol.md)
- [Git Workflow and Release Rules](./git_workflow.md)
- [Deployment Handbook](./deployment.md)
- [Release and Rollback Checklist（2026-03-18）](./release_and_rollback_checklist_2026-03-18.md)
- [服务器目录与部署路径说明（2026-03-19）](./server_layout_and_deploy_paths_2026-03-19.md)

### 2.4 账号与会员专题

- [账号体系过渡与上线实施方案（2026-03-18）](./account_system_transition_plan_2026-03-18.md)
- [账号体系总结（2026-03-18）](./account_system_summary_2026-03-18.md)
- [高级院校公告监控功能需求（2026-03-18）](./premium_monitoring_requirements_2026-03-18.md)

### 2.5 验收与目标清单

- [Miniapp Smoke Checklist（2026-03-18）](./miniapp_smoke_checklist_2026-03-18.md)
- [首批重点学校/学院清单（2026-03-18）](./priority_school_targets_2026-03-18.md)
- [priority_school_targets_2026-03-18.json](./priority_school_targets_2026-03-18.json)

### 2.6 数据库变更

- [`docs/sql/`](./sql/)

## 3. 条件性文档

这组文档不是所有人都需要看，按场景读取。

- [Frontend and Design Spec](./frontend_and_design.md)
  - 适合改 UI、miniapp 页面、视觉规范时看
- [Web UI 接口对齐说明（2026-03-17）](./web_ui_api_alignment_2026-03-17.md)
  - 适合核对 Web UI 与接口对接范围时看
- [账号体系过渡与上线实施方案（2026-03-18）](./account_system_transition_plan_2026-03-18.md)
  - 适合继续做微信接入、支付回调和遗留清理时看

## 4. 历史/归档文档

这组文档保留是为了追溯，不建议作为当前开发入口。

- [服务器版本记录（2026-03-17）](./archive/server_release_2026-03-17.md)
- [AI 协作工作流与近期执行计划（2026-03-18）](./archive/ai_workflow_and_execution_plan_2026-03-18.md)
- [UI Rebuild Execution Baseline](./archive/ui_rebuild_execution_baseline.md)
- [Website UI Backup (2026-03-17)](./archive/ui_backup_2026-03-17.md)
- [Ubuntu 全新环境部署 Clash（Mihomo）代理指南](./archive/ubuntu_clash_proxy_deploy.md)
- [Development Plan](./plan.md)
- [Claude Quickstart](./archive/claude_quickstart.md)

说明：

- 这些文档没有删除，因为里面仍有追溯价值
- 但默认不再作为“先读材料”

## 5. 当前项目的文档分工

为避免以后继续堆文档，按下面规则处理：

- `README.md`
  - 只做索引，不重复写实现细节
- `plan.md`
  - 当前唯一主路线图，负责阶段目标、缺口与执行顺序
- `current_status_*.md`
  - 只保留一份当前现状主文档，持续更新
- `*_architecture.md` / `*_spec.md`
  - 只写长期有效的结构与约束
- `*_checklist.md`
  - 只写可执行清单
- 带日期的临时总结、备份、阶段计划
  - 默认视为阶段性材料
  - 不进入“先读”列表

## 6. 当前推荐阅读路径

### 路径 A：继续开发功能

1. [主路线图](./plan.md)
2. [当前进度](./current_status_2026-03-18.md)
3. [注册登录架构](./auth_login_architecture.md)
4. [Backend and Crawler Spec](./backend_and_crawler.md)
5. 对应专题文档

### 路径 B：准备上线或排障

1. [Deployment Handbook](./deployment.md)
2. [Release and Rollback Checklist](./release_and_rollback_checklist_2026-03-18.md)
3. [服务器目录与部署路径说明](./server_layout_and_deploy_paths_2026-03-19.md)

### 路径 C：继续做账号/会员/微信

1. [账号体系总结](./account_system_summary_2026-03-18.md)
2. [注册登录架构](./auth_login_architecture.md)
3. [账号体系过渡与上线实施方案](./account_system_transition_plan_2026-03-18.md)
