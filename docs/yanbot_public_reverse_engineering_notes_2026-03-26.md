# yanbot 公开侧拆解与可借鉴点（2026-03-26）

本文档记录对 `https://h5.yanbot.tech` / `https://api.yanbot.tech` 公开可见部分的逆向观察，目的不是复刻对方产品，而是提炼三类信息：

- 这个网站大概率是怎么组织抓取、清洗和展示链路的
- 它们可能是怎么拿到院校/频道入口的
- 对 `格物简录` 当前公告主链路，哪些做法值得借鉴，哪些不建议照抄

重要边界：

- 本文只基于公开页面、公开前端 bundle、公开接口命名和页面行为推断。
- 没有拿到对方后端源码、数据库结构、worker 代码、管理后台源码。
- 因此本文会明确区分：
  - `已确认`
  - `高概率推断`
  - `当前看不出来`

## 1. 结论先行

如果只用一句话总结：

- `yanbot` 不是“前端在微信里临时爬学校官网”，而是“后端先抓取并清洗成统一内容层，再按业务需要派生结构化层，前端只消费自己的 API”。

对我们最值得借鉴的不是某个选择器写法，而是这套分层：

1. 原始来源/快照层
2. 统一正文内容层
3. 业务结构化层
4. 站内详情页与外链原文双通道

对我们当前阶段最有价值的借鉴点是：

- 公告先做稳定的“站内可读正文层”
- 原文链接必须保留
- 正文抽取和结构化抽取解耦
- 源站入口至少保留一层可人工治理的资产，而不是幻想全自动发现全国院校官网

## 2. 已确认的公开事实

### 2.1 这是一个微信体系优先的 H5

- 页面加载了微信 JS SDK：`https://res.wx.qq.com/open/js/jweixin-1.6.0.js`
- 登录相关调用走 `/wx/userInfo`
- 未登录或 token 失效时，页面会自动尝试 refresh token 登录，并弹微信登录提示

公开入口：

