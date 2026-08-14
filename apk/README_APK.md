# 学习台 APK 打包与联网自动更新说明

本目录已为你准备好两个独立 App 的工程与素材，分别对应两个孩子：

| 目录 | 适用 | 内容 |
|------|------|------|
| `android-girl/` + `girl/` | 女孩子 · 五年级升六年级 | 学做菜 + 积分成就 |
| `android-boy/` + `boy/` | 男孩子 · 初一升初二 | C++/CSP-J 备考 + 积分成就 |

每个平台都有两套产物：
- `android-xxx/`：Android Studio 工程（推荐，可生成正式签名 APK，并支持联网自动更新内容）。
- `xxx/index.html`：单文件网页版，可直接用「HTML 转 APK」类免编程工具打包（联网更新需主机允许跨域，详见下文）。

---

## 一、联网自动更新内容（核心功能）

应用采用「**内置内容 + 远程内容合并**」机制：

- 安装包内置一份内容池（新闻 / 常识 / 题库 / 菜谱 / 提示 / 欢迎语）。
- 每次启动（联网状态下），原生层会从你指定的网址下载一份最新内容 JSON，与内置内容**合并**：
  - **相同 id → 远程覆盖内置**（便于修正/更新某篇文章，无需发新 APK）。
  - **新 id → 追加**到对应的池子里。
- 合并后当天的「每日训练 / 新闻 / 常识 / 今日菜谱 / 欢迎语」仍按日期种子轮换，只是可选内容更多、更新。
- **联网失败或离线**时，自动回退到内置内容 + 上一次联网缓存的内容，**完全不影响使用**。

> 关键好处：**以后想加新文章 / 新题目 / 新菜谱，只要改 JSON 并重新上传到同一个网址即可，不必重新打包 APK。** 只有当要更换内容网址本身时，才需要改配置并重新构建。

### 安全与隐私
- 应用仅会访问你在配置里填写的那一个内容网址，不会连接任何其它服务器。
- 为了联网更新，工程已声明 `INTERNET` 权限（仅用于下载内容 JSON）。
- 远程内容在注入前会做 HTML 特殊字符转义，避免内容里的标签被当成代码执行。

---

## 二、新闻来自「人民日报」，每日自动更新（重点）

家长要求：新闻板块**专门取自人民日报，并且每天自动更新**。本方案已按此实现。

### 1) 数据源说明（为什么不用 RSS，而抓取频道页）
人民日报社主办的**人民网（www.people.com.cn）**就是人民日报的官方网站，每天更新。
- 人民网早期提供的 RSS 订阅源（`/rss/*.xml`）**已经长期停更**（实测停留在 2025 年甚至 2016 年），不能直接用。
- 因此抓取脚本改为直接读取人民网**频道列表页 + 文章页**，保证拿到的是当天/近期的新鲜新闻。

抓取脚本：`apk/fetch_people_news.py`（仅用 Python 标准库，无需安装任何第三方包，可在 GitHub Actions 或你自己的电脑上直接运行）。

它做的事：
1. 依次抓取儿童友好的频道：社会、国际、教育、健康。
2. 从列表页提取文章链接与标题，按 URL 中的日期排序，取最新若干篇。
3. 进入每篇文章页，提取正文 `<p>` 段落（自动过滤页脚/导航噪音）。
4. 按标题/正文关键词，把新闻归到 App 的四个分类：**科学探索 / 科技前沿 / 自然万物 / 社会百科**。
5. 自动过滤不适合儿童阅读的内容（违纪、犯罪、暴力、灾害伤亡等）。
6. 输出标准 JSON（字段 `news`，题库/常识/菜谱继续沿用 App 内置）。

### 2) 本地手动跑一次（先看效果 / 调试）
```bash
cd apk
python fetch_people_news.py                 # 生成到脚本同目录（apk/）
python fetch_people_news.py --out-dir ..     # 生成到仓库根目录（推荐，供 jsDelivr 直接托管）
python fetch_people_news.py --limit 30       # 控制抓取数量
python fetch_people_news.py --dry-run        # 只打印不写文件
```
脚本默认把 `content-girl.json` / `content-boy.json` 写到**仓库根目录**（与 `.github` 同级），方便对外提供。

