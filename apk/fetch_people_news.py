#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_people_news.py
====================
每日从「人民网 / 人民日报」官方频道抓取最新新闻，转换为学习台 App 的 news 字段格式，
写入 content-girl.json / content-boy.json，供 APK 联网自动更新使用。

数据源说明
----------
人民网（www.people.com.cn）是人民日报社主办的官方网站，其频道页每天更新。
注意：人民网早期的 RSS 订阅源（/rss/*.xml）已长期不更新（实测停留在 2025 甚至 2016 年），
因此本脚本直接抓取频道“列表页 + 文章页”，保证拿到的是当天/近期新鲜新闻。

抓取流程
--------
1. 依次抓取若干儿童友好的频道列表页（社会 / 国际 / 教育 / 健康）。
2. 从列表页提取文章链接与标题，按 URL 中的日期排序，取最新的若干篇。
3. 对每篇进入文章页，提取正文的 <p> 段落（过滤页脚/导航噪音）。
4. 根据标题/正文关键词映射到 App 的 4 个新闻分类：科学探索 / 科技前沿 / 自然万物 / 社会百科。
5. 写出标准 JSON（仅含 news 字段，题库/常识/菜谱继续沿用 App 内置）。

依赖：仅 Python 标准库（urllib / html / re / json / datetime），可在 GitHub Actions 或本机直接运行。

用法
----
    python fetch_people_news.py                 # 生成到脚本同目录
    python fetch_people_news.py --out-dir ./     # 指定输出目录
    python fetch_people_news.py --limit 30       # 控制抓取文章数量
    python fetch_people_news.py --dry-run         # 只打印，不写文件
"""

import argparse
import datetime
import html
import json
import os
import re
import sys
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# 配置：儿童友好的人民网频道（列表页链接形如 /n1/YYYY/MM/xxx.html）
# ---------------------------------------------------------------------------
CHANNELS = [
    {"name": "社会", "url": "http://society.people.com.cn/", "base": "社会百科"},
    {"name": "国际", "url": "http://world.people.com.cn/",   "base": "社会百科"},
    {"name": "教育", "url": "http://edu.people.com.cn/",     "base": "社会百科"},
    {"name": "健康", "url": "http://health.people.com.cn/",  "base": "社会百科"},
]

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 不适合儿童阅读的话题（违纪/犯罪/暴力/灾害伤亡等），标题命中即跳过
UNSUITABLE = ["受贿", "违纪", "审查调查", "犯罪", "杀人", "死亡", "遇难", "坠亡",
              "爆炸", "袭击", "赌博", "色情", "贪腐", "判刑", "拘捕", "恐怖",
              "绑架", "枪击", "纵火", "虐待", "性侵", "走私", "贩毒", "落马"]

# 分类关键词映射（命中即归入对应分类，按优先级从高到低）
CAT_RULES = [
    ("科技前沿", ["科技", "人工智能", "AI", "机器人", "卫星", "航天", "火箭", "飞船",
                "芯片", "量子", "互联网", "数字", "5G", "6G", "新能源", "电池",
                "高铁", "无人机", "自动驾驶", "算法", "算力", "元宇宙", "脑机"]),
    ("科学探索", ["宇宙", "天文", "星系", "黑洞", "行星", "恒星", "月球", "火星", "太阳",
                "太空", "科学", "研究", "发现", "实验", "基因", "疫苗", "医学", "医院",
                "大脑", "物理", "化学", "数学", "考古", "化石", "大脑", "细胞", "纳米"]),
    ("自然万物", ["动物", "植物", "生态", "自然", "森林", "海洋", "湿地", "候鸟", "熊猫",
                "大熊猫", "保护", "气候", "环境", "天气", "台风", "暴雨", "地震", "火山",
                "河流", "湖泊", "雪山", "草原", "沙漠", "公园", "花草", "鸟类", "昆虫"]),
]

FOOTER_MARKERS = ["人民日报社概况", "关于人民网", "报社招聘", "招聘英才", "广告服务",
                 "运营服务", "合作加盟", "版权服务", "数据服务", "网站声明", "网站律师",
                 "信息保护", "联系我们", "责任编辑", "扫描二维码", "关注我们", "客户端",
                 "下载客户端", "分享到", "上一篇", "下一篇", "相关阅读", "延伸阅读",
                 "违法和不良信息举报", "举报电话", "点击查看", "图为", "图为："]

HTTP_TIMEOUT = 15
MAX_PARAS = 8          # 每篇文章最多保留的段落数
MAX_TOTAL_CHARS = 1600 # 每篇文章正文总字数上限


def fetch_text(url):
    """抓取网页文本，失败返回 None。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read()
        # 人民网页面多为 utf-8 / gbk，先尝试 utf-8
        for enc in ("utf-8", "gbk", "gb18030"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")
    except Exception as e:
        sys.stderr.write("  [warn] fetch failed %s -> %s\n" % (url, e))
        return None


def clean_text(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = html.unescape(s)
    s = s.replace("\u3000", " ").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def url_date_key(url):
    """从 /n1/2026/0814/... 中提取 (2026,8,14) 用于排序。"""
    m = re.search(r"/n1/(\d{4})/(\d{2})/(\d{2})/", url)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return (0, 0, 0)


def is_suitable(title):
    t = title or ""
    for w in UNSUITABLE:
        if w in t:
            return False
    return True


def match_blob(blob):
    for cat, kws in CAT_RULES:
        for kw in kws:
            if kw in (blob or ""):
                return cat
    return None


def map_category(title, text):
    """分类优先级：标题命中 > 正文命中（仅限 科学探索/自然万物）> 频道 base。
    科技前沿 只在标题命中时才采用，避免正文里偶尔出现的“数字/科技”等词误判风景稿。"""
    t = match_blob(title)
    if t == "科技前沿":
        return "科技前沿"
    b = match_blob(text)
    if b in ("科学探索", "自然万物"):
        return b
    if t:
        return t
    return None  # 交给调用方用频道 base


def extract_articles_from_listing(html_text, host):
    """从频道列表页提取 (url, title)。"""
    items = []
    seen = set()
    # 匹配：href="http(s)://<host>/n1/YYYY/MM/...html" 后面紧跟的锚文本
    pat = re.compile(
        r'href="(https?://' + re.escape(host) +
        r'/n1/\d{4}/\d{4}/[^"]+\.html)"[^>]*>(.*?)</a>',
        re.S | re.I)
    for m in pat.finditer(html_text or ""):
        url = m.group(1).strip()
        title = clean_text(m.group(2))
        if len(title) < 6 or len(title) > 60:
            continue
        if url in seen:
            continue
        seen.add(url)
        items.append((url, title))
    return items


def extract_paragraphs(article_html):
    """从文章页提取正文段落，过滤页脚/导航噪音。"""
    if not article_html:
        return []
    # 优先在常见正文容器内查找
    container = None
    for sel in [r'id="rwb_zw"', r'class="show_text"', r'class="rm_txt"',
                r'class="text"', r'id="articleContent"', r'class="content"']:
        blk = re.search(r'<div[^>]*' + sel + r'[^>]*>(.*?)</div>', article_html, re.S)
        if blk:
            container = blk.group(1)
            break
    scope = container if container else article_html

    raw_ps = re.findall(r"<p[^>]*>(.*?)</p>", scope, re.S)
    paras = []
    total = 0
    for p in raw_ps:
        t = clean_text(p)
        if len(t) < 12:
            continue
        if any(mk in t for mk in FOOTER_MARKERS):
            continue
        # 跳过纯导航/链接性质的短句
        if t.endswith(">") or "点击" in t[:4]:
            continue
        paras.append(t)
        total += len(t)
        if len(paras) >= MAX_PARAS or total >= MAX_TOTAL_CHARS:
            break
    return paras


def build_summary(paras):
    if not paras:
        return "（暂无摘要）"
    # 取首段前 60 字作为一句话简介
    s = paras[0]
    if len(s) > 60:
        s = s[:60] + "…"
    return s


def estimate_read_min(paras):
    chars = sum(len(p) for p in paras)
    # 约 250 字/分钟，至少 1 分钟，最多 5 分钟
    return max(1, min(5, (chars + 249) // 250))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--limit", type=int, default=26, help="最终保留的文章数量")
    ap.add_argument("--dry-run", action="store_true", help="只打印不写文件")
    args = ap.parse_args()

    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")
    print("[info] 开始抓取人民网新闻，日期 %s" % today_str)

    collected = []  # (date_key, url, title, channel_base)
    for ch in CHANNELS:
        print("[info] 抓取频道：%s (%s)" % (ch["name"], ch["url"]))
        h = fetch_text(ch["url"])
        if not h:
            continue
        host = ch["url"].split("/")[2]
        arts = extract_articles_from_listing(h, host)
        print("       列表命中 %d 条" % len(arts))
        for url, title in arts:
            if not is_suitable(title):
                continue
            collected.append((url_date_key(url), url, title, ch["base"]))

    # 按日期倒序，最新在前
    collected.sort(key=lambda x: x[0], reverse=True)
    # 去重：同一 URL 或同一标题（不同频道可能用不同链接发同一篇稿）
    _punct = "，。、：:；;·•（）()【】[]\"'\\-—_|“”‘’ \t\n"
    seen_url, seen_title = set(), set()
    unique = []
    for dk, url, title, base in collected:
        if url in seen_url:
            continue
        nt = title or ""
        for ch in _punct:
            nt = nt.replace(ch, "")
        if nt in seen_title:
            continue
        seen_url.add(url)
        seen_title.add(nt)
        unique.append((url, title, base))

    print("[info] 候选去重后 %d 条，准备抓取正文（上限 %d）" % (len(unique), args.limit))
    news = []
    for idx, (url, title, base) in enumerate(unique[:args.limit], start=1):
        ah = fetch_text(url)
        paras = extract_paragraphs(ah)
        if not paras:
            # 正文抓取失败：用标题生成单段兜底，保证卡片可打开
            paras = [title + "。点击可前往人民网查看详情。"]
        # 若文章页 <title> 更完整，用它替换列表标题
        if ah:
            tm = re.search(r"<title>(.*?)</title>", ah, re.S)
            if tm:
                full = clean_text(tm.group(1))
                full = re.split(r"[_\-|—]", full)[0].strip()
                if len(full) >= 6:
                    title = full
        # 用完整标题再做一次儿童适宜性校验（列表标题可能被截断而漏掉“犯罪”等词）
        if not is_suitable(title):
            print("       跳过不适宜内容：%s" % title[:30])
            continue
        cat = map_category(title, " ".join(paras[:2]))
        if not cat:
            cat = base
        item = {
            "id": "peo" + today_str.replace("-", "") + "%03d" % idx,
            "category": cat,
            "title": title,
            "summary": build_summary(paras),
            "readMin": estimate_read_min(paras),
            "paras": paras,
            "source": "人民网",
            "link": url,
        }
        news.append(item)
        print("  [%02d] %s | %s | %d段" % (idx, cat, title[:30], len(paras)))

    if not news:
        sys.stderr.write("[error] 未抓到任何新闻，可能是网络或页面结构变化，已中止以免覆盖旧数据。\n")
        sys.exit(1)

    payload = {
        "version": 1,
        "updatedAt": today_str,
        "source": "人民网（人民日报社主办）官方频道，每日自动抓取",
        "news": news,
    }

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:2000])
        return

    for name in ("content-girl.json", "content-boy.json"):
        out = os.path.join(args.out_dir, name)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print("[ok] 已写出 %s (%d 条新闻)" % (out, len(news)))


if __name__ == "__main__":
    main()
