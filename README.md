# 2027 秋招雷达

固定网站（启用 GitHub Pages 后）：https://lmy930.github.io/lmy_qiuzhao/

已导入用户上传名单：央企 99 家、民营企业 500 家、银行 21 家，按同名企业去重后共 619 家。

## 网页发布
仓库 Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: main / (root) → Save。

## 每日自动搜集
.github/workflows/daily-discovery.yml 每天北京时间 08:40 调用 scripts/discover.py，分批滚动查询企业的 2027 届招聘线索。可在 Actions → Daily recruitment discovery → Run workflow 手动试运行。

搜索结果存放在 data/leads.json，仅供待核验；**不直接认定已开启**，以免误导投递。data/companies.json 中状态、招聘开启日期、截止时间、网申链接必须核验企业官方公告后方能更新。

注意：GitHub Actions 免费定时运行不是秒级实时监控，存在延迟和外部搜索服务不可用的可能。每日只批量检查部分企业，官网核实流程仍需后续完善。
