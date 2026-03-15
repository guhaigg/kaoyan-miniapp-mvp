# Handover Status (2026-03-15)

## 当前阶段
- 阶段定位：Week 4 验收完成，进入“测试版联调”阶段。
- 当前主分支策略：`dev` 持续集成，`main` 仅通过 PR 合并。

## 已完成（可直接复用）
- 新仓库已完成基础架构：微信小程序 + FastAPI + Redis + MySQL 兼容。
- 核心 API 已落地：`silent-login`、公告查询、调剂查询、内容入库、后台录入、院校联想、健康检查。
- 异步补抓链路已落地：`refresh=true -> crawl_jobs -> worker 消费 -> jobs 轮询`。
- Alembic 迁移已接入，远程 MySQL 验证通过。
- Week 4 首批 20 所院校源已可导入并验证。
- 文档体系已放在 `docs/`（Docs as Code）。

## 已验证结果
- 后端单测：`python -m pytest -q` -> `5 passed`。
- 测试版冒烟脚本：`npm run smoke:test-version` 通过。
- 远程库链路验证通过（含 job 入队、worker 消费、状态回写）。

## 本次新增（用于跨电脑接手）
- 一键冒烟脚本：`backend/scripts/smoke_test_version.py`
- NPM 命令：`smoke:test-version`
- 部署/联调文档补全：远程 MySQL URL、密码 URL 编码、测试版冒烟流程。

## 换电脑后最短恢复步骤
1. 克隆仓库并切到 `dev`
2. 配置 `backend/.env`（或使用环境变量）
3. 安装依赖并迁移数据库
4. 执行后端测试 + 冒烟脚本

```bash
git clone https://github.com/guhaigg/kaoyan-miniapp-mvp.git
cd kaoyan-miniapp-mvp
git checkout dev
npm install
cd backend
pip install -r requirements.txt
python -m alembic upgrade head
python -m pytest -q
cd ..
npm run smoke:test-version
```

## 下一步建议
- 接入正式微信配置（`USE_MOCK_WECHAT=false`）做提审前联调。
- 服务器侧完成 Nginx + HTTPS + 小程序合法域名白名单。
- 发起 `dev -> main` PR，进入小范围内测。
