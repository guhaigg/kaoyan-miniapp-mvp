# 账号体系过渡与上线实施方案（2026-03-18）

本文档用于统一说明当前账号体系的真实状态、过渡期兼容策略、后期正式上线要求，以及分阶段实施顺序。

结论先行：

- 这套账号体系不能“一次性全做完再上线”。
- 正确做法是：`先兼容落地 -> 再双写双读 -> 再切主路径 -> 最后下线遗留表`。
- 当前仓库已经完成 `Phase 1`：主账号不变，新增身份/角色/权益表，并接入兼容读写。

## 1. 业务目标

上线后的账号体系要满足 4 个约束：

1. 一个真实用户只有一个主账号。
2. 网站登录和微信小程序登录最终落到同一个主账号。
3. 管理员只是少数固定账号拥有的角色，不是另一套平行账号体系。
4. 高级会员是权益，不是账号类型，且网站和微信要同步生效。

## 2. 当前状态

当前仓库历史上存在 3 套概念：

### 2.1 `users`

- 用途：微信静默登录的影子用户
- 问题：不适合作为正式业务主账号
- 结论：后续只保留兼容用途，最终退出主链路

### 2.2 `portal_users`

- 用途：网站正式注册用户
- 当前已经承载：
  - 登录
  - 会话
  - 订阅
  - 监控目标
  - 监控命中
  - Bark 配置
- 结论：继续作为主账号表，不新建第二个主用户表

### 2.3 `admin_accounts` + `premium_*`

- `admin_accounts`：管理员角色的旧实现
- `portal_users.premium_monitoring_enabled / premium_expires_at`：高级会员的旧实现
- 问题：
  - 登录身份、角色、会员权益耦合在一起
  - 不利于接微信绑定
  - 不利于会员支付、赠送、续费留痕

## 3. 目标模型

最终目标模型如下：

### 3.1 主账号

- 表：`portal_users`
- 角色：唯一主账号
- 原则：所有业务数据都挂 `portal_users.id`

### 3.2 登录身份

- 表：`account_identities`
- 作用：把“怎么登录”从主账号里拆出去

当前计划支持：

- `password`
- `wechat_miniapp`

典型场景：

- 网站用户名密码登录
- 小程序微信登录
- 一个主账号绑定多个身份

### 3.3 角色

- 表：`account_roles`
- 当前核心角色：`admin`

设计原则：

- 管理员是角色，不是另一类用户
- 日常管理只认 `account_roles`
- `.env` 里的管理员口令仅保留为救援路径

### 3.4 权益

- 表：`account_entitlements`
- 当前核心权益：`premium_monitoring`

设计原则：

- 高级会员是权益
- 要能表达：
  - 网站购买
  - 微信支付
  - 管理员赠送
  - 到期失效
  - 撤销

## 4. 过渡原则

过渡期必须遵守下面 4 条规则：

1. 不迁移 `portal_users` 外键主线  
原因：当前大量业务表已经绑定 `portal_users.id`，强切主表风险过高。

2. 新表先加，老字段先不删  
原因：需要给生产灰度、数据回填和回滚留空间。

3. 先双读，再双写，最后切主路径  
原因：先看新表是否稳定，再让写流量进入新模型。

4. `users` 不再扩展新业务  
原因：微信影子用户只能继续兼容，不能再承载正式能力。

## 5. 分阶段实施

## 5.1 Phase 0：现状保底

目标：

- 保证网站登录、管理员、会员、订阅、监控都还能运行
- 不引入大规模外键迁移

完成标准：

- 原链路不退化
- 可以接受生产回填

状态：

- 已完成

## 5.2 Phase 1：新模型落表并接入兼容层

目标：

- 新增：
  - `account_identities`
  - `account_roles`
  - `account_entitlements`
- 认证、管理员、会员权限改成新表优先读取
- 管理员提权/降级改成新旧双写

已完成内容：