### 3) 一键「每天自动更新」（推荐：GitHub Actions + jsDelivr）
仓库里已放好工作流 `.github/workflows/daily-people-news.yml`，它会：
- 每天 **北京时间约 06:17** 自动运行；
- 执行抓取脚本，重新生成 `content-girl.json` / `content-boy.json`；
- 内容有变化才提交回仓库。

内容通过 **jsDelivr**（`https://cdn.jsdelivr.net/gh/<用户名>/<仓库名>@main/content-girl.json`）对外提供——
**无需开启 GitHub Pages，也自带跨域头 `Access-Control-Allow-Origin: *`**，网页版和原生版都能直接拉取。

你只需做两步：
1. 把这个仓库推到 GitHub（**公开仓库**即可；jsDelivr 只服务公开仓库）。
2. 把下面两个网址分别填进工程里（见第三节第 3 步），重新打包 APK：
   ```
   女孩版：https://cdn.jsdelivr.net/gh/<你的GitHub用户名>/<仓库名>@main/content-girl.json
   男孩版：https://cdn.jsdelivr.net/gh/<你的GitHub用户名>/<仓库名>@main/content-boy.json
   ```
   之后**每天新闻会自动刷新**，无需再动 APK。也可在 Actions 页面点 “Run workflow” 立即手动触发一次。

> 说明：若 GitHub 的境外服务器偶尔连不上人民网，某次抓取会失败、不更新（原有 JSON 保持不变，不影响使用），次日会继续尝试。如需更高成功率，可在你自己的国内电脑上用下面的「本地定时」方案。

### 4) 本地定时更新（备选方案）
如果你不想用 GitHub，也可以在自己**长期开机的电脑**上定时运行脚本，再把生成的 `content-girl.json` / `content-boy.json` 上传到任意支持 HTTPS 的静态空间（云存储 / 自己的服务器 / 内网都可）：
- **Windows**：任务计划程序 → 创建基本任务 → 触发器“每天”→ 操作“启动程序”→ 程序 `python.exe`，参数 `apk/fetch_people_news.py --out-dir <输出目录>`。
- **macOS / Linux**：`crontab -e` 加入 `17 22 * * * cd /path/to/repo && python apk/fetch_people_news.py --out-dir .`

### 5) 新闻内容的“覆盖”行为（重要）
- 远程 JSON 带有来自人民日报的 `news` 时，App 会**用人民日报新闻整池替换**内置示例新闻（内置 `NEWS_ITEMS` 仅作为未联网时的兜底）。
- 联网失败 / 离线 / 还没配置网址时，自动回退到内置示例新闻，**界面照常可用**。
- 文案、题库、常识、菜谱等仍按原有「同 id 覆盖、新 id 追加」的合并规则处理。

---

## 三、如何部署内容 JSON（你来控制）

### 1) 准备 JSON
参考本目录提供的样例：`content-sample-girl.json`、`content-sample-boy.json`。它们就是标准 JSON，字段如下（任意字段都可省略，省略则沿用内置）：

```jsonc
{
  "version": 1,                 // 可随便写，便于你自己记录
  "updatedAt": "2026-08-14",
  "news": [                     // 新闻（取自人民日报，会整池替换内置示例）
    {"id":"peo20260814001","category":"科技前沿","title":"标题","summary":"一句话简介","readMin":2,
     "paras":["正文第一段","正文第二段"],"source":"人民网","link":"https://..."}
  ],
  "knowledge": [                // 常识（结构同 news，按 id 合并）
    {"id":"k201","category":"健康生活","title":"标题","summary":"简介","readMin":2,
     "paras":["正文"]}
  ],
  "questions": {                // 题库：按学科分组的对象（注意是对象不是数组）
    "数学": [
      {"id":"m201","type":"choice","difficulty":"基础","knowledgePoint":"小数加减",
       "question":"计算 0.3+0.5=？","options":["0.8","0.35","0.2","1.5"],"answer":0,
       "hint":{"approach":"思路","pitfall":"易错点","extension":"拓展"}}
    ]
  },
  "newsTips": ["💡 一条看新闻小提示"],      // 字符串数组，会追加（去重）
  "knowledgeTips": ["💡 一条小常识"],
  "cookTips": ["🍳 一条做菜安全提示"],      // 仅女孩版用得到
  "recipes": [                  // 菜谱（仅女孩版；字段见内置 DEFAULT_RECIPES）
    {"id":"rk201","name":"菜名","category":"汤","difficulty":"简单","time":40,"servings":3,
     "ingredients":["排骨 500克","冬瓜 300克"],"steps":["步骤1","步骤2"],"tip":"小贴士"}
  ],
  "homeWelcome": ["🌟 一条首页欢迎语"]       // 字符串数组，会追加（去重）
}
```

