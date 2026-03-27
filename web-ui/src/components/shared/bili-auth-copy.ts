"use client";

export type AuthPane = "password" | "sms" | "register";

export const AUTH_PANE_LABELS: Record<AuthPane, string> = {
  password: "密码登录",
  sms: "短信登录",
  register: "注册账号",
};

export const AUTH_FEATURE_PILLS = [
  "公告搜索",
  "调剂雷达",
  "关注提醒",
  "账号安全",
];

export const AUTH_SCENE_CARDS = [
  {
    title: "登录主账号",
    description: "继续管理关注、通知和检索偏好。",
  },
  {
    title: "亮色统一入口",
    description: "路由页和弹窗共用同一套账号壳，不再分裂成两种风格。",
  },
  {
    title: "后续动作更清晰",
    description: "登录后直达检索页，账号中心和退出也保留在同一位置。",
  },
];

export const AUTH_VALUE_POINTS = [
  {
    label: "统一会话",
    value: "登录后可直接进入搜索和账号空间",
  },
  {
    label: "操作稳定",
    value: "注册、登录、退出都走现有真实 auth API",
  },
  {
    label: "入口预留",
    value: "扫码、短信、社交入口先保留高保真占位",
  },
];

export const AUTH_SOCIAL_ENTRIES = [
  { key: "wechat", label: "微信登录", badge: "微" },
  { key: "qq", label: "QQ 登录", badge: "Q" },
  { key: "weibo", label: "微博登录", badge: "博" },
] as const;

export const AUTH_LOCKED_COPY: Record<string, string> = {
  sms: "短信登录暂未开放，请先使用账号密码登录。",
  qrcode: "二维码登录暂未开放，请先使用账号密码登录。",
  wechat: "微信登录暂未开放，请先使用账号密码登录。",
  qq: "QQ 登录暂未开放，请先使用账号密码登录。",
  weibo: "微博登录暂未开放，请先使用账号密码登录。",
};
