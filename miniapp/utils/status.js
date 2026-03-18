function extractErrorMessage(err, fallbackMessage = "服务暂时不可用，请稍后重试") {
  if (!err) return fallbackMessage;

  if (typeof err === "string") {
    return err.trim() || fallbackMessage;
  }

  if (typeof err.detail === "string" && err.detail.trim()) {
    return err.detail.trim();
  }

  if (typeof err.message === "string" && err.message.trim()) {
    return err.message.trim();
  }

  if (typeof err.errMsg === "string" && err.errMsg.trim()) {
    return err.errMsg.trim();
  }

  if (typeof err.msg === "string" && err.msg.trim()) {
    return err.msg.trim();
  }

  if (err.code !== undefined && err.code !== null) {
    return `请求失败（错误码: ${err.code}）`;
  }

  return fallbackMessage;
}

function normalizeStatusTitle(title) {
  if (typeof title !== "string") {
    return "状态";
  }
  const value = title.trim();
  return value || "状态";
}

function goStatus(title, err, fallbackMessage = "服务暂时不可用，请稍后重试", options = {}) {
  const message = extractErrorMessage(err, fallbackMessage);
  const action = typeof options.action === "string" ? options.action.trim() : "";
  const actionText = typeof options.actionText === "string" ? options.actionText.trim() : "";
  const source = typeof options.source === "string" ? options.source.trim() : "";
  wx.navigateTo({
    url:
      `/pages/status/index?title=${encodeURIComponent(normalizeStatusTitle(title))}` +
      `&message=${encodeURIComponent(message)}` +
      `&action=${encodeURIComponent(action)}` +
      `&actionText=${encodeURIComponent(actionText)}` +
      `&source=${encodeURIComponent(source)}`,
  });
}

module.exports = {
  extractErrorMessage,
  goStatus,
  normalizeStatusTitle,
};
