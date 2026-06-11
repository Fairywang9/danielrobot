# DanielRobot Static Site

增速科技 / DanielRobot 的静态网站仓库。当前项目不依赖构建工具，HTML 文件可以直接由 GitHub Pages 或任意静态文件服务托管。

## 目录结构

- `index.html`: 增速科技主站首页。
- `about.html`: EurekaTalk 关于页面。
- `services.html`: 服务与洞察页面。
- `blog.html`: 博客列表页。
- `zhitan/`: 增速智谈子站首页。
- `utalk/`: 增速商谈子站首页。
- `reports/`: 机器人与产业研究报告页面，部分页面依赖 Chart.js CDN。
- `pics/`: 站点图片资源。
- `CNAME`: GitHub Pages 自定义域名配置。

## 当前架构

这是一个多页面静态站。各页面目前仍以内联 CSS 和内联 JavaScript 为主，部分页面使用 Tailwind CDN，报告页使用 Chart.js CDN。

优点是部署简单、没有构建成本；缺点是公共导航、页脚、样式和交互逻辑容易重复。后续如果页面继续增加，建议逐步抽离公共资源。

## 维护建议

1. 保持页面入口清晰，新增独立页面时优先放在明确目录下。
2. 图片资源统一放在 `pics/` 或未来的 `assets/img/`，避免引用不存在的占位文件。
3. 重复的导航、页脚、语言切换和移动菜单逻辑后续应抽到公共脚本。
4. 如果内容量持续增长，建议迁移到 Astro 或 Eleventy，以便使用布局模板、Markdown 内容和自动 sitemap。

## 本地预览

可以直接用浏览器打开 HTML 文件，也可以在项目目录启动一个静态服务：

```bash
python3 -m http.server 8000
```

然后访问 `http://localhost:8000/`。