> 自动化生成的 `content-*.json`（在仓库根目录）通常**只包含 `news`**（来自人民日报），其余内容继续用 App 内置；你若要覆盖常识/题库/菜谱，再往同一个 JSON 里补对应字段即可，规则同上。

字段说明：
- `news` / `knowledge`：`category` 建议用内置已有的分类（新闻：科学探索/科技前沿/自然万物/社会百科；常识：历史故事/健康生活/文化艺术/趣味常识/科学探索/科技前沿/自然万物/社会百科），这样能在分类筛选里正常显示。
- `questions`：必须是**对象**，键为学科名（如 语文/数学/英语/科学/道法/物理…），值是对应的题目数组。题目 `id` 全局唯一即可；覆盖内置题用相同 id。
- `recipes`：女孩版用；`difficulty` 用 `简单/中等/困难`，`time` 是数字（分钟），`ingredients`、`steps` 是字符串数组。

### 2) 托管 JSON（推荐 jsDelivr，无需任何额外配置）
- **jsDelivr（推荐，零配置）**：只要仓库是**公开**的并推到 GitHub，就可用
  `https://cdn.jsdelivr.net/gh/<用户名>/<仓库名>@main/content-girl.json` 直接访问。
  - 自带 `Access-Control-Allow-Origin: *`，网页版和原生版都能拉取。
  - 仓库里 `.github/workflows/daily-people-news.yml` 每日把最新 JSON 提交回仓库，jsDelivr 会自动跟着更新（App 端还带了时间戳防缓存参数，保证拉到当天最新）。
  - 注意分支名：默认写 `@main`；若你的默认分支叫 `master`，把 URL 里的 `@main` 改成 `@master`。
- **GitHub Pages（可选）**：把 JSON 放仓库根目录并开启 Pages，得到 `https://<用户名>.github.io/<仓库>/content-girl.json`。比 jsDelivr 多一步配置，但同样可用。
- **任意静态托管 / 云存储 / 自己的服务器**：只要能通过 HTTPS 直接访问到这个 `.json` 文件即可（网页版还要求返回跨域头 `Access-Control-Allow-Origin: *`；**原生 Android 工程不需要** CORS，因为是原生层下载后再注入）。

### 3) 填好内容网址（重要）
把你的真实网址填到两处（先把占位 `https://example.com/...` 替换掉）：
- 原生工程：`android-xxx/app/src/main/res/values/strings.xml` 里的 `content_url`。
- 网页版（免编程打包用）：`index.html` 里的 `const CONTENT_URL = '...'`。
两处保持一致即可。

> 应用检测到网址仍是占位 `example.com` 时不会发起请求，避免无谓联网。

### 4) 更新内容流程
1. 直接编辑你的 `content-*.json`（加新文章/题目，或改已有 id 的内容）——或让每日工作流自动生成最新人民日报新闻。
2. 重新上传/提交到同一个网址（覆盖原文件）。
3. 平板上的 App 下次启动时自动拉取并合并。**无需重新打包 APK。**
4. 若想更换网址本身，才需要改第 3 步的两处配置并重新构建 APK。

---

## 四、打包成 APK

