# 2027 秋招雷达

固定网站（启用 GitHub Pages 后）：https://lmy930.github.io/lmy_qiuzhao/

已导入用户上传名单：央企 99 家、民营企业 500 家、银行 21 家，按同名企业去重后共 619 家。

## 网页发布
仓库 Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: main / (root) → Save。

## 每日自动搜集
.github/workflows/daily-discovery.yml 每天北京时间 08:40 调用 scripts/discover.py，分批滚动查询企业的 2027 届招聘线索。可在 Actions → Daily recruitment discovery → Run workflow 手动试运行。

搜索结果存放在 data/leads.json，仅供待核验；**不直接认定已开启**，以免误导投递。data/companies.json 中状态、招聘开启日期、截止时间、网申链接必须核验企业官方公告后方能更新。

注意：GitHub Actions 免费定时运行不是秒级实时监控，存在延迟和外部搜索服务不可用的可能。每日只批量检查部分企业，官网核实流程仍需后续完善。

## 自动核验与日期证据

开发环境只需 Python 3.12 和 Node.js，不依赖第三方包。运行：

```sh
python -m unittest discover -s tests -v
node tests/check_frontend.mjs
```

每日 Actions 在发现线索后运行 `scripts/verify_pages.py`，自动回访政府、高校和已登记的企业官网正文。已确认但没有网申日期的企业也会继续回访。`python scripts/verify_pages.py --dry-run` 可检查而不修改企业数据，但仍生成扫描报告；`--limit N` 可限制诊断请求数量。

网页日历仅采用 `open_date_evidence` 中有原文、目标届别、来源及企业范围的开启日期。旧记录中未留原文的日期继续保存在数据里供自动回溯，不计为“确切开启”。公告日、首次确认日、截止日和“即日起”都不能替代网申起始日期。旗下单位的日期保存为 `subsidiary_openings`，不写成集团统一开启日期；共享的 TCL 品牌不能直接区分 TCL 科技和 TCL 实业。

`data/page_verification_report.json` 记录本次读取、匹配、日期冲突和站点失败。全部正文读取失败时命令返回非零，Actions 不发布该轮数据，并上传诊断报告；部分站点失败时保留既有证据。搜索返回响应不等于核验成功。原始网页依赖 JavaScript、验证码、图片或封闭 API 时，当前文本采集仍不能保证覆盖，需要继续增加对应站点适配。不得通过降低核验标准来提高数量。