- [首页 HTML](https://h5.yanbot.tech/home)

### 2.2 首页不是直连学校官网，而是读它自己的 API

首页网络请求里可见：

- `GET https://api.yanbot.tech/feedList`
- `GET https://api.yanbot.tech/feedList/subscribed`
- `GET https://api.yanbot.tech/transfer-data/list`
- `GET https://api.yanbot.tech/config_json/configs?...`

这说明首页的资讯流和调剂列表都不是前端现抓学校网页，而是后端已经准备好的数据。

相关公开证据：

- [首页 HTML](https://h5.yanbot.tech/home)
- [home bundle](https://h5.yanbot.tech/assets/home-index-7GSVToYg.js)
- [transfer api bundle](https://h5.yanbot.tech/assets/transfer-DaSiHSwt.js)

### 2.3 它们有“统一正文层”

`feed` 相关公开接口能看出：

- `GET /feedList`
- `GET /feedList/subscribed`
- `GET /feed/:feedId`

而 `feed` 详情页前端会直接渲染：

- `feed.title`
- `feed.content`
- `feed.contentSummary`
- `feed.link`

其中 `feed.content` 是直接 `innerHTML` 渲染的，这意味着它们大概率把清洗后的正文 HTML 存到了后端，而不是每次详情页都跳原网站。

相关公开证据：

- [feed api bundle](https://h5.yanbot.tech/assets/index-DpWzOaBC.js)
- [feed detail bundle](https://h5.yanbot.tech/assets/feed-detail-9RRw5Cjf.js)

### 2.4 它们有“调剂结构化层”

调剂相关公开接口能看出：

- `GET /transfer-data/list`
- `GET /transfer-data/detail/:id`

详情页里返回的数据已经是结构化字段，不是原公告正文：

- `schoolName`
- `majorName`
- `majorCode`
- `vacancy`
- `requirement`
- `note`
- `contactInfo`
- `transferSource`

而且调剂详情对象里还会挂一个 `feed`，用于回链到原文详情页。

相关公开证据：

- [transfer api bundle](https://h5.yanbot.tech/assets/transfer-DaSiHSwt.js)
- [TransferDataDetail bundle](https://h5.yanbot.tech/assets/TransferDataDetail-DieBMvmB.js)

### 2.5 “正文抓取”和“调剂结构化”是两步，不是一步

`feed` 详情页里对调剂类内容会触发：

- `GET /agent/transfer-feed-parse`

这非常像一个“把已有公告正文再解析成调剂结构化字段”的服务，而不是抓取器一次性把所有事做完。

公开证据：

- [feed detail bundle](https://h5.yanbot.tech/assets/feed-detail-9RRw5Cjf.js)

## 3. 我对它整体链路的理解

基于公开证据，我对 `yanbot` 的高概率理解如下。

### 3.1 高概率真实链路

1. 先维护学校/频道资产
2. 从频道入口页抓列表和详情
3. 把正文抽成统一 `feed`
4. 对部分 `feed` 做业务解析，生成 `transfer-data`
5. 前端列表页读结构化数据
6. 详情页既能站内看正文，也保留外链“查看原文”

### 3.2 对应的数据分层

高概率至少有三层：

- `source/task/channel`
  - 学校、频道、原始入口 URL、频道配置
- `feed`
  - 统一资讯/公告正文层
- `transfer-data`
  - 从 `feed` 派生出的调剂结构化层

这套分层带来的好处是：

- 前端不依赖学校官网结构
- 原文和结构化信息可以分别治理
- 老数据可以重复跑解析器
- 结构化抽取坏了，也不会影响正文可读性

## 4. 它们怎么获取院校网站/频道入口

这是你最关心的一点。公开侧能看出来一部分。

### 4.1 已确认：它们至少有人工维护入口 URL 的能力

后台“新增频道”页面会：

- 先调用 `GET /schoolList` 做学校联想
- 再提交一个对象到 `POST /admin/task`

提交字段包括：

- `title`
- `school`
- `originUrl`
- `type`
- `isVirtualTask`

这说明至少有一部分频道/院校入口是人工建的，`originUrl` 就是抓取起点或官网入口。

公开证据：

- [NewTask bundle](https://h5.yanbot.tech/assets/NewTask-Du9dkKGn.js)
- [submitTask bundle](https://h5.yanbot.tech/assets/submitTask-BSm9o2An.js)

### 4.2 已确认：频道详情页保留了“去官网”按钮

频道详情页会直接用：

- `task.originUrl`

渲染“去官网”按钮。

这进一步说明：

- `task/channel` 这一层本身就挂着官方入口 URL
- 这些 URL 不是临时算出来的，而是已落入后端模型

公开证据：

- [task detail bundle](https://h5.yanbot.tech/assets/task-detail-D83SRiwh.js)

### 4.3 高概率推断：它们不是纯自动发现全国院校官网

从目前能看到的公开证据，更像是：

- 先有学校字典：`/schoolList`
- 再通过后台新建频道，把学校和 `originUrl` 绑起来
- 自动化更多发生在“从已知入口向下抓取和清洗”
- 而不是“系统自己全网自动找到全国所有研招站并稳定维护”

我更倾向认为它们的起步方式是：

1. 先有人把重点学校和频道入口配出来
2. 系统再从这些入口自动抓取
3. 后续再做频道聚合、子频道、可能的自动扩展

### 4.4 当前看不出来的部分

公开侧目前看不出来：

- `/schoolList` 本身是手工导入、外部字典，还是早期批量爬来的
- `originUrl` 之后是否还会自动发现二级栏目
- 后台是否存在更复杂的 selector/抓取规则配置
- 是否有专门的学校/频道治理面板，不止是 `task` 这层

但即便这些细节看不见，也不影响前面的主判断：

- 它们不是“纯自动找学校官网”
- 至少保留了“学校字典 + 人工频道入口”这一层

## 5. 它们的抓取与清洗，最值得学的地方

### 5.1 先做统一正文层，不要一开始只做业务结构化

`feed` 这一层是最值得学的。

原因：

- 学校站点结构不稳定
- 业务规则会反复变
- 只做结构化，后面很难复盘和修规则

统一正文层至少应该保存：

- 标题
- 清洗后正文
- 原始链接
- 快照
- 发布时间
- 来源学校/频道
- 内容指纹

### 5.2 保留“站内正文”和“站外原文”双通道

`yanbot` 不是只做一个外链跳转，也不是只做站内镜像。

它的做法更实用：

- 默认先看站内清洗后的正文
- 如果正文或附件有问题，再点“查看原文”

这能兼顾：

- 用户阅读体验
- 抓取失败兜底
- 对来源网站的回链

### 5.3 正文抽取与业务解析解耦

它们明显把：

- `feed.content` 抽取

和：

- `transfer-feed-parse`

拆成了两步。

这是成熟做法，因为：

- 正文抽取失败和业务解析失败是两种不同问题
- 抓取成功后可以重复修解析器
- 新增结构化字段不用重抓历史原文

### 5.4 入口资产要可治理

从 `schoolList + admin/task + originUrl` 这条线看，它们明显没有把入口发现完全交给黑盒。

这点非常值得借鉴：

- 真正决定抓取质量的，往往不是 parser，而是入口资产是否干净
- 如果入口错了，后面清洗再强也只是错上加错

## 6. 对我们项目可以直接借鉴的部分

下面只讨论对 `格物简录` 当前主线真正有帮助的部分。

### 6.1 借鉴点 A：把“公告正文层”继续做扎实

我们当前已经有：

- `contents`
- `content_snapshots`
- selector + readability 双通道
- PDF 文本提取

这和 `yanbot` 的 `feed` 思路是相通的。

可以继续强化的方向：

- 让公告详情默认展示站内清洗正文，而不是优先把用户送去原站
- 原文链接作为兜底和溯源
- 把正文抽取质量视为独立治理对象，而不是搜索副产物

### 6.2 借鉴点 B：显式维护“学校/栏目入口资产”

我们现在已经有：

- `site_sections`
- `site_section_links`

这其实比对方公开可见的 `task + originUrl` 更接近可运营化。

可借鉴的是思路，而不是照搬命名：

- 入口资产必须是显式、可治理、可追溯的
- 自动发现只能辅助，不能完全替代资产维护

### 6.3 借鉴点 C：详情页要能承载“正文 + 结构化情报 + 原文”

虽然本轮不做调剂主链路改造，但它的详情页承载思路值得学：

- 一层是正文
- 一层是结构化摘要
- 一层是外部原文

对我们后续的公告详情页，也可以采用类似思路：

- 顶部：学校/栏目/发布时间/标签
- 中间：站内正文
- 底部：原文链接、附件、快照说明

### 6.4 借鉴点 D：先人工种入口，再自动扩张

对我们当前阶段，最稳的方式不是“全自动全国高校发现”，而是：

1. 重点学校先种干净入口
2. 入口下再自动 discovery
3. 自动发现结果回流到治理面板

这和我们当前 `site_sections` 的方向是一致的，比直接学一个黑盒自动发现更现实。

## 7. 不建议照抄的地方

### 7.1 不要盲目模仿它的微信优先路径

`yanbot` 明显强依赖微信登录和微信场景。

我们的主线当前仍是：

- 先把 Web 正式可运营做扎实

因此不建议为了模仿竞品，把抓取/展示设计绑死到微信容器和微信登录链路。

### 7.2 不要只学“调剂卡片”，忽略底层内容治理

它表面上最吸引人的是：

- 调剂卡片
- AI 调剂
- 会员转化

但真正支撑这些的，是入口资产、正文层、结构化层和治理后台。

如果只学卡片 UI，不学数据分层，最后只会得到一个漂亮但不稳定的前端壳子。

### 7.3 直接 `innerHTML` 渲染正文有风险

`yanbot` 前端公开代码里会直接把 `feed.content` 塞到 `innerHTML`。

这只有在服务端清洗非常严格时才安全。

对我们来说，不应只看“它能渲染”，还要同时审视：

- XSS 风险
- 富文本白名单
- 附件和外链处理策略

## 8. 对我们当前阶段的具体建议

基于当前路线图和现状，我认为现在真正适合借鉴 `yanbot` 的，不是“改造成它那样的调剂产品”，而是下面三件事：

### 8.1 先把公告详情页做成站内主阅读页

目标：

- 公告搜索结果不只给列表预览
- 用户点进详情后，优先看站内正文
- 原文链接保留在详情页

这一步最接近 `yanbot` 里已经验证有效的阅读路径，但不会把项目范围带偏到“调剂大改造”。

### 8.2 把入口资产治理继续前置

目标：

- 明确每个重点学校/栏目从哪里抓
- 避免把“入口发现错误”拖到搜索质量阶段才暴露
- 让 discovery 更像“从可信入口向下扩张”

### 8.3 保持“正文层”和“结构化层”解耦

即使后面要做更强的调剂结构化，也建议坚持：

- 公告正文层独立存在
- 调剂结构化只是公告层之上的派生层

这样更符合我们现有 `contents` / `content_snapshots` / `site_sections` 架构，不需要推翻重来。

## 9. 最终判断

`yanbot` 公开侧最值得借鉴的，不是某个神秘爬虫技巧，而是非常朴素但成熟的工程组织方式：

- 有学校/频道资产
- 有统一正文层
- 有业务结构化层
- 有站内详情与外链原文双通道
- 有人工治理入口

对 `格物简录` 来说，当前最应该借鉴的是：

- 继续强化公告正文层
- 保持入口资产可治理
- 让详情页真正成为站内阅读与溯源中心

当前最不应该做的是：

- 为了模仿竞品，过早把重心从“Web 公告主链路”切到“调剂产品大改造”
- 试图用纯自动发现替代入口资产治理

## 10. 公开观察用到的入口

以下内容用于支撑本文判断：

- [首页 HTML](https://h5.yanbot.tech/home)
- [main bundle](https://h5.yanbot.tech/assets/index-BiA73VWg.js)
- [home bundle](https://h5.yanbot.tech/assets/home-index-7GSVToYg.js)
- [transfer api bundle](https://h5.yanbot.tech/assets/transfer-DaSiHSwt.js)
- [TransferDataDetail bundle](https://h5.yanbot.tech/assets/TransferDataDetail-DieBMvmB.js)
- [feed api bundle](https://h5.yanbot.tech/assets/index-DpWzOaBC.js)
- [feed detail bundle](https://h5.yanbot.tech/assets/feed-detail-9RRw5Cjf.js)
- [task detail bundle](https://h5.yanbot.tech/assets/task-detail-D83SRiwh.js)
- [TaskManageIndex bundle](https://h5.yanbot.tech/assets/TaskManageIndex-DnWZ4hP7.js)
- [NewTask bundle](https://h5.yanbot.tech/assets/NewTask-Du9dkKGn.js)
- [submitTask bundle](https://h5.yanbot.tech/assets/submitTask-BSm9o2An.js)