- 注册时自动写 `account_identities(password)`
- 网站登录优先从 `account_identities(password)` 识别
- `/auth/me` 的 `is_admin / is_premium / role` 改为：
  - `account_roles / account_entitlements` 优先
  - 旧表/旧字段回退
- 管理员升降级同步写：
  - `account_roles`
  - `account_entitlements`
  - 历史 `admin_accounts`
  - 历史 `premium_*`
- 已提供迁移 SQL 和回填脚本

上线门槛：

- 后端全量测试通过
- 生产新表创建成功
- 历史回填成功

状态：

- 已完成

## 5.3 Phase 2：网站账号主路径正式切换

目标：

- 所有网站登录相关逻辑都只以 `account_identities(password)` 为准
- `portal_users.username/password_hash` 从“主来源”降为“兼容影子字段”

需要做的事：

1. 后台用户列表和用户编辑接口增加身份视图
2. 密码修改、重置、封禁全部改为操作 `account_identities`
3. 管理员后台展示：
   - 主账号
   - 登录身份
   - 角色
   - 权益

上线门槛：

- 网站所有登录、换密、管理员登录路径只走新身份表
- 不再依赖 `portal_users.username` 作为唯一身份来源

状态：

- 已完成

## 5.4 Phase 3：微信绑定与小程序登录接入

目标：

- 小程序正式登录不再只生成 `users shadow`
- 改为落 `account_identities(wechat_miniapp)`

需要做的事：

1. 新增微信身份绑定流程
   - 已登录网站账号后绑定微信
   - 或首次微信登录后创建主账号
2. 支持 `openid` / `unionid` 绑定
3. 小程序与网站共享：
   - 收藏
   - 监控目标
   - 会员权益
   - 通知状态

上线门槛：

- 网站与微信登录都能命中同一个 `portal_users.id`

状态：
- 服务端已完成，客户端补齐延后
- 已完成：
  - 小程序静默登录命中已绑定身份后，直接切主账号会话
  - 小程序支持“网站账号密码绑定”
  - 网站端支持生成短期微信绑定码
  - 小程序支持“使用绑定码绑定”
- 保留接口位置：
  - `POST /api/v1/auth/wechat/bind`
  - `POST /api/v1/auth/wechat/bind-code`
  - `POST /api/v1/auth/wechat/bind-code/claim`
- 未完成：
  - `unionid` 归并
  - 微信首次登录直接创建主账号
  - 解绑/换绑
  - 小程序正式发布与客户端收口

已完成内容：

- `POST /api/v1/auth/wechat/bind`
  - 要求同时具备：
    - `X-Visitor-Token`（微信静默登录影子身份）
    - `X-User-Token / Authorization: Bearer ...`（网站主账号）
  - 成功后写入 `account_identities(wechat_miniapp)`
- `POST /api/v1/auth/silent-login`
  - 未绑定时仍返回 `shadow` 模式，保留兼容
  - 已绑定时直接返回主账号 `access_token / refresh_token`
- 小程序全局状态已支持：
  - `visitorToken`
  - `userAccessToken`
  - `userRefreshToken`
  - `linkedPortalUserId`
  - `authMode=portal_bound`

未完成内容：

- 小程序侧正式绑定/登录 UI 入口
- 使用 `unionid` 做跨 app 归并
- 首次微信登录直接创建主账号
- 网站页面上的微信绑定入口

## 5.5 Phase 4：会员支付与权益结算

目标：

- 高级会员完全切到 `account_entitlements`

需要做的事：

1. 增加支付来源字段使用规范
   - `web_pay`
   - `wechat_pay`
   - `admin_grant`
   - `migration`
2. 增加会员订单/支付单对接
3. 续费、赠送、到期、撤销全留痕
4. 下游权限判断不再依赖 `premium_*` 旧字段

上线门槛：

- 会员跨端同步
- 会员状态完全由权益表驱动

状态：
- 已完成

已完成内容：

