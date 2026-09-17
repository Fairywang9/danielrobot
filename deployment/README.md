# upspeedtech.com 文章发布

线上网站由阿里云 47.116.100.27 的 Nginx 提供服务，根目录是 `/usr/share/nginx/html`。
使用专用密钥登录现有 `admin` 账户，通过 `sudo -n` 发布文件。发布不依赖 1Panel 界面或构建工具。

`publish.py` 只依赖 Python 标准库和本机 SSH。SSH 私钥和连接 JSON 留在电脑上，不得提交到 GitHub、复制到网页目录或写入文章附件。

## 日常流程

1. 编辑文章 HTML 和图片；更新对应栏目列表。先检查排版、移动端显示和本地链接。
2. 在 Git 中只提交本次网站文件。GitHub 写入登录正常时同步仓库；失败时明确报告，不能声称 GitHub 已同步。
3. 生成计划，列出本次明确需要发布的文件。图片和正文在前，栏目列表在后。
4. 核对计划后发布。脚本为受影响文件备份，并通过 HTTPS 核对线上 SHA-256。
5. 记录发布编号和文章网址。需要恢复时按发布编号回滚。

```bash
python3 deployment/publish.py --connection /path/to/local/connection.json plan \
  --output /path/to/local/release-plan.json \
  pics/article-cover.jpg reports/article.html reports/index.html

python3 deployment/publish.py --connection /path/to/local/connection.json publish \
  /path/to/local/release-plan.json

python3 deployment/publish.py --connection /path/to/local/connection.json rollback \
  RELEASE_ID
```

连接 JSON 的 `key` 和 `known_hosts` 字段相对该 JSON 所在目录解析；它们分别指向私钥和已核对的 SSH 主机记录。

## 备份与保护

- 完整基线备份位于服务器 `/var/backups/upspeedtech/site-*.tar.gz`，不会作为网页提供下载。
- 单次发布的原文件和清单位于 `/var/backups/upspeedtech/releases/RELEASE_ID/`。
- 发布只处理明确列出的文件，不清空网站、不同步整仓库，也不删除服务器上的其他文件。
- 若本地文件在计划后改变，或者服务器文件在计划后改变，发布会拒绝执行。
- 拒绝隐藏文件、符号链接、越界路径和开发工具目录，避免把密钥或开发目录发布到网站。
- 每个文件原子替换；多文件发布失败时恢复备份。它不是整个网站同时切换的部署，因此应将入口列表放在最后。
- 线上校验失败会自动尝试回滚。回滚拒绝覆盖此发布之后的其他修改；出现此情况需要先检查新修改。

## 文章栏目

- 增速智谈入口：`zhitan/index.html`。
- 增速商谈入口：`utalk/index.html`；现有文章部分链接到公众号。
- 报告中心：`reports/index.html`；独立 HTML 可放入 `reports/`。

根据文章归属更新对应入口；正文、封面、标题、摘要、日期和链接应一起更新。

## 搜索引擎与样式

网站主域名为 `https://upspeedtech.com/`。新文章应有独立网址、唯一标题、摘要、同域 canonical，以及栏目中的真实链接；发布时一起更新根目录 `sitemap.xml`。站点地图只列正式发布的页面，修改日期仅在有可信日期时填写。

`robots.txt` 允许抓取公开页面，并标明站点地图。百度搜索资源平台、Google Search Console 的网站验证与站点地图提交需要站点所有者账号；提交不保证收录时间或排名。

增速智谈及报告的 Tailwind 样式已用 3.4.17 预编译到 `assets/css/editorial.css`，浏览器不再依赖 Tailwind CDN。新增样式类时用已安装的 Tailwind 3 CLI 执行：

```bash
tailwindcss -c deployment/tailwind.config.cjs -i deployment/tailwind.css -o assets/css/editorial.css --minify
```

发布 HTML 时需要一起发布改动后的 CSS。`deployment/` 是开发工具目录，不应发布到网页目录。
