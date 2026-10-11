# 按需刷新后端（Cloudflare Workers）

静态 GitHub Pages 无法自行抓取657家企业的招聘站点。本目录提供可部署的轻量接口。

## 部署准备

1. 在 Cloudflare 控制台创建 Worker（名称例如 `qiuzhao-refresh`），源代码使用 `src/index.js`。
2. 创建 KV 命名空间并绑定到 Worker，变量名必须为 `REFRESH_LIMIT`。
3. 为 Worker 设置密钥 `GITHUB_TOKEN`：GitHub fine-grained personal access token，仅授予 `lmy930/lmy_qiuzhao` 的 Actions: write 权限，避免授予全账号权限。密钥只能放在 Cloudflare Secret，不能放网页或公开仓库。
4. 部署后测试 `GET https://<worker-host>/health` 和有 Origin 头的 `POST /refresh`。
5. 将得到的完整 Worker URL 写入根目录 `refresh-config.json` 的 `endpoint` 字段。若尚未部署，请保持空字符串。

网页打开时即读取 GitHub 上最新已保存的数据。配置了 Worker 后，网页会发出一次按需扫描请求，并显示后台扫描中；按钮可再次请求，但全站最短间隔30分钟。查询进度依赖 GitHub Actions / 仓库数据的实际更新。不是几秒钟内搜完657家。

安全：接口只允许指定 Origin，另以 KV 缓存进行30分钟冷却。Origin 不能作为强身份认证。低风险个人站点适用；公开大流量部署应增加 Turnstile 或其他认证。Cloudflare KV 最终一致性不保证严格限流。