### 方式 A：Android Studio（推荐，支持联网更新 + 正式签名）
1. 安装 [Android Studio](https://developer.android.com/studio)。
2. 打开 `android-girl` / `android-boy`（分别构建出两个独立 APK）。
3. 按第三节第 3 步填好 `content_url`，并确认 `assets/index.html` 已就位（本目录已放入最终网页）。
4. `Build → Generate Signed Bundle / APK` → 选 APK → 用你的签名密钥 → release。
5. 产出 `app/release/app-release.apk`，分别装到两个孩子平板。

图标/名称微调：
- 应用名：`res/values/strings.xml` 的 `app_name`。
- 图标底色：`res/values/colors.xml` 的 `ic_launcher_background`。
- 图标图形：`res/drawable/ic_launcher_foreground.xml`。

### 方式 B：免编程「HTML 转 APK」工具
把 `girl/index.html` / `boy/index.html`（已内置内容，且 `CONTENT_URL` 已填好）作为入口上传。注意：此类工具默认可能带广告/联网权限，建议关闭；联网更新需主机允许跨域（见第三节）。

---

## 五、安装到平板
- USB/ADB：`adb install app-release.apk`（平板需开启「开发者选项 → USB 调试」）。
- 文件传输：拷到平板后点按安装（允许「未知来源」）。
- 两个 App 包名不同（`com.study.girl` / `com.study.boy`），可同时安装不冲突。

---

## 六、技术实现要点（给想了解的人）
- 网页侧：启动时先合并「上次联网缓存」（`localStorage` 里的 `remoteContent`），再尝试联网；原生层下载成功后调用 `window.__applyRemoteContent(json)` 合并并刷新界面。所有远程文本注入前做 `& < >` 转义防 XSS。拉取时会在网址后追加 `?_=<时间戳>` 防 CDN 缓存，确保拿到当天最新。
- **新闻覆盖逻辑**：`applyRemoteContent` 在收到远程 `news` 时，用 `NEWS_POOL = d.news`（整池替换内置示例），并显式把新池子写回 `INFO_BOARDS.news.pool`（展示配置持有的是初始引用，必须回写界面才会刷新）；远程无 `news` 时回退到内置 `NEWS_ITEMS`。
- 合并幂等：每次都从「内置内容 + 远程内容」重新合并，重复拉取不会产生重复条目。
- 原生侧：`MainActivity` 在网页加载完成后用 `HttpURLConnection` 下载 JSON（规避 WebView 跨域），转义后通过 `evaluateJavascript` 注入；离线/失败静默忽略。
- `minSdk 26`：自适应图标用 XML，无需准备多尺寸 PNG。
- **抓取脚本**：`fetch_people_news.py` 仅用标准库，抓取人民网频道页与文章页，映射到 App 的 news 字段；可本地运行，也可由 `.github/workflows/daily-people-news.yml` 每日调度。

---

## 七、文件清单
```
仓库根目录/
├── content-girl.json            # 女孩版新闻内容（每日自动生成，取自人民日报）
├── content-boy.json             # 男孩版新闻内容（每日自动生成，取自人民日报）
├── .github/workflows/
│   └── daily-people-news.yml    # 每日自动抓取人民日报新闻并提交的工作流
└── apk/
    ├── README_APK.md                # 本说明
    ├── fetch_people_news.py          # 人民日报新闻抓取脚本（标准库，零依赖）
    ├── content-sample-girl.json     # 女孩版内容 JSON 完整 schema 样例（含菜谱/提示）
    ├── content-sample-boy.json      # 男孩版内容 JSON 完整 schema 样例（含题库）
    ├── girl/index.html              # 女孩版单文件网页（免编程工具用）
    ├── boy/index.html               # 男孩版单文件网页
    ├── android-girl/                # 女孩版 Android Studio 工程（支持联网更新机制）
    │   ├── settings.gradle, build.gradle, gradle.properties
    │   ├── gradle/wrapper/gradle-wrapper.properties
    │   └── app/
    │       ├── build.gradle, proguard-rules.pro
    │       └── src/main/
    │           ├── AndroidManifest.xml          # 已含 INTERNET 权限
    │           ├── java/com/study/girl/MainActivity.java   # 含联网拉取逻辑
    │           ├── res/values/{strings(含content_url),colors,themes}.xml
    │           ├── res/drawable/ic_launcher_foreground.xml
    │           ├── res/mipmap-anydpi-v26/ic_launcher.xml
    │           └── assets/index.html             # 最终网页（含联网更新 + 人民日报新闻覆盖逻辑）
    └── android-boy/                 # 男孩版 Android Studio 工程（结构同上）
```
