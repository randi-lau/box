# 学习台「远程内容源」部署指南（你的仓库版）

> 你的 GitHub 仓库 `randi-lau/box` 已经在每天自动更新人民日报新闻（content-boy.json）。
> 下面把这套**完整内容源**（新闻+常识+菜谱+编程+三学段题库）接进去，之后所有模块每天自动更新。
> 全程免费，约 5 分钟，之后什么都不用管。

---

## 这套东西是什么

| 文件 | 作用 |
|------|------|
| `generate.py` | 内容生成器。每天运行一次，输出 5 个 JSON |
| `content.json` | 总清单（manifest）：当天新闻、常识、菜谱、编程题、题库索引 |
| `q-primary.json` / `q-junior.json` / `q-senior.json` | 小学 / 初中 / 高中 题库 |
| `.github/workflows/daily-content.yml` | 每天北京时间 08:00 自动运行生成器并推送 |

**每天更新的内容（生成器自动做，无需你管）：**
- 📰 **新闻**：服务端直接抓**中国新闻网当日实时新闻**（GitHub 服务器抓取，不受浏览器限制），抓不到才用内置池
- 📚 **常识 / 🍳 菜谱 / 💻 编程题 / 📝 题库**：从大内容池按当天日期抽取不同子集，每天不同

---

## 2 步启用

### 第 1 步：把内容源文件上传到你的仓库

1. 打开 https://github.com/randi-lau/box （你的仓库）。
2. 点 **Add file → Upload files**，把本机 `content` 文件夹里的这些文件全部拖进去：
   - `generate.py`
   - `content.json`、`manifest.json`
   - `q-primary.json`、`q-junior.json`、`q-senior.json`
   - `.github` 文件夹（里面是 `workflows/daily-content.yml`；如果上传页面不方便拖文件夹，就打开 `.github/workflows/` 目录，单独把 `daily-content.yml` 上传到同路径）
3. 底部 Commit changes，完成。

> 装过 Git 的话，也可以直接在 `content` 文件夹里执行：
> ```
> git init
> git add .
> git commit -m "远程内容源"
> git branch -M main
> git remote add origin https://github.com/randi-lau/box.git
> git push -u origin main
> ```
> 注意：如果你本地的 `content` 和仓库其他文件混在一个 Git 仓库里，就把 `content/` 当子目录 push 即可。

### 第 2 步：把 App 的内容地址改成新清单

新地址是：

```
https://cdn.jsdelivr.net/gh/randi-lau/box@main/content.json
```

两种改法：
- **本机一键改**（推荐）：在项目根目录运行
  ```
  python apk/set_content_url.py randi-lau/box
  ```
  它会自动把地址写进全部 HTML 和安卓工程，然后**重新打包 APK** 即可。
- **App 内改**：打开 App → 设置/高级 →「远程内容地址」→ 粘贴上面地址 → 保存并同步。

---

## 每天自动更新怎么生效

```
北京时间 08:00
   ↓ GitHub Actions 自动跑 generate.py
   ↓ 服务端抓中新网当日新闻 + 按日期抽取常识/菜谱/编程/题库
   ↓ 提交并推送 content.json 等 5 个文件
   ↓ jsDelivr（全球 CDN）几分钟内同步
   ↓ 小朋友打开 App → 拉到当天内容，自动缓存
```

- 手机没网 / 拉取失败：App 自动用上次缓存或内置内容，**不会空白**。
- 你仓库原有的"人民日报新闻每日抓取"（content-boy.json）可以继续留着，互不影响；想精简也可以删掉旧工作流。

---

## 常见问题

**Q1：Actions 没自动跑？**
新仓库首次要在仓库页面点 **Actions** 标签 → 找到「每日内容自动更新」→ 点 **Run workflow** 手动触发一次（顺便验证）。之后每天自动跑。

**Q2：App 里还是旧内容？**
jsDelivr 缓存最长 12 小时；也可以把地址里的 `@main` 改成 `@latest`，或手动点 App 里的「🔄 立即同步」。

**Q3：怎么验证成功？**
手机/电脑浏览器打开 `https://cdn.jsdelivr.net/gh/randi-lau/box@main/content.json`，能看到 JSON 且 `news` 是当天新闻就成功了。

**Q4：想改内容池？**
编辑 `generate.py` 里的 `NEWS_POOL` / `KNOWLEDGE_POOL` / `COOKING_RECIPES` 等大池（中文注释清楚），保存后本地运行 `python generate.py` 即可预览效果。

**Q5：仓库里的网页版 HTML 是旧版？**
把最新版 `study_workspace.html` 一起 push 上去，网页版（jsDelivr 访问）就是最新功能了。APK 版则需重新打包安装。