1. 权限判定只认 `account_entitlements`
2. 新增 `account_payment_orders`
3. 网站用户可创建会员订单并查看订单历史
4. 管理侧可创建订单、查看订单账本并确认支付
5. 订单支付完成后，自动发放 `premium_monitoring`
6. 权益记录保留：
   - `source`
   - `order_ref`
   - `starts_at / expires_at / revoked_at`
7. 已保留支付来源规范：
   - `web_pay`
   - `wechat_pay`
   - `admin_grant`
   - `migration`

说明：

- 当前实现采用“订单/支付单 -> 权益发放”的内部账本模型。
- 外部第三方支付网关仍可后续接入，不影响当前账号体系主路径。
- 微信支付仅预留 `source=wechat_pay` 和对应接口位置，不阻塞网站侧账号体系完成。

## 5.6 Phase 5：遗留表收尾

目标：

- 下线遗留设计

计划清理对象：

- `admin_accounts`
- `portal_users.premium_monitoring_enabled`
- `portal_users.premium_expires_at`
- `users` 影子用户主路径

前置条件：

- 微信登录已稳定接入身份表
- 会员支付已切到权益表
- 管理员角色已完全切到 `account_roles`

状态：
- 已完成（运行时）

已完成内容：

1. 管理员角色运行时只认 `account_roles`
2. 高级会员运行时只认 `account_entitlements`
3. `admin_accounts`、`portal_users.premium_*` 不再参与权限判定
4. 已补回归测试，确保旧字段即使存在也不会继续放权

说明：

- 当前代码已经完成运行时切换。
- 物理清理 DDL 已补齐：
  - `docs/sql/2026-03-18_drop_legacy_account_auth_mysql.sql`
  - `docs/sql/2026-03-18_drop_legacy_account_auth_sqlite.sql`
- 物理清理范围：
  - `admin_accounts`
  - `portal_users.premium_monitoring_enabled`
  - `portal_users.premium_expires_at`
- `users` 微信影子表暂不物理删除，因为小程序接口位置仍保留。

## 6. 当前推荐实施顺序

不要并行硬推所有阶段。建议严格按下面顺序推进：

1. `Phase 1` 先上线并稳定观察
2. 做 `Phase 2`，把网站账号真正切到身份表
3. 再做 `Phase 3`，接微信绑定与登录
4. 再做 `Phase 4`，把会员支付正式接进来
5. 最后再做 `Phase 5` 清遗留

## 7. 当前仓库与生产的实际状态

截至 2026-03-18：

- 本地代码已完成 `Phase 1` ~ `Phase 5`（微信客户端只保留接口位置）
- 生产已完成：
  - 新表创建
  - 历史回填
  - 运行时切换到 `identities / roles / entitlements / payment_orders`
  - 网站侧账号总览、改密、通知历史、会员订单、管理员订单账本上线
  - 遗留管理员表/旧会员列进入物理清理阶段

已知现实：

- 生产管理员账号目前仍以少数 `portal_users` 为主
- `.env` 中的 `ADMIN_USERNAME/ADMIN_PASSWORD` 仍存在
- 当前它应被视为救援通道，而不是长期主账号模型

## 8. 对外上线要求

后期正式上线前，账号体系必须满足以下验收项：

1. 网站注册用户可以绑定微信
2. 微信登录用户可以补全网站登录方式
3. 管理员角色只认 `account_roles`
4. 高级会员只认 `account_entitlements`
5. 网站和微信的收藏、监控、通知、会员完全同步
6. 救援口令不参与日常权限判定

## 9. 当前结论

这件事不能追求“全做完再一次性交付”。  
正确的工程节奏是：

- 先把数据模型搭对
- 再把读写路径渐进切换
- 最后再删旧逻辑

当前已经完成的是“搭对模型并接上兼容层”。  
后面真正影响产品上线质量的，是：

- 网站身份表主路径切换
- 微信绑定
- 会员权益支付接入
