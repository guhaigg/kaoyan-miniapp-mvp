# 服务器版本记录（2026-03-17）

> Legacy note (2026-03-18):
> This record describes the older static-site release flow based on `infra/nginx/*`.
> It is kept only as historical context.
> The current production web deploy must use `web-ui/out` instead of copying `infra/nginx` pages into `/var/www/html`.

## 1) 本次目标

- 将当前线上可用版本的页面与后台静态文件回收进仓库。
- 修复“查询入口 -> 返回主页”时偶发未渲染过渡态。
- 统一品牌标识：`GW` 图标、`GeWuJian` 文案、站点 favicon。

## 2) 已同步文件

### Web（Nginx 静态目录）

- `infra/nginx/index.html`
- `infra/nginx/register.html`
- `infra/nginx/query/index.html`
- `infra/nginx/about/index.html`
- `infra/nginx/assets/brand/gw-mark.svg`
- `infra/nginx/assets/brand/gw-app-shell.js`

### Backend 管理台静态资源

- `backend/app/static/console/admin.html`
- `backend/app/static/console/admin.css`
- `backend/app/static/console/admin.js`
- `backend/app/static/console/gw-mark.svg`

## 3) 关键改动说明

- 采用「MPA + Swup」混合架构：`/query` 与 `/register` 并入 `#swup-container` 转场容器。
- 新增 `gw-app-shell.js`，在 `swup:pageView` 生命周期重新挂载页面逻辑，避免事件丢失和重复绑定。
- 移除首页对 `/query`、`/register` 的强制整页跳转拦截，交由 Swup 接管无缝转场。
- 首页、查询页、注册页、管理员页统一切换为 GW favicon。
- 增加全站 `pageshow` 回退保护，处理 BFCache 返回导致的未渲染态。
- 查询页品牌文字统一为 `GeWuJian`，保留 Twilight 版式。

## 4) 线上校验结果

以下接口均返回 200：

- `https://example.com`
- `https://example.com/query/`
- `https://example.com/register/`
- `https://api.example.com/admin/`
- `https://example.com/assets/brand/gw-mark.svg`
- `https://api.example.com/static/console/gw-mark.svg`

## 5) 发布/同步命令（参考）

```bash
scp infra/nginx/index.html <deploy-user>@<server-ip>:/var/www/html/index.html
scp infra/nginx/register.html <deploy-user>@<server-ip>:/var/www/html/register.html
scp infra/nginx/register.html <deploy-user>@<server-ip>:/var/www/html/register/index.html
scp infra/nginx/query/index.html <deploy-user>@<server-ip>:/var/www/html/query/index.html
scp infra/nginx/about/index.html <deploy-user>@<server-ip>:/var/www/html/about/index.html
scp infra/nginx/assets/brand/gw-mark.svg <deploy-user>@<server-ip>:/var/www/html/assets/brand/gw-mark.svg
scp infra/nginx/assets/brand/gw-app-shell.js <deploy-user>@<server-ip>:/var/www/html/assets/brand/gw-app-shell.js

scp backend/app/static/console/admin.html <deploy-user>@<server-ip>:/srv/kaoyan-miniapp-mvp/backend/app/static/console/admin.html
scp backend/app/static/console/admin.css <deploy-user>@<server-ip>:/srv/kaoyan-miniapp-mvp/backend/app/static/console/admin.css
scp backend/app/static/console/admin.js <deploy-user>@<server-ip>:/srv/kaoyan-miniapp-mvp/backend/app/static/console/admin.js
scp backend/app/static/console/gw-mark.svg <deploy-user>@<server-ip>:/srv/kaoyan-miniapp-mvp/backend/app/static/console/gw-mark.svg
```

## 6) 回滚建议

- Web 静态页回滚：恢复 `/var/www/html` 下对应文件的 `.bak` 或上一版文件。
- 管理台回滚：恢复 `/srv/kaoyan-miniapp-mvp/backend/app/static/console` 的上一版文件后重启后端服务。
- 回滚后务必复查：
  - `/api/v1/health`
  - `https://example.com/query/` 页面返回链路
  - `https://api.example.com/admin/` 登录页可访问
