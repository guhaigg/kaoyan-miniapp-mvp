# 账号体系总结（2026-03-18）

## 1. 当前终态

网站侧账号体系已经完成切换，当前生产主路径如下：

- 主账号：`portal_users`
- 登录身份：`account_identities`
- 管理员角色：`account_roles`
- 会员权益：`account_entitlements`
- 会员订单账本：`account_payment_orders`

运行时权限判定：

- 管理员只认 `account_roles(role_code=admin)`
- 高级会员只认 `account_entitlements(entitlement_code=premium_monitoring)`

已物理删除的遗留对象：

- `admin_accounts`
- `portal_users.premium_monitoring_enabled`
- `portal_users.premium_expires_at`

暂时保留：

- `users` 微信影子表
- 微信绑定相关接口与服务端逻辑

保留原因：

- 小程序客户端还没有作为正式发布路径收口
- 后续仍需要 `shadow -> 主账号绑定` 这条兼容链路

## 2. 网站侧已经完成的能力

用户侧：

- 注册 / 登录 / 刷新 / 登出
- 账号总览
- 身份列表查看
- 角色与权益查看
- 自助修改密码
- 最近通知历史查看
- 会员订单创建
- 会员订单历史查看
- 网站端微信绑定码生成

管理侧：

- 管理员门禁
- 管理员二次登录
- 用户提权 / 降级
- 用户密码重置
- 角色 / 身份 / 权益查看
- 会员订单账本查看
- 手动创建会员订单
- 手动确认支付并发放权益

## 3. 当前支付模型

当前使用内部账本模型：

- 用户或管理员先创建 `account_payment_orders`
- 订单确认支付后，发放 `account_entitlements`
- 运行时永远只读 entitlement，不直接读 order

这套模型后续可以平滑接：

- 网站支付
- 微信支付
- 管理员赠送

而不需要再改账号主模型。

## 4. 微信当前状态

服务端接口已保留：

- `POST /api/v1/auth/silent-login`
- `POST /api/v1/auth/wechat/bind`
- `POST /api/v1/auth/wechat/bind-code`
- `POST /api/v1/auth/wechat/bind-code/claim`

当前未做完的部分：

- `unionid` 归并
- 首次微信登录直接创建主账号
- 解绑 / 换绑
- 小程序正式客户端发布收口

## 5. 结论

账号体系这条线，网站侧已经可以认为完成。

后续如果继续推进，优先级应当是：

1. 微信客户端正式接入
2. 第三方支付回调接 `account_payment_orders`
3. 微信 `unionid` 归并
4. 最终评估是否删除 `users` 影子表
