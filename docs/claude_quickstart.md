# Claude Quickstart

这份文档用于在 `格物简录` 项目里快速上手 Claude Code。

## 1. 启动方式

推荐在项目根目录启动：

```bash
claude
```

你本机已经配置过自动行为：

- 在 `~` 目录直接输入 `claude`，会自动切到项目目录
- 也可以使用：

```bash
gwproj
gwclaude
Claude
```

当前默认配置：

- Base URL: `https://api.longcat.chat/anthropic`
- Model: `LongCat-Flash-Thinking-2601`
- 认证方式：`ANTHROPIC_AUTH_TOKEN`
- 已禁用网页登录

## 2. 开始前建议

进入仓库后，先让 Claude 读规则：

```text
请先阅读 AGENTS.md、CLAUDE.md、docs/development_protocol.md，再开始工作
```

如果是第一次在当前仓库使用 Claude，建议先执行：

```text
/init
```

如果当前仓库已经有 `CLAUDE.md`，优先遵守现有文件，不要重复生成冲突规则。

## 3. 最常用工作流

### 功能开发

适合需求较完整、改动较大的任务：

```text
/feature-dev
```

或者直接：

```text
/feature-dev 实现管理员数据面板接入真实接口
```

适用场景：

- 做一整块新功能
- 要先看代码结构再落实现
- 希望 Claude 先设计方案再编码

### 前端页面/交互

你已经安装了 `frontend-design`，可以直接这样说：

```text
请基于当前站点风格优化这个页面，不要重做视觉体系，只改这个模块
```

或：

```text
请设计一个符合当前 Twilight 风格的查询结果卡片
```

建议每次都明确：

- 是否允许改视觉风格
- 是否只改当前模块
- 是否要保持现有版式

### 代码评审

如果在 PR 分支或需要自查：

```text
/code-review
```

适合：

- 提交前自查
- 评估风险点
- 看看有没有遗漏的 bug / 回归

### 提交代码

你已经安装了 `commit-commands`，可以直接用：

```text
/commit
```

或者整套：

```text
/commit-push-pr
```

注意：

- 仓库规范默认不建议日常开发直接在 `main`
- 但如果你明确要求在 `main` 热修，Claude 也能执行

## 4. 项目里最有用的命令/说法

### 让 Claude 先理解代码

```text
先读一遍这个模块相关代码，再告诉我当前实现、缺点和下一步建议
```

### 让 Claude 只做最小改动

```text
只做最小补丁，不要顺手重构别的模块
```

### 让 Claude 先提方案再改

```text
先给我 2 个方案，确认后再动代码
```

### 让 Claude 更新文档

```text
改完代码后，同步更新 README 和相关 docs
```

### 让 Claude 带验证

```text
改完后请自己运行相关 lint / build / test，再给我总结
```

## 5. 当前仓库推荐验证命令

### 后端

```bash
npm run test:backend
```

### Web UI

```bash
cd web-ui
npm run lint
npm run build
```

### 本地后端开发

```bash
npm run dev:backend
```

## 6. 常见任务模板

### 模板 A：做功能

```text
请先阅读 AGENTS.md、CLAUDE.md 和 docs/development_protocol.md，然后实现这个需求。
要求：
1. 先理解相关代码
2. 只改必要文件
3. 改完运行相关验证
4. 最后更新文档并总结
```

### 模板 B：改前端但不允许乱改

```text
请在保留当前设计语言的前提下优化这个页面。
不要重做整体风格，不要改无关模块，只处理当前页面。
改完请跑 web-ui 的 lint 和 build。
```

### 模板 C：查线上问题

```text
请先定位问题根因，再给出最小修复方案。不要先大改。
如果涉及部署，请顺手帮我完成验证。
```

### 模板 D：让 Claude 帮你收尾

```text
请检查这次改动是否需要补 README、docs、部署说明，并一起处理掉。
```

## 7. 已安装插件

当前这台机器上的 Claude 已安装：

- `frontend-design`
- `feature-dev`
- `commit-commands`
- `claude-md-management`
- `code-review`
- `security-guidance`
- `typescript-lsp`
- `pyright-lsp`
- `claude-code-setup`
- `skill-creator`

## 8. 推荐习惯

- 大任务先用 `/feature-dev`
- 前端任务明确“允许改到什么程度”
- 改完要求 Claude 自己执行验证
- 每次交付都要求总结：
  - 改了什么
  - 怎么验证
  - 还有什么风险

这样 Claude 的稳定性会明显更高。
