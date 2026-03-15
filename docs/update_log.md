# 更新文档（Update Log）

本文件用于记录所有修复与更新。  
从 `2026-03-15` 起，任何代码、配置、流程、文档变更都必须追加记录，不允许只改代码不留痕。

## 记录规则

1. 每次交付至少新增一条记录（按时间倒序）。
2. 记录必须包含：日期、分支、提交、变更摘要、验证结果、风险/后续。
3. 若有未完成验证，必须在记录中明确写出。
4. 禁止覆盖历史记录，只能追加。

## 模板

```md
## YYYY-MM-DD - <type>: <title>
- Branch: `dev` / `feat/*` / `fix/*`
- Commit: `<short-sha>`
- Summary:
  - ...
- Verification:
  - ...
- Risks / Next:
  - ...
```

## 2026-03-15 - chore: auto-clean old preview qrcodes before generation
- Branch: `dev`
- Commit: `35b0280`
- Summary:
  - 更新 `scripts/miniprogram-preview.js`：每次生成预览二维码前，自动删除同目录下历史 `miniprogram-preview*.jpg|jpeg|png` 文件。
  - 更新冒烟文档，明确“先删旧码再生成新码”的默认行为。
- Verification:
  - `node --check scripts/miniprogram-preview.js`
  - `npm run smoke:miniapp:preview -- --help`
- Risks / Next:
  - 清理规则按文件名前缀 `miniprogram-preview` 生效，请避免将其他业务图片使用该前缀放在同目录。

## 2026-03-15 - fix: miniapp status page error visibility and request domain troubleshooting
- Branch: `dev`
- Commit: `a6fa43f`
- Summary:
  - 增强状态页：增加安全解码、错误文案复制按钮、可选中文本展示，避免报错信息不可见或不可复制。
  - 将 `miniapp/project.config.json` 的 `appid` 对齐为 `wx02ddbac747a8a137`，与当前测试私钥一致。
  - 补充冒烟文档排障项：`request:fail url not in domain list` 处理步骤。
- Verification:
  - `node --check miniapp/pages/status/index.js`
  - `npm run smoke:miniapp:preview -- --privateKeyPath .secrets/private.wx02ddbac747a8a137.key --qrcodeOutput artifacts/miniprogram-preview-fix-20260315-1746.jpg`（成功生成二维码）
- Risks / Next:
  - 真机预览仍依赖微信公众平台对当前 `appid` 完成 `request` 合法域名配置并生效。

## 2026-03-15 - fix: restore backend worker config and test compatibility
- Branch: `dev`
- Commit: `926eda1`
- Summary:
  - 补充 `beautifulsoup4` 依赖，修复 `ModuleNotFoundError: bs4`。
  - 恢复 worker 配置项：`worker_poll_interval_seconds`、`worker_max_sources_per_job`、`worker_max_items_per_source`。
  - 挂载 `/api/v1/jobs` 路由并统一微信凭据异常断言，修复测试不一致。
- Verification:
  - `npm run test:backend`（`7 passed`）。
- Risks / Next:
  - 腾讯云 PyPI 镜像对 `beautifulsoup4` 可能存在偶发同步问题；如安装失败可切换到官方源重试。

## 2026-03-15 - feat: ubuntu miniapp preview smoke workflow
- Branch: `feat/ubuntu-miniapp-smoke` -> `dev`
- Commit: `e4f2fb0`（feature）, `5c3f795`（merge to dev）
- Summary:
  - 新增 Ubuntu 可执行的小程序预览冒烟脚本与命令：`npm run smoke:miniapp:preview`。
  - 新增小程序冒烟文档 `docs/miniapp_smoke.md`，补充运行前提、参数、检查清单与排障。
  - 启用 `miniapp/app.json` 的 `lazyCodeLoading: requiredComponents`。
  - README 增加分支策略，明确默认只走 `dev`，`main` 需明确确认后才推送/合并。
- Verification:
  - `node --check scripts/miniprogram-preview.js`
  - `npm run smoke:miniapp:preview -- --help`
- Risks / Next:
  - 真正 preview 上传依赖小程序上传私钥与 IP 白名单，仍需在目标环境完成一次真机扫码冒烟。
