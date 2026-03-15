# New PC Bootstrap (10 Minutes)

## 目标
- 在新电脑快速恢复 `kaoyan-miniapp-mvp` 开发环境。
- 使用本地开发 + 远程 MySQL（腾讯云）模式。

## 1) 安装基础工具（Windows）
- Git
- Node.js 18+
- Python 3.10+（已验证 3.14 也可运行当前项目）
- WeChat DevTools（调试小程序）

## 2) 拉取代码并切分支

```bash
git clone https://github.com/guhaigg/kaoyan-miniapp-mvp.git
cd kaoyan-miniapp-mvp
git checkout dev
```

## 3) 安装依赖

```bash
npm install
cd backend
pip install -r requirements.txt
cd ..
```

## 4) 配置远程数据库环境变量（PowerShell 示例）

> 注意：密码中 `@`、`!` 等字符必须 URL 编码（例如 `@` -> `%40`, `!` -> `%21`）

```powershell
$env:DATABASE_URL='mysql+pymysql://kaoyan_app:<URLENCODED_PASSWORD>@sh-cynosdbmysql-grp-6d5yzec2.sql.tencentcdb.com:26017/gwj001-7gnogq6td6fcd69f?charset=utf8mb4'
$env:USE_MOCK_WECHAT='true'
$env:WECHAT_APPID='mock'
$env:WECHAT_SECRET='mock'
$env:SECRET_KEY='dev-secret-local'
$env:AUTO_CREATE_TABLES='false'
```

## 5) 执行迁移与测试

```bash
npm run db:migrate
npm run test:backend
npm run smoke:test-version
```

预期：
- 单测通过（当前基线：`5 passed`）
- 冒烟脚本通过（health/silent-login/refresh/job/worker 链路通过）

## 6) 启动本地后端

```bash
npm run dev:backend
```

后端默认地址：
- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/docs`

## 7) 启动小程序联调
- 用 WeChat DevTools 打开 `miniapp/`
- 确认请求地址指向本机后端或你的服务器域名

## 8) 常用命令速查

```bash
npm run dev:backend
npm run test:backend
npm run db:migrate
npm run smoke:test-version
```

## 9) 异常排查
- `Can't connect to MySQL`：
  - 检查 IP 白名单/安全组
  - 检查 `DATABASE_URL` 是否 URL 编码密码
- `silent-login 400`：
  - 开发阶段可先用 `USE_MOCK_WECHAT=true`
- `refresh job created but contents=0`：
  - 先确认 `sources` 已导入并启用
