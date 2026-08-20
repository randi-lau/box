#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
『学习台』远程内容源生成器
============================
每天由 GitHub Actions 运行（或本地手动运行），按当天日期确定性抽取内容，
写出：
  - content.json        (manifest 顶层，含 news/knowledge/cooking/csp/题库索引)
  - q-primary.json      (小学题库，按学科分)
  - q-junior.json       (初中题库)
  - q-senior.json       (高中题库)

App 端（study_workspace.html）已对接该 manifest：
  - 新闻：优先服务端抓取中国新闻网当日实时 RSS（fetch_live_news），失败回退内置池轮播
  - 常识/菜谱/编程题 每天自动轮播不同子集 → 体感"每天更新"
  - 题库通过 q-*.json 按需拉取，可按学段独立更新

字段严格对齐 App 消费逻辑（见 study_workspace.html）：
  news/knowledge 条目: {id,category,title,readMin,summary,paras[],source}
  cooking.recipes:     {id,emoji,title,category,level,timeMin,ingredients[],steps[],tip}
  cooking.tips:        {id,emoji,title,text}
  cspLessons:          {id,title,desc,sections[],exercise{}}
  cspProblems:         {title,desc,difficulty,problemText,inputDesc,outputDesc,
                        sampleInput,sampleOutput,hint{approach,pitfall,extension},template,solution}
  题库题:              {id,type,difficulty,knowledgePoint,question,options[],answer,hint{...}}
"""
import json
import os
import datetime

# ----------------------------------------------------------------------------
# 工具：确定性按天轮播
# ----------------------------------------------------------------------------
def day_number(d=None):
    d = d or datetime.date.today()
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    return d.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def pick(pool, n, seed):
    """从 pool 中按 seed 取一个确定性滑动窗口子集。"""
    N = len(pool)
    if N == 0:
        return []
    start = seed % N
    out = []
    for i in range(min(n, N)):
        out.append(pool[(start + i) % N])
    return out


def fetch_live_news():
    """服务端抓取中国新闻网即时新闻 RSS（当日实时）。

    在 GitHub Actions 里运行没有浏览器 CORS 限制，可抓到真·当日新闻；
    本地/无网/解析失败时返回 None，调用方自动回退内置池（幂等安全）。
    条目字段严格对齐 App 消费 schema：{id,category,title,readMin,summary,paras[],source}
    """
    import re as _re
    import hashlib as _hl
    import urllib.request as _ur

    url = "https://www.chinanews.com.cn/rss/scroll-news.xml"
    try:
        req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0 (study-content-bot)"})
        xml = _ur.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
    except Exception:
        return None
    items = _re.findall(r"<item>(.*?)</item>", xml, _re.S)
    out = []
    for it in items[:12]:
        def g(tag):
            m = _re.search(r"<%s>(.*?)</%s>" % (tag, tag), it, _re.S)
            return _re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
        title = g("title")
        desc = g("description")
        link = g("link")
        cat = g("category") or "要闻"
        if not title:
            continue
        out.append({
            "id": "cn_" + _hl.md5((title + link).encode("utf-8")).hexdigest()[:10],
            "category": cat,
            "title": title,
            "readMin": max(1, len(title) // 30),
            "summary": (desc or "")[:120],
            "paras": [desc] if desc else [title],
            "source": "中国新闻网（每日自动抓取）",
        })
    return out if len(out) >= 5 else None


# ============================================================================
# 内容大池（MASTER）
# 说明：池子越大，"每天不同"的循环周期越长。可随时往这里手动加新内容。
# ============================================================================

NEWS_POOL = [
    {"id": "rn01", "category": "科技前沿", "title": "神舟飞船再探天宫", "readMin": 3,
     "summary": "我国航天员乘神舟飞船再次进驻空间站，开展太空科学实验。",
     "paras": ["神舟飞船是中国自主研制的载人飞船，能把航天员安全送到空间站。",
             "在空间站里，科学家可以做失重环境下的材料、生物等实验，很多在地面上做不到。",
             "一次次成功发射，说明中国航天技术已经非常成熟可靠。"],
     "source": "学习台编辑部"},
    {"id": "rn02", "category": "科学探索", "title": "月球背面长什么样", "readMin": 3,
     "summary": "嫦娥探测器拍回了月球背面的清晰照片，那里和正面很不一样。",
     "paras": ["月亮总用同一面对着地球，背面我们平时看不到。",
             "月球背面坑更多、更古老，藏着太阳系早期的秘密。",
             "中国探测器率先在月背软着陆，还带了月球样品回来研究。"],
     "source": "学习台编辑部"},
    {"id": "rn03", "category": "自然万物", "title": "蜜蜂为什么会跳舞", "readMin": 3,
     "summary": "蜜蜂发现花蜜后，会跳'8字舞'告诉同伴花在哪里。",
     "paras": ["蜜蜂的'摇摆舞'能指出食物的方向和距离。",
             "太阳是它们的指南针，舞蹈角度对应太阳的方向。",
             "一只蜜蜂找到蜜源，整个蜂群都能高效采集，非常聪明。"],
     "source": "学习台编辑部"},
    {"id": "rn04", "category": "社会百科", "title": "高铁是怎样提速的", "readMin": 3,
     "summary": "中国高铁又快又稳，靠的是无缝钢轨、流线车头和精密调度。",
     "paras": ["普通铁路有缝隙会'咣当'响，高铁用无缝长钢轨，跑起来更平顺。",
             "车头做成流线型，像子弹一样把空气分开，减少阻力。",
             "强大的调度系统让一列列车安全有序地飞驰。"],
     "source": "学习台编辑部"},
    {"id": "rn05", "category": "健康生活", "title": "为什么要早睡早起", "readMin": 2,
     "summary": "充足睡眠能帮助大脑记忆、身体长高，长期熬夜会伤身。",
     "paras": ["睡眠时大脑会整理白天学的知识，像把文件归档。",
             "生长激素多在深睡时分泌，儿童尤其需要早睡。",
             "规律作息让人白天更有精神、学习更专注。"],
     "source": "学习台编辑部"},
    {"id": "rn06", "category": "历史故事", "title": "丝绸之路上的驼铃声", "readMin": 3,
     "summary": "古代商人赶着骆驼，把中国的丝绸运到西方，也带回异域物产。",
     "paras": ["张骞出使西域，打通了连接东西方的商路。",
             "丝绸、瓷器向西走，葡萄、香料、宝石向东来。",
             "这条路不仅是买卖，更是文明交流的桥梁。"],
     "source": "学习台编辑部"},
    {"id": "rn07", "category": "科技前沿", "title": "人工智能如何认图", "readMin": 3,
     "summary": "AI 通过大量图片学习，逐渐能认出猫狗、人和各种物体。",
     "paras": ["就像小朋友看很多次猫，才学会认猫。",
             "计算机会把图片变成数字，找出'猫'的共同特征。",
             "现在 AI 还能画画、写作、对话，帮我们做很多事。"],
     "source": "学习台编辑部"},
    {"id": "rn08", "category": "科学探索", "title": "北极为什么那么冷", "readMin": 3,
     "summary": "北极太阳辐射弱、冰雪又反射阳光，所以终年严寒。",
     "paras": ["地球是斜着转的，北极有半年见不到太阳。",
             "冰雪白白的，把阳光大部分反射回天空，留不住热量。",
             "全球变暖让北极冰融化加快，会影响全世界的天气。"],
     "source": "学习台编辑部"},
    {"id": "rn09", "category": "自然万物", "title": "竹子为什么长得快", "readMin": 2,
     "summary": "竹子用地下茎积蓄多年力量，一旦冒头几天就能蹿很高。",
     "paras": ["竹笋在地下连着粗壮的竹鞭，藏着充足养分。",
             "雨后温度合适，它便迅速拔节，一天能长几十厘米。",
             "竹子中空有节，又轻又韧，是很好的材料。"],
     "source": "学习台编辑部"},
    {"id": "rn10", "category": "文化艺术", "title": "成语里的历史", "readMin": 3,
     "summary": "很多成语来自真实故事，读懂它就像翻开一页历史。",
     "paras": ["'一鸣惊人'讲楚庄王三年不鸣、一鸣惊人的故事。",
             "'卧薪尝胆'说越王勾践忍辱负重、终报大仇。",
             "一个四字成语，往往藏着古人智慧与经验教训。"],
     "source": "学习台编辑部"},
    {"id": "rn11", "category": "科学探索", "title": "彩虹是怎么来的", "readMin": 2,
     "summary": "雨后阳光穿过小水珠，被分成七色，就出现了彩虹。",
     "paras": ["阳光看着是白的，其实由红橙黄绿蓝靛紫七色组成。",
             "小水珠像三棱镜，把光'掰'成七色。",
             "背对太阳、面向水雾，最容易看到彩虹。"],
     "source": "学习台编辑部"},
    {"id": "rn12", "category": "社会百科", "title": "图书馆为什么安静", "readMin": 2,
     "summary": "安静的环境让人专注阅读与思考，是图书馆的默契。",
     "paras": ["很多人同时看书，一点杂音都会被放大。",
             "安静也是一种对他人的尊重。",
             "现在也有讨论区，方便小组交流学习。"],
     "source": "学习台编辑部"},
    {"id": "rn13", "category": "科技前沿", "title": "电动汽车靠什么跑", "readMin": 3,
     "summary": "电动汽车用电池驱动电机，比燃油车更安静、更清洁。",
     "paras": ["大容量电池像'移动充电宝'，存下电能。",
             "电机把电变成动力，没有尾气排放。",
             "充电桩越建越多，长途出行也越来越方便。"],
     "source": "学习台编辑部"},
    {"id": "rn14", "category": "健康生活", "title": "多喝水有什么用", "readMin": 2,
     "summary": "水参与身体里几乎所有反应，帮助运输营养、排出废物。",
     "paras": ["人离不开水，几天不喝水就很危险。",
             "运动出汗后更要及时补水。",
             "白开水是最好的饮料，少喝太甜的饮品。"],
     "source": "学习台编辑部"},
    {"id": "rn15", "category": "自然万物", "title": "候鸟如何认路", "readMin": 3,
     "summary": "大雁排成人字南飞，靠太阳、星星和地磁找到回家的路。",
     "paras": ["鸟类体内像有指南针，能感知地球磁场。",
             "人字形队形省力，后面的鸟借前面气流飞行。",
             "它们年复一年往返，从不迷路，令人惊叹。"],
     "source": "学习台编辑部"},
    {"id": "rn16", "category": "历史故事", "title": "万里长城的故事", "readMin": 3,
     "summary": "古人修建长城抵御外敌，它今天是世界闻名的奇迹。",
     "paras": ["长城沿山脊蜿蜒，像一条巨龙。",
             "它是无数劳动者一砖一石垒起来的。",
             "如今长城象征坚韧，吸引着世界各地游客。"],
     "source": "学习台编辑部"},
    {"id": "rn17", "category": "科学探索", "title": "声音也能看见吗", "readMin": 2,
     "summary": "声音是振动，用仪器能把它画成起伏的波形图。",
     "paras": ["敲鼓时鼓面在快速抖动，这就是振动。",
             "振动越快，声音越尖；越慢，声音越低。",
             "示波器能把声音变成看得见的曲线。"],
     "source": "学习台编辑部"},
    {"id": "rn18", "category": "文化艺术", "title": "京剧的脸谱密码", "readMin": 3,
     "summary": "京剧用不同颜色和图案的脸谱，代表人物性格。",
     "paras": ["红脸常表忠勇，如关羽；黑脸表刚正，如包公。",
             "白脸多表奸诈，蓝绿脸常是草莽英雄。",
             "脸谱是夸张的艺术，一眼就能看懂角色。"],
     "source": "学习台编辑部"},
    {"id": "rn19", "category": "科技前沿", "title": "北斗导航怎样指路", "readMin": 3,
     "summary": "北斗卫星在天上的网络，让手机能精准定位到几米内。",
     "paras": ["多颗卫星同时测距，交点就是你的位置。",
             "北斗还能发短报文，没信号也能报平安。",
             "导航、打车、搜救都离不开它。"],
     "source": "学习台编辑部"},
    {"id": "rn20", "category": "趣味常识", "title": "为什么星星会眨眼", "readMin": 2,
     "summary": "星光穿过晃动的大气层，看起来就一闪一闪的。",
     "paras": ["高空气流让空气密度不断变化。",
             "光经过时路线被轻微弯折，亮度忽明忽暗。",
             "在太空望远镜里，星星是不眨眼的。"],
     "source": "学习台编辑部"},
]

KNOWLEDGE_POOL = [
    {"id": "rk01", "category": "科学探索", "title": "为什么海水是咸的", "readMin": 3,
     "summary": "河水把岩石里的盐分带进大海，海水被太阳晒蒸发，盐却留了下来。",
     "paras": ["雨水流过岩石土壤，溶解少量矿物质和盐类，汇入江河，最后流入大海。",
             "太阳把海面部分水变成水蒸气升上天空，盐却留在海里，千万年积累变咸。",
             "死海几乎只进不出，盐度特别高，人躺上去都不容易沉下去。"],
     "source": "学习台知识库"},
    {"id": "rk02", "category": "科技前沿", "title": "二维码里藏了多少信息", "readMin": 3,
     "summary": "黑白小方块用排列组合记下网址文字，手机一扫就懂。",
     "paras": ["二维码由很多小方格组成，黑格白格代表0和1，不同位置存数据、纠错和定位。",
             "三个角的大方块是'定位标'，手机靠它们摆正方向，斜着扫也能识别。",
             "因为加了纠错码，弄脏一小块也还能扫出来。"],
     "source": "学习台知识库"},
    {"id": "rk03", "category": "自然万物", "title": "树叶秋天为什么会变黄", "readMin": 3,
     "summary": "秋天日照变短，叶子里的叶绿素减少，原本被盖住的颜色就显出来。",
     "paras": ["夏天叶子绿，是因为大量叶绿素在工作。",
             "秋天天气转凉，树木回收养分，叶绿素分解，叶黄素、花青素露面。",
             "枫叶变红，是花青素在低温里增多造成的。"],
     "source": "学习台知识库"},
    {"id": "rk04", "category": "科学探索", "title": "闪电是怎么发生的", "readMin": 3,
     "summary": "云里正负电荷分开，放电时就出现耀眼的闪电和雷声。",
     "paras": ["云中冰晶碰撞，使顶部带正电、底部带负电。",
             "电荷差大到一定程度，空气被击穿，形成闪电。",
             "光比声快，所以先见闪电后闻雷声。"],
     "source": "学习台知识库"},
    {"id": "rk05", "category": "健康生活", "title": "洗手为什么能防病", "readMin": 2,
     "summary": "用洗手液认真洗手，能冲走手上的细菌和病毒。",
     "paras": ["手每天摸很多东西，容易沾上病菌。",
             "七步洗手法、搓够20秒，才洗得干净。",
             "饭前便后、外出回家都要洗手。"],
     "source": "学习台知识库"},
    {"id": "rk06", "category": "社会百科", "title": "人民币上的风景", "readMin": 3,
     "summary": "纸币背面印着祖国名山大川，是移动的国家名片。",
     "paras": ["一元背面是杭州西湖的三潭印月。",
             "一百元背面是人民大会堂，庄严又气派。",
             "看着这些风景，也能认识祖国的大好河山。"],
     "source": "学习台知识库"},
    {"id": "rk07", "category": "趣味常识", "title": "先有鸡还是先有蛋", "readMin": 3,
     "summary": "从演化看，是'先有蛋'——鸟类由恐龙演化，蛋早存在亿万年。",
     "paras": ["恐龙时代就有蛋，比鸡出现早得多。",
             "现代鸡由远古鸟类逐渐演化而来。",
             "所以严格说，会下'鸡蛋'的鸡之前，蛋早就有了。"],
     "source": "学习台知识库"},
    {"id": "rk08", "category": "科学探索", "title": "黑洞是什么", "readMin": 3,
     "summary": "黑洞引力极强，连光都逃不掉，是宇宙中最神秘的天体之一。",
     "paras": ["当大质量恒星燃料耗尽、塌缩，可能形成黑洞。",
             "它的边界叫'事件视界'，进去就回不来。",
             "科学家用间接方法'拍'到了黑洞的影子。"],
     "source": "学习台知识库"},
    {"id": "rk09", "category": "自然万物", "title": "珊瑚是植物还是动物", "readMin": 2,
     "summary": "珊瑚是动物，由无数小珊瑚虫分泌碳酸钙堆积而成。",
     "paras": ["珊瑚虫像 tiny 的水母亲戚，会捕食浮游生物。",
             "它们死后骨骼留存，一代代堆成珊瑚礁。",
             "色彩斑斓的珊瑚礁是海洋里的'热带雨林'。"],
     "source": "学习台知识库"},
    {"id": "rk10", "category": "文化艺术", "title": "楷书行书草书有什么区别", "readMin": 3,
     "summary": "它们是汉字的不同书写风格，由工整到奔放。",
     "paras": ["楷书横平竖直，最工整，适合认读。",
             "行书连笔流畅，日常书写常用。",
             "草书笔画简省连绵，艺术性强但难认。"],
     "source": "学习台知识库"},
    {"id": "rk11", "category": "科学探索", "title": "冰箱为什么能保鲜", "readMin": 2,
     "summary": "低温让细菌和食物里的化学反应变慢，东西就不容易坏。",
     "paras": ["细菌在常温下繁殖快，食物易变质。",
             "冷藏延缓变质，冷冻更能长期保存。",
             "但冰箱不是保险箱，放太久也会坏。"],
     "source": "学习台知识库"},
    {"id": "rk12", "category": "社会百科", "title": "快递是怎么到你家的", "readMin": 3,
     "summary": "从下单到收货，包裹要经过分拣、运输、派送多个环节。",
     "paras": ["仓库按地址把包裹分到不同流向。",
             "大货车、飞机、高铁把包裹运往各地。",
             "快递员最后送到你手里，背后是一整套物流网。"],
     "source": "学习台知识库"},
    {"id": "rk13", "category": "自然万物", "title": "猫为什么爱舔毛", "readMin": 2,
     "summary": "猫舔毛是在清洁、降温，也能缓解紧张。",
     "paras": ["舌头上的倒刺能梳掉脏东西和掉毛。",
             "唾液蒸发帮猫在热天降温。",
             "紧张时舔毛，是猫自我安慰的方式。"],
     "source": "学习台知识库"},
    {"id": "rk14", "category": "健康生活", "title": "保护视力小妙招", "readMin": 2,
     "summary": "多到户外、少盯屏幕、读写姿势端正，眼睛更舒服。",
     "paras": ["每天户外两小时，能延缓近视发生。",
             "看书保持一尺距离，光线要充足。",
             "用眼20分钟，远眺20秒，给眼睛放假。"],
     "source": "学习台知识库"},
    {"id": "rk15", "category": "科学探索", "title": "火山为什么会喷发", "readMin": 3,
     "summary": "地下岩浆压力大，沿薄弱处冲出地表，就形成火山喷发。",
     "paras": ["地球内部很热，岩石熔化形成岩浆。",
             "岩浆比周围轻，会往上挤。",
             "找到裂缝就喷涌而出，带来新的土地。"],
     "source": "学习台知识库"},
    {"id": "rk16", "category": "趣味常识", "title": "一年为什么有四季", "readMin": 3,
     "summary": "地球歪着身子绕太阳转，不同地区受光不同，就有了四季。",
     "paras": ["地轴倾斜约23.5度，不是正着转的。",
             "北半球倾向太阳时是夏天，背向时是冬天。",
             "南北半球季节正好相反。"],
     "source": "学习台知识库"},
    {"id": "rk17", "category": "历史故事", "title": "活字印刷是谁发明的", "readMin": 3,
     "summary": "北宋毕昇发明了活字印刷，比欧洲早了好几百年。",
     "paras": ["先用胶泥刻字、烧硬，排版后刷墨印刷。",
             "字可以拆下重排，比整版雕刻省事。",
             "这是印刷史上一大飞跃，影响全世界。"],
     "source": "学习台知识库"},
    {"id": "rk18", "category": "科技前沿", "title": "无人机靠什么飞", "readMin": 3,
     "summary": "多旋翼无人机靠几个螺旋桨配合，实现悬停和飞行。",
     "paras": ["转速不同，就能前进、转向、升降。",
             "陀螺仪和传感器帮它保持平稳。",
             "航拍、送药、巡检都能用到它。"],
     "source": "学习台知识库"},
    {"id": "rk19", "category": "自然万物", "title": "含羞草为什么会合拢", "readMin": 2,
     "summary": "触碰含羞草，叶枕里的水分会迅速流走，叶子就垂下来。",
     "paras": ["这是植物的'防御反应'，吓退想吃它的动物。",
             "过几分钟水分回流，叶子又张开。",
             "它像植物里的'害羞小孩'，很可爱。"],
     "source": "学习台知识库"},
    {"id": "rk20", "category": "文化艺术", "title": "十二生肖怎么来的", "readMin": 3,
     "summary": "传说玉皇大帝办赛跑，前十二名动物成为生肖。",
     "paras": ["鼠骑在牛背上，最后跳下夺了第一。",
             "龙因降雨迟到，排在第五。",
             "生肖十二年一轮，用来记年很有趣。"],
     "source": "学习台知识库"},
    {"id": "rk21", "category": "科学探索", "title": "月亮为什么有阴晴圆缺", "readMin": 3,
     "summary": "月亮本身不发光，我们看到的形状随它绕地球的位置变化。",
     "paras": ["月亮被太阳照亮，但我们从不同角度看亮面。",
             "满月时亮面正对我们，新月时几乎看不见。",
             "一个周期约29.5天，叫朔望月。"],
     "source": "学习台知识库"},
    {"id": "rk22", "category": "社会百科", "title": "垃圾分类有什么用", "readMin": 2,
     "summary": "分类能让可回收物再利用，有害垃圾安全处理，减少污染。",
     "paras": ["废纸塑料金属能变回资源。",
             "电池灯管含毒，要单独处理。",
             "厨余垃圾可堆肥，变废为宝。"],
     "source": "学习台知识库"},
    {"id": "rk23", "category": "健康生活", "title": "早餐为什么重要", "readMin": 2,
     "summary": "一夜没进食，早餐给身体和大脑补充能量，开启一天。",
     "paras": ["不吃早餐容易上午没精神、注意力不集中。",
             "优质早餐有主食、蛋白和蔬菜更好。",
             "规律吃早餐有助于健康成长。"],
     "source": "学习台知识库"},
    {"id": "rk24", "category": "趣味常识", "title": "蚂蚁如何找回家", "readMin": 2,
     "summary": "蚂蚁沿途留下气味，顺着气味路标就能带回巢穴。",
     "paras": ["腹部腺体分泌信息素，画成'香味小路'。",
             "同伴跟着气味走，还能一起搬大食物。",
             "路断了，它们会重新探路留下新气味。"],
     "source": "学习台知识库"},
    {"id": "rk25", "category": "科学探索", "title": "彩虹之外还有颜色吗", "readMin": 3,
     "summary": "人眼只看到七色，其实光里还有看不见的红外和紫外。",
     "paras": ["红光之外是红外线，我们有时会感到热。",
             "紫光之外是紫外线，晒多了会伤皮肤。",
             "蜜蜂能看到紫外花纹，引导它找花蜜。"],
     "source": "学习台知识库"},
    {"id": "rk26", "category": "自然万物", "title": "鲸鱼不是鱼", "readMin": 2,
     "summary": "鲸用肺呼吸、胎生哺乳，其实是哺乳动物。",
     "paras": ["鲸要浮出水面换气，喷出的水柱是废气。",
             "小鲸靠喝母乳长大，和牛马一样。",
             "它祖先曾是陆地动物，后来回到海里生活。"],
     "source": "学习台知识库"},
    {"id": "rk27", "category": "历史故事", "title": "造纸术的来历", "readMin": 3,
     "summary": "东汉蔡伦改进造纸术，用树皮破布做出便宜好用的纸。",
     "paras": ["更早人们把字刻在竹简、写在丝帛上，都不方便。",
             "蔡伦用树皮、麻头、破布捣烂成浆，晾干成纸。",
             "造纸术传到世界，推动了文化传播。"],
     "source": "学习台知识库"},
    {"id": "rk28", "category": "科技前沿", "title": "机器人怎样走路", "readMin": 3,
     "summary": "机器人靠传感器感知、控制器计算、电机驱动来移动。",
     "paras": ["摄像头和雷达像它的眼睛。",
             "芯片快速决策先迈哪条腿。",
             "有的用轮子，有的用腿，有的甚至能后空翻。"],
     "source": "学习台知识库"},
    {"id": "rk29", "category": "健康生活", "title": "为什么运动让人快乐", "readMin": 2,
     "summary": "运动后大脑会分泌让人愉悦的物质，心情更轻松。",
     "paras": ["跑步跳舞后常觉得痛快淋漓。",
             "运动还能改善睡眠、增强抵抗力。",
             "每天动一动，学习和游戏都更有劲。"],
     "source": "学习台知识库"},
    {"id": "rk30", "category": "趣味常识", "title": "为什么会有回声", "readMin": 2,
     "summary": "声音碰到墙壁大山反弹回来，就听到重复的回声。",
     "paras": ["在空旷山谷大喊，会听见自己的声音回来。",
             "墙壁越硬越平，回声越清楚。",
             "太近的墙回声和原声重叠，就听不出来了。"],
     "source": "学习台知识库"},
    {"id": "rk31", "category": "科学探索", "title": "地球内部是什么样", "readMin": 3,
     "summary": "地球像颗糖葫芦：外壳是地壳，中间地幔，最里是火热地核。",
     "paras": ["我们站在薄薄的地壳上。",
             "地幔是缓慢流动的炽热岩石。",
             "地核温度极高，主要是铁和镍。"],
     "source": "学习台知识库"},
    {"id": "rk32", "category": "自然万物", "title": "向日葵为什么追太阳", "readMin": 2,
     "summary": "生长中的向日葵随日照转动，成熟后多固定朝东。",
     "paras": ["幼嫩花盘里的生长素怕光，背光侧长得快，把它推向太阳。",
             "长大后重心稳了，常朝东迎早阳。",
             "追太阳能让花更暖、吸引更多蜜蜂。"],
     "source": "学习台知识库"},
    {"id": "rk33", "category": "社会百科", "title": "红绿灯为什么是红黄绿", "readMin": 2,
     "summary": "红色最醒目代表停，绿色代表行，黄色提醒准备。",
     "paras": ["红光波长穿透力强，远处也看得见。",
             "这套规则全球通用，避免混乱。",
             "遵守信号灯，过马路才安全。"],
     "source": "学习台知识库"},
    {"id": "rk34", "category": "文化艺术", "title": "水墨画为什么多为黑白", "readMin": 3,
     "summary": "传统水墨以浓淡墨色表现远近虚实，讲究意境。",
     "paras": ["墨分五色，靠水分多少画出层次。",
             "留白不是空，是给人想象的空间。",
             "不求形似求神似，是东方美学。"],
     "source": "学习台知识库"},
    {"id": "rk35", "category": "科学探索", "title": "云是怎么变成雨的", "readMin": 3,
     "summary": "水汽遇冷凝成小水滴，越聚越多变重，就落下来成雨。",
     "paras": ["太阳晒热水面，水汽升上天空。",
             "高空冷，水汽凝在小尘埃上成云。",
             "水滴变大撑不住，便纷纷落下。"],
     "source": "学习台知识库"},
    {"id": "rk36", "category": "健康生活", "title": "牙齿为什么要刷两次", "readMin": 2,
     "summary": "早晚刷牙能清除食物残渣和细菌，保护牙齿不得蛀牙。",
     "paras": ["夜里唾液少，细菌容易繁殖。",
             "用含氟牙膏、每次刷够三分钟。",
             "饭后漱口、少吃糖，牙齿更坚固。"],
     "source": "学习台知识库"},
]

COOKING_RECIPES = [
    {"id": "c_rec1", "emoji": "🍅", "title": "西红柿炒鸡蛋", "category": "家常菜", "level": "★", "timeMin": 10,
     "ingredients": ["西红柿 2 个", "鸡蛋 2 个", "小葱 少许", "盐 适量", "食用油 适量"],
     "steps": ["鸡蛋打散加少许盐搅匀；", "西红柿去蒂切块；", "热锅少油，倒入蛋液炒至凝固盛出；",
             "锅留底油下西红柿，炒出红汁；", "倒入鸡蛋翻匀，撒葱花出锅。"],
     "tip": "鸡蛋嫩炒、西红柿炒出汁，味道最香。"},
    {"id": "c_rec2", "emoji": "🥗", "title": "缤纷水果沙拉", "category": "免开火", "level": "★", "timeMin": 8,
     "ingredients": ["苹果 1 个", "香蕉 1 根", "草莓 6 颗", "酸奶 2 勺"],
     "steps": ["水果用清水洗净；", "苹果、香蕉切小块；", "草莓对半切开；", "淋上酸奶轻轻拌匀即可。"],
     "tip": "现做现吃，放久苹果容易氧化变黄。"},
    {"id": "c_rec3", "emoji": "🍜", "title": "元气煮面条", "category": "主食", "level": "★", "timeMin": 12,
     "ingredients": ["面条 1 把", "小青菜 1 把", "鸡蛋 1 个", "生抽 1 勺"],
     "steps": ["锅里水烧开，下直面；", "青菜洗净后放入同煮；", "另起小锅少油煎一个荷包蛋；", "面熟捞起，加生抽，摆上煎蛋。"],
     "tip": "水要多一些，面才不会黏成一团。"},
    {"id": "c_rec4", "emoji": "🍳", "title": "香煎太阳蛋", "category": "早餐", "level": "★", "timeMin": 5,
     "ingredients": ["鸡蛋 1 个", "食用油 几滴", "盐 少许"],
     "steps": ["平底锅预热，倒几滴油；", "磕入鸡蛋，转小火；", "蛋白凝固、边缘微焦时撒盐；", "用铲子轻推出锅。"],
     "tip": "一定要小火，蛋黄才嫩、不易糊。"},
    {"id": "c_rec5", "emoji": "🥣", "title": "燕麦酸奶杯", "category": "免开火", "level": "★", "timeMin": 6,
     "ingredients": ["即食燕麦 3 勺", "酸奶 4 勺", "蓝莓 1 把", "香蕉 半根"],
     "steps": ["杯底铺一层燕麦；", "倒一层酸奶；", "放蓝莓和香蕉片；", "再重复铺一层，好看又好吃。"],
     "tip": "做好放冰箱冷藏一会儿更爽口。"},
    {"id": "c_rec6", "emoji": "🥪", "title": "蔬菜三明治", "category": "免开火", "level": "★", "timeMin": 8,
     "ingredients": ["吐司 2 片", "黄瓜 几片", "番茄 几片", "奶酪片 1 片"],
     "steps": ["吐司平放，铺上奶酪片；", "摆上黄瓜片和番茄片；", "盖上另一片吐司；", "对角切成两个三角形。"],
     "tip": "番茄片用厨房纸吸去水分，吐司更酥不软。"},
    {"id": "c_rec7", "emoji": "🥚", "title": "水蒸蛋", "category": "家常菜", "level": "★", "timeMin": 15,
     "ingredients": ["鸡蛋 2 个", "温水 半碗", "生抽 几滴", "香油 几滴"],
     "steps": ["鸡蛋打散，加约1.5倍温水搅匀；", "过筛去泡，盖保鲜膜扎孔；", "上锅中小火蒸10分钟；", "出锅滴生抽香油即可。"],
     "tip": "用温水、过筛，蒸出来才嫩滑无蜂窝。"},
    {"id": "c_rec8", "emoji": "🍌", "title": "香蕉奶昔", "category": "饮品", "level": "★", "timeMin": 5,
     "ingredients": ["香蕉 1 根", "牛奶 1 杯", "蜂蜜 少许"],
     "steps": ["香蕉切片；", "和牛奶一起放入搅拌机；", "打成顺滑奶昔，喜甜加少许蜂蜜。"],
     "tip": "用冻香蕉更冰爽，像冰淇淋口感。"},
    {"id": "c_rec9", "emoji": "🥦", "title": "蒜蓉西兰花", "category": "家常菜", "level": "★", "timeMin": 10,
     "ingredients": ["西兰花 1 颗", "蒜 3 瓣", "盐 适量", "油 适量"],
     "steps": ["西兰花掰小朵，盐水泡洗；", "开水焯1分钟捞出；", "热油爆香蒜末；", "下西兰花翻炒，加盐出锅。"],
     "tip": "焯水保持翠绿，别煮太久发黄。"},
    {"id": "c_rec10", "emoji": "🍚", "title": "蛋炒饭", "category": "主食", "level": "★★", "timeMin": 12,
     "ingredients": ["隔夜米饭 1 碗", "鸡蛋 1 个", "葱花 少许", "生抽 1 勺", "油 适量"],
     "steps": ["蛋液打散；", "热油下蛋液炒散；", "倒入米饭炒散，压开结块；", "加生抽、葱花炒匀出锅。"],
     "tip": "用稍硬的隔夜饭，炒出来粒粒分明不黏。"},
    {"id": "c_rec11", "emoji": "🥣", "title": "南瓜浓汤", "category": "汤羹", "level": "★", "timeMin": 20,
     "ingredients": ["南瓜 300 克", "牛奶 1 杯", "盐 少许"],
     "steps": ["南瓜去皮切块蒸熟；", "加牛奶用搅拌机打成泥；", "倒锅小火加热，加盐调味。"],
     "tip": "喜欢顺滑可过滤一次，喜欢颗粒感直接喝。"},
    {"id": "c_rec12", "emoji": "🐟", "title": "清蒸鱼", "category": "家常菜", "level": "★★", "timeMin": 20,
     "ingredients": ["鱼 1 条", "姜 几片", "葱 1 根", "蒸鱼豉油 1 勺"],
     "steps": ["鱼洗净两面划刀，铺姜片；", "水开上锅蒸8分钟；", "倒掉腥水，铺葱丝；", "淋热油激香，浇豉油。"],
     "tip": "蒸的时间看鱼大小，过了肉就老。"},
    {"id": "c_rec13", "emoji": "🥔", "title": "香煎土豆丝饼", "category": "主食", "level": "★★", "timeMin": 18,
     "ingredients": ["土豆 2 个", "胡萝卜 半个", "盐 适量", "油 适量"],
     "steps": ["土豆胡萝卜擦细丝；", "加盐拌匀稍腌出水；", "热油小火摊成小饼；", "两面煎金黄即可。"],
     "tip": "丝要细，容易熟透且更脆。"},
    {"id": "c_rec14", "emoji": "🍞", "title": "牛奶吐司布丁", "category": "甜点", "level": "★", "timeMin": 25,
     "ingredients": ["吐司 2 片", "鸡蛋 1 个", "牛奶 1 杯", "糖 1 勺"],
     "steps": ["吐司切小块铺碗底；", "鸡蛋牛奶糖搅匀淋上；", "静置10分钟入味；", "烤箱180度烤20分钟。"],
     "tip": "没有烤箱可上锅蒸，口感更嫩。"},
    {"id": "c_rec15", "emoji": "🥬", "title": "清炒小白菜", "category": "家常菜", "level": "★", "timeMin": 8,
     "ingredients": ["小白菜 1 把", "蒜 2 瓣", "盐 适量", "油 适量"],
     "steps": ["小白菜洗净切段；", "热油爆香蒜；", "下菜大火快炒；", "加盐翻匀出锅。"],
     "tip": "大火快炒保脆嫩，出水就不好吃了。"},
    {"id": "c_rec16", "emoji": "🍎", "title": "烤苹果片", "category": "甜点", "level": "★", "timeMin": 40,
     "ingredients": ["苹果 2 个", "肉桂粉 少许（可选）"],
     "steps": ["苹果切薄片；", "平铺烤盘；", "100度烤30-40分钟至干脆；", "凉后密封保存。"],
     "tip": "薄而均匀才脆，厚了会韧。"},
]

COOKING_TIPS = [
    {"id": "c_tip1", "emoji": "🧼", "title": "七步洗手法", "text": "处理食材前、饭前便后都要用洗手液把手洗干净，至少20秒。"},
    {"id": "c_tip2", "emoji": "🔪", "title": "刀具安全", "text": "用刀时专心看手，刀尖不对人；用完立刻洗净归位，不要泡在水里。"},
    {"id": "c_tip3", "emoji": "🥩", "title": "生熟分开", "text": "生肉和熟食要用不同的砧板与餐具，避免细菌交叉污染。"},
    {"id": "c_tip4", "emoji": "🔥", "title": "火候判断", "text": "油面冒少许青烟再下菜；煎炒用小火慢来，不容易糊锅。"},
    {"id": "c_tip5", "emoji": "🧂", "title": "调味适量", "text": "盐糖少量多次放，边做边尝，既健康又不会过咸过甜。"},
    {"id": "c_tip6", "emoji": "🌡️", "title": "煮熟确认", "text": "肉禽蛋类要彻底煮熟，中心不再粉红、汤汁清澈才安全。"},
]

CSP_LESSONS = [
    {"id": 1, "title": "枚举与模拟", "desc": "CSP-J最基础也最核心的算法思想",
     "sections": [
        {"type": "text", "content": "枚举（暴力）和模拟是CSP-J复赛中最基础的算法思想。枚举是逐一尝试所有可能的情况，模拟是按照题目描述的规则一步步操作。"},
        {"type": "code", "code": r"""#include <iostream>
using namespace std;

int main() {
    int n;
    cin >> n;
    // 枚举 1 到 n 中 3 的倍数
    for (int i = 1; i <= n; i++) {
        if (i % 3 == 0) {
            cout << i << " ";
        }
    }
    cout << endl;
    return 0;
}"""},
        {"type": "explain", "title": "枚举的核心要点", "items": [
            "确定枚举范围：明确变量的取值范围，不遗漏不重复",
            "确定枚举顺序：根据题意选择合适的遍历顺序",
            "优化剪枝：通过分析条件提前终止不可能的情况",
            "注意数据范围：n<=1e6 可以O(n)枚举，n<=1e3 可以O(n^2)枚举",
            "CSP-J技巧：先写暴力枚举拿部分分，再想优化算法"]},
        {"type": "tip", "content": "CSP-J复赛策略：每道题先想暴力怎么做！即使想不出正解，暴力枚举也能拿到30-60分。先把暴力写对，再考虑优化。"}
     ],
     "exercise": {"prompt": "输入n，输出1到n中所有既能被3整除又能被5整除的数（即15的倍数）。",
                  "template": r"""#include <iostream>
using namespace std;

int main() {
    int n;
    cin >> n;
    // 在这里写代码

    return 0;
}""",
                  "expected": ""}},
    {"id": 2, "title": "贪心算法", "desc": "局部最优推导全局最优",
     "sections": [
        {"type": "text", "content": "贪心算法在每一步选择中都采取当前状态下的最优选择，期望最终得到全局最优解。贪心的关键是证明'局部最优=全局最优'。"},
        {"type": "code", "code": r"""#include <iostream>
#include <algorithm>
using namespace std;

int coins[] = {100, 50, 20, 10, 5, 1};

int main() {
    int n; cin >> n;
    int count = 0;
    for (int i = 0; i < 6; i++) {
        count += n / coins[i];
        n %= coins[i];
    }
    cout << count << endl;
    return 0;
}"""},
        {"type": "explain", "title": "贪心常见模型", "items": [
            "区间调度：按结束时间排序，选不冲突的最多区间",
            "排队接水：按服务时间从小到大排序，总等待时间最短",
            "哈夫曼编码：每次合并最小的两个",
            "找零问题：优先使用大面额纸币",
            "注意：贪心不一定对所有问题都正确！需要证明"]},
        {"type": "tip", "content": "贪心题的关键步骤：①确定贪心策略 ②排序 ③按序选择 ④验证正确性。如果不确定贪心是否正确，可以先写出来测试样例。"}
     ],
     "exercise": {"prompt": "有n个任务，每个任务有一个所需时间t。输入n个t，问最少能完成几个任务（按时间从小到大贪心）。",
                  "template": r"""#include <iostream>
#include <algorithm>
using namespace std;

int main() {
    int n; cin >> n;
    // 输入并排序，贪心选择

    return 0;
}""",
                  "expected": ""}},
    {"id": 3, "title": "排序算法", "desc": "冒泡、选择、插入与sort函数",
     "sections": [
        {"type": "text", "content": "排序是CSP-J的基础工具。比赛中可以直接用sort()函数，但理解排序原理对解题非常重要。"},
        {"type": "code", "code": r"""#include <iostream>
#include <algorithm>
using namespace std;

void bubbleSort(int a[], int n) {
    for (int i = 0; i < n - 1; i++)
        for (int j = 0; j < n - 1 - i; j++)
            if (a[j] > a[j + 1]) swap(a[j], a[j + 1]);
}

int main() {
    int n; cin >> n;
    int a[1005];
    for (int i = 0; i < n; i++) cin >> a[i];
    bubbleSort(a, n);
    for (int i = 0; i < n; i++) cout << a[i] << " ";
    return 0;
}"""},
        {"type": "explain", "title": "排序算法对比", "items": [
            "冒泡排序 O(n^2)：相邻比较交换，稳定",
            "选择排序 O(n^2)：每次选最小放前面，不稳定",
            "插入排序 O(n^2)：逐个插入已排序部分，稳定",
            "sort() O(n log n)：C++标准库，基于快排+堆排",
            "sort(a, a+n) 对数组排序；greater<int>() 降序"]},
        {"type": "tip", "content": "CSP-J中几乎都用sort()函数！头文件 #include <algorithm>。但笔试可能要求手写排序，三种基本排序都要会。"}
     ],
     "exercise": {"prompt": "输入n和n个整数，用sort()把它们从小到大输出。",
                  "template": r"""#include <iostream>
#include <algorithm>
using namespace std;

int main() {
    int n; cin >> n;
    int a[1005];
    // 读入并排序输出

    return 0;
}""",
                  "expected": ""}},
    {"id": 4, "title": "二分查找", "desc": "在有序序列中快速定位",
     "sections": [
        {"type": "text", "content": "二分查找要求序列有序。每次取中间元素比较，缩小一半查找范围，时间复杂度O(log n)。"},
        {"type": "code", "code": r"""#include <iostream>
using namespace std;

// 在 a[0..n-1] 中找 x，找到返回下标，否则返回 -1
int binarySearch(int a[], int n, int x) {
    int L = 0, R = n - 1;
    while (L <= R) {
        int mid = (L + R) / 2;
        if (a[mid] == x) return mid;
        if (a[mid] < x) L = mid + 1;
        else R = mid - 1;
    }
    return -1;
}"""},
        {"type": "explain", "title": "二分要点", "items": [
            "前提：序列必须有序",
            "循环中 L<=R，mid=(L+R)/2",
            "根据比较结果移动 L 或 R",
            "常用于答案具有单调性的'二分答案'题",
            "注意边界，避免死循环"]},
        {"type": "tip", "content": "二分答案：当'最大/最小'类问题满足单调性时，把答案当作枚举对象二分，用 check() 判断是否可行。"}
     ],
     "exercise": {"prompt": "输入有序数组和x，输出x的下标，不存在输出-1。",
                  "template": r"""#include <iostream>
using namespace std;

int main() {
    int n, x; cin >> n >> x;
    int a[1005];
    // 二分查找

    return 0;
}""",
                  "expected": ""}},
    {"id": 5, "title": "递归入门", "desc": "函数自己调用自己",
     "sections": [
        {"type": "text", "content": "递归是函数直接或间接调用自身。写递归要有两个要素：递归边界（何时停）和递归关系（怎么缩小问题）。"},
        {"type": "code", "code": r"""#include <iostream>
using namespace std;

int factorial(int n) {
    if (n <= 1) return 1;        // 递归边界
    return n * factorial(n - 1); // 递归关系
}

int main() {
    int n; cin >> n;
    cout << factorial(n) << endl;
    return 0;
}"""},
        {"type": "explain", "title": "递归三要素", "items": [
            "递归边界：最小的、能直接返回的情况",
            "递归关系：把大问题拆成小问题",
            "相信递归：假设小规模已正确，写出当前层",
            "太深会栈溢出，注意数据范围",
            "很多搜索、分治都靠递归"]},
        {"type": "tip", "content": "画递归树帮助理解：每个节点是一个调用，叶子是边界，从叶子往根回代得到答案。"}
     ],
     "exercise": {"prompt": "用递归求斐波那契数列第n项（f(1)=1,f(2)=1,f(n)=f(n-1)+f(n-2)）。",
                  "template": r"""#include <iostream>
using namespace std;

int fib(int n) {
    // 递归实现

}

int main() {
    int n; cin >> n;
    cout << fib(n) << endl;
    return 0;
}""",
                  "expected": ""}},
    {"id": 6, "title": "DFS 深度优先搜索", "desc": "一条路走到黑，再回头",
     "sections": [
        {"type": "text", "content": "DFS 像走迷宫：沿着一条路一直走，走不通就退回上一个岔路口换条路。常用递归实现，是排列组合、连通性、路径类题目的主力。"},
        {"type": "code", "code": r"""#include <iostream>
using namespace std;

int n, ans = 0;
int a[25];

void dfs(int i, int sum, int S) {
    if (i == n) { if (sum == S) ans++; return; }
    dfs(i + 1, sum, S);          // 不选
    dfs(i + 1, sum + a[i], S);   // 选
}

int main() {
    int S; cin >> n >> S;
    for (int i = 0; i < n; i++) cin >> a[i];
    dfs(0, 0, S);
    cout << ans << endl;
}"""},
        {"type": "explain", "title": "DFS 要点", "items": [
            "用递归参数表示'当前状态'",
            "到边界时判断/统计",
            "选与不选（或枚举每种选择）两种分支",
            "必要时用 vis 数组标记访问",
            "复杂度爆炸时注意剪枝"]},
        {"type": "tip", "content": "子集和问题：n<=20用DFS枚举，n较大且S较小用01背包DP。先判断数据范围再选方法。"}
     ],
     "exercise": {"prompt": "n个物品选若干使难度和恰好为S，输出方案数对1e9+7取模（n<=20）。",
                  "template": r"""#include <iostream>
using namespace std;

int n, S, ans = 0;
int a[25];

void dfs(int i, int sum) {
    // 补全 DFS

}

int main() {
    cin >> n >> S;
    for (int i = 0; i < n; i++) cin >> a[i];
    dfs(0, 0);
    cout << ans << endl;
}""",
                  "expected": ""}},
    {"id": 7, "title": "BFS 广度优先搜索", "desc": "层层扩散求最短路",
     "sections": [
        {"type": "text", "content": "BFS 从起点一层层向外扩展，第一次到达某点时的步数就是最短步数，适合迷宫最短路、状态最少步数等问题。"},
        {"type": "code", "code": r"""#include <iostream>
#include <queue>
using namespace std;

char maze[105][105];
int dist[105][105];
int dx[] = {0, 0, 1, -1};
int dy[] = {1, -1, 0, 0};

int main() {
    int n, m; cin >> n >> m;
    for (int i = 1; i <= n; i++)
        for (int j = 1; j <= m; j++) { cin >> maze[i][j]; dist[i][j] = -1; }
    queue<int> qx, qy;
    qx.push(1); qy.push(1); dist[1][1] = 0;
    while (!qx.empty()) {
        int x = qx.front(); qx.pop();
        int y = qy.front(); qy.pop();
        for (int k = 0; k < 4; k++) {
            int nx = x + dx[k], ny = y + dy[k];
            if (nx >= 1 && nx <= n && ny >= 1 && ny <= m
                && maze[nx][ny] == '.' && dist[nx][ny] == -1) {
                dist[nx][ny] = dist[x][y] + 1;
                qx.push(nx); qy.push(ny);
            }
        }
    }
    cout << dist[n][m] << endl;
}"""},
        {"type": "explain", "title": "BFS 要点", "items": [
            "用队列保存待访问点",
            "入队时标记 visited，避免重复",
            "方向数组 dx/dy 表示上下左右",
            "第一次到达即最短，可立即返回",
            "无权图最短路的标配"]},
        {"type": "tip", "content": "BFS 求最短路是 CSP-J 高频考点。变体：多起点 BFS、带传送门、双向 BFS。核心就是队列+访问标记+方向数组。"}
     ],
     "exercise": {"prompt": "给定迷宫（.可走 #墙），求左上到右下最少步数，不可达输出-1。",
                  "template": r"""#include <iostream>
#include <queue>
using namespace std;

// 用上面的 BFS 框架补全主函数读入与输出

int main() {
    return 0;
}""",
                  "expected": ""}},
    {"id": 8, "title": "字符串处理", "desc": "字符数组与常用操作",
     "sections": [
        {"type": "text", "content": "字符串题在CSP-J很常见：统计字符、反转、子串、进制转换等。C++里字符串可用 string 或 char 数组。"},
        {"type": "code", "code": r"""#include <iostream>
#include <string>
using namespace std;

int main() {
    string s; cin >> s;
    // 反转字符串
    string t = s;
    int L = 0, R = t.size() - 1;
    while (L < R) swap(t[L++], t[R--]);
    cout << t << endl;
    return 0;
}"""},
        {"type": "explain", "title": "字符串常用技巧", "items": [
            "s.size() 取长度；s[i] 取第i个字符",
            "用双指针反转、判断回文",
            "char 数组可用 strcpy/strlen（<cstring>）",
            "数字与字符互转：'0' 的差值是 48",
            "小心下标越界和末尾 '\\0'"]},
        {"type": "tip", "content": "回文题：双指针从两端向中间比，发现不同就不是回文。多练几道就有手感。"}
     ],
     "exercise": {"prompt": "输入一个字符串，判断它是否为回文（正读反读一样），是输出YES否则NO。",
                  "template": r"""#include <iostream>
#include <string>
using namespace std;

int main() {
    string s; cin >> s;
    // 判断回文

    return 0;
}""",
                  "expected": ""}},
]

CSP_PROBLEMS = [
    {"title": "买铅笔（CSP-J 2017 T1）", "desc": "模拟题 · 难度：入门", "difficulty": "easy",
     "problemText": "P老师需要买n支铅笔。商店有3种包装，不同包装内数量和价格可能不同，必须整包买。求最少花费。",
     "inputDesc": "第一行正整数n。接下来三行，每行两个正整数：一种包装的铅笔数量和价格。",
     "outputDesc": "一行一个整数，最少花费的钱数。",
     "sampleInput": "57\n2 2\n50 30\n30 27", "sampleOutput": "54",
     "hint": {"approach": "对每种包装，计算需要几包：向上取整 (n+cnt-1)/cnt，再乘单价。三种取最小。",
              "pitfall": "注意向上取整！n=57每包2支要29包。用整数 (n+cnt-1)/cnt，别用浮点 ceil 以免精度问题。",
              "extension": "模拟题关键是读懂题意、注意边界、整数运算做除法。"},
     "template": r"""#include <iostream>
#include <algorithm>
using namespace std;

int main() {
    int n; cin >> n;
    int ans = 1e9;
    for (int i = 0; i < 3; i++) {
        int cnt, price; cin >> cnt >> price;
        int bags = (n + cnt - 1) / cnt;
        ans = min(ans, bags * price);
    }
    cout << ans << endl;
    return 0;
}""",
     "solution": r"""#include <iostream>
#include <algorithm>
using namespace std;

int main() {
    int n; cin >> n;
    int ans = 1e9;
    for (int i = 0; i < 3; i++) {
        int cnt, price; cin >> cnt >> price;
        int bags = (n + cnt - 1) / cnt;
        ans = min(ans, bags * price);
    }
    cout << ans << endl;
    return 0;
}"""},
    {"title": "优秀的拆分（CSP-J 2020 T1）", "desc": "位运算/贪心 · 难度：简单", "difficulty": "easy",
     "problemText": "若正整数能拆成若干个不同的2的正整数次幂之和，则称优秀拆分。给定n，问优秀拆分方案数。",
     "inputDesc": "一行一个正整数n。", "outputDesc": "一行一个整数，方案数；不能拆分输出0。",
     "sampleInput": "6", "sampleOutput": "1",
     "hint": {"approach": "2的正整数次幂不含2^0=1。n为奇数无法拆分输出0；n为偶数方案唯一（二进制去掉最低位）。",
              "pitfall": "注意是2的正整数次幂，不含1！所以奇数直接输出0。",
              "extension": "考察二进制理解，二进制表示唯一，去掉最低位1即唯一方案。"},
     "template": r"""#include <iostream>
using namespace std;

int main() {
    int n; cin >> n;
    // 奇数输出 0，偶数输出 1

    return 0;
}""",
     "solution": r"""#include <iostream>
using namespace std;

int main() {
    int n; cin >> n;
    if (n % 2 == 1) cout << 0 << endl;
    else cout << 1 << endl;
    return 0;
}"""},
    {"title": "题库统计（子集和）", "desc": "枚举/模拟 · 难度：中等", "difficulty": "medium",
     "problemText": "n道题，每题难度a[i]。选若干题使难度和恰好为S，求方案数对1e9+7取模。",
     "inputDesc": "第一行n和S；第二行n个正整数a[i]。", "outputDesc": "一行方案数（取模）。",
     "sampleInput": "5 10\n1 2 3 4 5", "sampleOutput": "3",
     "hint": {"approach": "n<=20用DFS选或不选枚举；n大S小用01背包DP：dp[j]+=dp[j-a[i]]。",
              "pitfall": "DFS注意n范围，>20会超时；DP每次更新后取模，且01背包要逆序更新。",
              "extension": "经典子集和问题，先判断数据范围选方法。"},
     "template": r"""#include <iostream>
using namespace std;

int n, S, a[25], ans = 0;
void dfs(int i, int sum) {
    // 补全
}
int main() {
    cin >> n >> S;
    for (int i = 0; i < n; i++) cin >> a[i];
    dfs(0, 0);
    cout << ans << endl;
}""",
     "solution": r"""#include <iostream>
using namespace std;

int n, S, a[25], ans = 0;
void dfs(int i, int sum) {
    if (i == n) { if (sum == S) ans++; return; }
    dfs(i + 1, sum);
    dfs(i + 1, sum + a[i]);
}
int main() {
    cin >> n >> S;
    for (int i = 0; i < n; i++) cin >> a[i];
    dfs(0, 0);
    cout << ans << endl;
}"""},
    {"title": "迷宫最短路（BFS）", "desc": "广度优先搜索 · 难度：中等", "difficulty": "medium",
     "problemText": "n×m迷宫，.可走#墙，求左上到右下最少步数，不可达输出-1。",
     "inputDesc": "第一行n,m；接下来n行每行m个字符。", "outputDesc": "一行最少步数，不可达-1。",
     "sampleInput": "5 5\n.....\n.###.\n.....\n.###.\n.....", "sampleOutput": "8",
     "hint": {"approach": "BFS从(1,1)搜索，队列+dist数组记录最短距离，第一次到达即最短。",
              "pitfall": "注意坐标越界；visited在入队时标记；检查字符是.不是0。",
              "extension": "BFS求无权图最短路是高频考点，核心是队列+访问标记+方向数组。"},
     "template": r"""#include <iostream>
#include <queue>
using namespace std;

char maze[105][105];
int dist[105][105];
int dx[] = {0, 0, 1, -1}, dy[] = {1, -1, 0, 0};
int main() {
    int n, m; cin >> n >> m;
    // 读入并 BFS

    return 0;
}""",
     "solution": r"""#include <iostream>
#include <queue>
using namespace std;

char maze[105][105];
int dist[105][105];
int dx[] = {0, 0, 1, -1}, dy[] = {1, -1, 0, 0};
int main() {
    int n, m; cin >> n >> m;
    for (int i = 1; i <= n; i++)
        for (int j = 1; j <= m; j++) { cin >> maze[i][j]; dist[i][j] = -1; }
    queue<int> qx, qy;
    qx.push(1); qy.push(1); dist[1][1] = 0;
    while (!qx.empty()) {
        int x = qx.front(); qx.pop();
        int y = qy.front(); qy.pop();
        for (int k = 0; k < 4; k++) {
            int nx = x + dx[k], ny = y + dy[k];
            if (nx >= 1 && nx <= n && ny >= 1 && ny <= m
                && maze[nx][ny] == '.' && dist[nx][ny] == -1) {
                dist[nx][ny] = dist[x][y] + 1;
                qx.push(nx); qy.push(ny);
            }
        }
    }
    cout << dist[n][m] << endl;
}"""},
    {"title": "数字反转", "desc": "模拟 · 难度：简单", "difficulty": "easy",
     "problemText": "输入一个整数，将其各位数字反转后输出（负号保留在前面）。",
     "inputDesc": "一行一个整数。", "outputDesc": "一行反转后的整数。",
     "sampleInput": "-123", "sampleOutput": "-321",
     "hint": {"approach": "逐位取模得到个位，乘10累加；注意负号先记下、对绝对值操作。",
              "pitfall": "末尾的0反转后应在前面（如1200反转21），不要多输出前导0。",
              "extension": "也可转成字符串反转，但要处理负号和前导0。"},
     "template": r"""#include <iostream>
using namespace std;

int main() {
    int x; cin >> x;
    // 反转输出

    return 0;
}""",
     "solution": r"""#include <iostream>
using namespace std;

int main() {
    int x; cin >> x;
    int neg = (x < 0) ? -1 : 1;
    if (x < 0) x = -x;
    int r = 0;
    while (x > 0) { r = r * 10 + x % 10; x /= 10; }
    cout << neg * r << endl;
}"""},
    {"title": "求和（等差数列）", "desc": "数学/模拟 · 难度：入门", "difficulty": "easy",
     "problemText": "输入n，求1+2+...+n的和。",
     "inputDesc": "一行一个正整数n。", "outputDesc": "一行一个整数。",
     "sampleInput": "100", "sampleOutput": "5050",
     "hint": {"approach": "公式 n*(n+1)/2 直接算，避免循环超时。",
              "pitfall": "n较大时用公式；循环也能过但要注意范围用long long。",
              "extension": "等差数列求和公式是基本功。"},
     "template": r"""#include <iostream>
using namespace std;

int main() {
    long long n; cin >> n;
    cout << n * (n + 1) / 2 << endl;
    return 0;
}""",
     "solution": r"""#include <iostream>
using namespace std;

int main() {
    long long n; cin >> n;
    cout << n * (n + 1) / 2 << endl;
    return 0;
}"""},
    {"title": "津津的储蓄计划", "desc": "模拟 · 难度：简单", "difficulty": "easy",
     "problemText": "津津每月月初得300元，每月有预算开销，剩余存进妈妈处（年底加倍返还）。若某月不够开销则当月退出。求最早退出月份，或年底总钱数。",
     "inputDesc": "12行，每行当月预算。", "outputDesc": "若中途不够输出负月份；否则输出年底总金额。",
     "sampleInput": "290\n230\n...（略）", "sampleOutput": "0 或 -月份",
     "hint": {"approach": "逐月模拟：余额=上月+300-开销，若<0记录月份退出；月底剩≥100且是整百则存100。",
              "pitfall": "存钱只在余额≥100且为100的倍数时存；年底返还=存款*2+余额。",
              "extension": "经典模拟题，细心按规则走即可。"},
     "template": r"""#include <iostream>
using namespace std;

int main() {
    int save = 0, left = 0;
    for (int m = 1; m <= 12; m++) {
        int budget; cin >> budget;
        // 模拟每月

    }
    return 0;
}""",
     "solution": r"""#include <iostream>
using namespace std;

int main() {
    int save = 0, left = 0;
    for (int m = 1; m <= 12; m++) {
        int budget; cin >> budget;
        int money = left + 300 - budget;
        if (money < 0) { cout << -m << endl; return 0; }
        if (money >= 100) { save += money / 100 * 100; money %= 100; }
        left = money;
    }
    cout << left + save * 2 << endl;
    return 0;
}"""},
    {"title": "纪念品分组", "desc": "贪心/排序 · 难度：中等", "difficulty": "medium",
     "problemText": "n个纪念品，每件价格w[i]。每两组装一袋，两袋总价不能超过上限W，求最少袋数。",
     "inputDesc": "第一行W和n；第二行n个w[i]。", "outputDesc": "一行最少袋数。",
     "sampleInput": "5 9\n1 2 3 4 5 6 7 8 9", "sampleOutput": "5",
     "hint": {"approach": "排序后双指针：最贵与最便宜配对，能装一袋就装，否则最贵的单独一袋。",
              "pitfall": "配对失败（超W）时，最贵的必单独占一袋；配对成功则两头各消耗一个。",
              "extension": "典型贪心+双指针，排序是关键。"},
     "template": r"""#include <iostream>
#include <algorithm>
using namespace std;

int main() {
    int W, n, w[30005];
    cin >> W >> n;
    for (int i = 0; i < n; i++) cin >> w[i];
    // 排序 + 双指针分组

    return 0;
}""",
     "solution": r"""#include <iostream>
#include <algorithm>
using namespace std;

int main() {
    int W, n, w[30005];
    cin >> W >> n;
    for (int i = 0; i < n; i++) cin >> w[i];
    sort(w, w + n);
    int L = 0, R = n - 1, ans = 0;
    while (L <= R) {
        if (w[L] + w[R] <= W) { L++; R--; }
        else R--;
        ans++;
    }
    cout << ans << endl;
    return 0;
}"""},
]

# ===== 题库（分学段，按学科）=====
Q_PRIMARY = {
    "语文": [
        {"id": "yp1", "type": "choice", "difficulty": "基础", "knowledgePoint": "古诗理解",
         "question": "“千磨万击还坚劲，任尔东西南北风”出自下列哪首诗？",
         "options": ["《竹石》", "《石灰吟》", "《墨梅》", "《七步诗》"], "answer": 0,
         "hint": {"approach": "这两句出自郑燮（郑板桥）的《竹石》，借竹子表达坚韧。",
                  "pitfall": "易与《石灰吟》（千锤万凿出深山）混淆，注意区分不同咏物诗。",
                  "extension": "小学常见咏物诗：竹石（坚韧）、石灰吟（清白）、墨梅（淡泊）。"}},
        {"id": "yp2", "type": "choice", "difficulty": "基础", "knowledgePoint": "成语运用",
         "question": "下列句子中成语使用正确的是？",
         "options": ["他做事精益求精，从不马虎", "这篇作文语句不通，简直是不刊之论", "他成绩一落千丈，令人刮目相看", "操场上人山人海，美不胜收"], "answer": 0,
         "hint": {"approach": "“精益求精”指好了还求更好，用在这里正确。",
                  "pitfall": "“不刊之论”指不可更改的正确言论，不能形容语句不通。",
                  "extension": "成语题常考望文生义，要记住真实含义再判断。"}},
        {"id": "yp3", "type": "choice", "difficulty": "基础", "knowledgePoint": "古诗默写",
         "question": "杜甫《春夜喜雨》中“随风潜入夜”的下一句是？",
         "options": ["润物细无声", "当春乃发生", "晓看红湿处", "花重锦官城"], "answer": 0,
         "hint": {"approach": "名句：好雨知时节，当春乃发生。随风潜入夜，润物细无声。",
                  "pitfall": "“润”不要写成“闰”。", "extension": "默写先理解诗意再背诵。"}},
        {"id": "yp4", "type": "choice", "difficulty": "中等", "knowledgePoint": "修辞手法",
         "question": "“春天的脚步近了”使用的修辞手法是？",
         "options": ["比喻", "拟人", "夸张", "排比"], "answer": 1,
         "hint": {"approach": "把春天当人来写，说它“迈脚步”，是拟人。",
                  "pitfall": "拟人是赋予事物人的动作；比喻要有喻体和喻词。",
                  "extension": "区分比喻和拟人：拟人不出现喻体。"}},
        {"id": "yp5", "type": "choice", "difficulty": "基础", "knowledgePoint": "标点符号",
         "question": "下列句子标点使用正确的是？",
         "options": ["他说：“今天天气真好”！", "他说：“今天天气真好！”", "他说“今天天气真好！”", "他说：今天天气真好！"], "answer": 1,
         "hint": {"approach": "引语内的感叹号应在引号内。",
                  "pitfall": "句末点号在引文为完整句子时要放在引号内。", "extension": "标点符号是基本功，多读规范例句。"}},
        {"id": "yp6", "type": "choice", "difficulty": "中等", "knowledgePoint": "病句辨析",
         "question": "下列句子没有语病的是？",
         "options": ["通过这次活动，使我明白了团结的重要", "他基本上把不好的习惯完全改掉了", "我们要认真克服并善于发现学习上的缺点", "阅读能开阔我们的视野"], "answer": 3,
         "hint": {"approach": "最后一句主谓宾完整、无矛盾。",
                  "pitfall": "“通过…使”缺主语；“基本”与“完全”矛盾；“克服并发现”语序不当。",
                  "extension": "病句常考成分残缺、搭配不当、矛盾、语序。"}},
    ],
    "数学": [
        {"id": "mp1", "type": "choice", "difficulty": "基础", "knowledgePoint": "分数加减",
         "question": "计算 1/2 + 1/3 = ？", "options": ["2/5", "5/6", "1/6", "3/5"], "answer": 1,
         "hint": {"approach": "通分：1/2=3/6，1/3=2/6，相加得5/6。",
                  "pitfall": "分数相加不能把分子分母分别相加，必须先通分。",
                  "extension": "异分母分数加减：先通分再加减。"}},
        {"id": "mp2", "type": "choice", "difficulty": "基础", "knowledgePoint": "百分数",
         "question": "一件商品原价100元，打八折后的售价是？", "options": ["80元", "20元", "92元", "88元"], "answer": 0,
         "hint": {"approach": "打八折=原价×80%：100×80%=80元。",
                  "pitfall": "“打八折”是乘80%，不是减去80%！", "extension": "现价=原价×折扣。"}},
        {"id": "mp3", "type": "choice", "difficulty": "中等", "knowledgePoint": "圆的周长",
         "question": "圆的半径扩大为原来的3倍，它的周长扩大为几倍？", "options": ["3倍", "6倍", "9倍", "不变"], "answer": 0,
         "hint": {"approach": "C=2πr，r变3倍，C也变3倍。",
                  "pitfall": "面积是r²关系会变9倍，周长只与r一次方成正比。", "extension": "周长正比半径，面积正比半径平方。"}},
        {"id": "mp4", "type": "choice", "difficulty": "基础", "knowledgePoint": "单位换算",
         "question": "3米5厘米 = 多少厘米？", "options": ["35厘米", "305厘米", "350厘米", "3005厘米"], "answer": 1,
         "hint": {"approach": "3米=300厘米，加5厘米=305厘米。", "pitfall": "1米=100厘米，别算成35。", "extension": "长度单位进率是100。"}},
        {"id": "mp5", "type": "choice", "difficulty": "中等", "knowledgePoint": "植树问题",
         "question": "一条100米的小路一边植树，每隔5米一棵（两端都种），共种几棵？", "options": ["19棵", "20棵", "21棵", "22棵"], "answer": 2,
         "hint": {"approach": "段数=100/5=20，两端都种棵数=段数+1=21。",
                  "pitfall": "别漏掉两端中的一棵；棵数=段数+1（两端种）。", "extension": "植树问题记住：两端种=段+1。"}},
        {"id": "mp6", "type": "choice", "difficulty": "基础", "knowledgePoint": "平均数",
         "question": "三个数 80、90、100 的平均数是？", "options": ["80", "90", "100", "270"], "answer": 1,
         "hint": {"approach": "总和270÷3=90。", "pitfall": "平均数=总和÷个数，不是最大数。", "extension": "平均数反映整体水平。"}},
    ],
    "英语": [
        {"id": "ep1", "type": "choice", "difficulty": "基础", "knowledgePoint": "be动词",
         "question": "I ___ a student.", "options": ["am", "is", "are", "be"], "answer": 0,
         "hint": {"approach": "I 后面用 am。", "pitfall": "he/she用is，you/we/they用are。", "extension": "be动词口诀：我用am你用are，is连着他她它。"}},
        {"id": "ep2", "type": "choice", "difficulty": "基础", "knowledgePoint": "名词复数",
         "question": "There are two ___ on the desk.", "options": ["book", "books", "bookes", "book's"], "answer": 1,
         "hint": {"approach": "two 后接复数 books。", "pitfall": "一般直接加s；以s,x,ch,sh结尾加es。", "extension": "名词复数规则要记牢。"}},
        {"id": "ep3", "type": "choice", "difficulty": "中等", "knowledgePoint": "疑问词",
         "question": "___ is your birthday?", "options": ["What", "When", "Where", "Who"], "answer": 1,
         "hint": {"approach": "问时间用 When。", "pitfall": "What问事物，Where问地点，Who问人。", "extension": "疑问词按'问什么'来选。"}},
        {"id": "ep4", "type": "choice", "difficulty": "基础", "knowledgePoint": "颜色词汇",
         "question": "“红色”的英文是？", "options": ["red", "read", "blue", "green"], "answer": 0,
         "hint": {"approach": "red 是红色。", "pitfall": "read 是“读”，不要混淆拼写。", "extension": "常见颜色：red/blue/green/yellow。"}},
        {"id": "ep5", "type": "choice", "difficulty": "中等", "knowledgePoint": "一般现在时",
         "question": "He ___ to school every day.", "options": ["go", "goes", "going", "went"], "answer": 1,
         "hint": {"approach": "第三人称单数用 goes。", "pitfall": "he/she/it 作主语，动词加s/es。", "extension": "一般现在时三单要变形。"}},
        {"id": "ep6", "type": "choice", "difficulty": "基础", "knowledgePoint": "数字",
         "question": "“12”的英文单词是？", "options": ["twelve", "twenty", "eleven", "two"], "answer": 0,
         "hint": {"approach": "twelve 是12。", "pitfall": "twenty是20，注意区分。", "extension": "1-12的拼写较特殊，需单独记。"}},
    ],
}

Q_JUNIOR = {
    "语文": [
        {"id": "yj1", "type": "choice", "difficulty": "基础", "knowledgePoint": "文言文实词",
         "question": "“学而时习之，不亦说乎”中“说”的意思是？", "options": ["说话", "高兴（通“悦”）", "劝说", "学说"], "answer": 1,
         "hint": {"approach": "“说”通“悦”，愉快。", "pitfall": "不要按现代“说话”理解。", "extension": "文言通假字要重点记。"}},
        {"id": "yj2", "type": "choice", "difficulty": "中等", "knowledgePoint": "文学常识",
         "question": "《西游记》的作者是？", "options": ["罗贯中", "吴承恩", "施耐庵", "曹雪芹"], "answer": 1,
         "hint": {"approach": "吴承恩写《西游记》。", "pitfall": "罗贯中《三国》、施耐庵《水浒》、曹雪芹《红楼》。", "extension": "四大名著作者要对应。"}},
        {"id": "yj3", "type": "choice", "difficulty": "中等", "knowledgePoint": "修辞手法",
         "question": "“问君能有几多愁？恰似一江春水向东流”用了什么修辞？", "options": ["比喻", "设问+比喻", "夸张", "对偶"], "answer": 1,
         "hint": {"approach": "自问自答是设问，把愁比春水是比喻。", "pitfall": "只看到比喻会漏掉设问。", "extension": "修辞识别要全面。"}},
        {"id": "yj4", "type": "choice", "difficulty": "基础", "knowledgePoint": "字词音形",
         "question": "下列加点字注音正确的是？", "options": ["瞠(chēng)目", "踉(niàng)跄", "酗(xiōng)酒", "字帖(tiē)"], "answer": 0,
         "hint": {"approach": "瞠目chēng mù正确。", "pitfall": "踉跄liàng；酗酒xù；字帖tiè。", "extension": "易错字音要积累。"}},
        {"id": "yj5", "type": "choice", "difficulty": "中等", "knowledgePoint": "病句辨析",
         "question": "下列没有语病的是？", "options": ["能否刻苦是成功的关键", "他那认真刻苦的精神值得学习", "大约有50人左右参加", "通过努力，使成绩提高"], "answer": 1,
         "hint": {"approach": "第二句成分完整、无矛盾。", "pitfall": "“能否”两面对一面；“大约”“左右”重复；“通过…使”缺主语。", "extension": "病句类型：两面对一面、重复、缺主语。"}},
    ],
    "数学": [
        {"id": "mj1", "type": "choice", "difficulty": "中等", "knowledgePoint": "一次函数",
         "question": "一次函数 y=2x+1 的图象与y轴交点的坐标是？", "options": ["(0,1)", "(1,0)", "(0,2)", "(2,0)"], "answer": 0,
         "hint": {"approach": "令x=0，y=1，交点(0,1)。", "pitfall": "与y轴交点x=0，不是y=0。", "extension": "y=kx+b与y轴交于(0,b)。"}},
        {"id": "mj2", "type": "choice", "difficulty": "中等", "knowledgePoint": "一元二次方程",
         "question": "方程 x²-5x+6=0 的解是？", "options": ["x=2或3", "x=1或6", "x=-2或-3", "x=5"], "answer": 0,
         "hint": {"approach": "因式分解 (x-2)(x-3)=0，x=2或3。", "pitfall": "别把常数项直接当解。", "extension": "十字相乘是常用解法。"}},
        {"id": "mj3", "type": "choice", "difficulty": "基础", "knowledgePoint": "概率",
         "question": "抛一枚均匀硬币，正面朝上的概率是？", "options": ["1/4", "1/2", "1", "0"], "answer": 1,
         "hint": {"approach": "正反两种等可能，概率1/2。", "pitfall": "不要想成1/4。", "extension": "概率=有利情况/总情况。"}},
        {"id": "mj4", "type": "choice", "difficulty": "中等", "knowledgePoint": "相似三角形",
         "question": "两相似三角形相似比为2:3，则面积比为？", "options": ["2:3", "4:9", "3:2", "√2:√3"], "answer": 1,
         "hint": {"approach": "面积比=相似比的平方=4:9。", "pitfall": "面积比是平方关系，不是线比。", "extension": "相似图形面积比=相似比²。"}},
        {"id": "mj5", "type": "choice", "difficulty": "基础", "knowledgePoint": "统计",
         "question": "数据 2,4,4,5,6 的中位数是？", "options": ["2", "4", "5", "6"], "answer": 1,
         "hint": {"approach": "排序后中间的数=4。", "pitfall": "中间是4不是平均数。", "extension": "奇数个数据中位数是正中间那个。"}},
    ],
    "英语": [
        {"id": "ej1", "type": "choice", "difficulty": "中等", "knowledgePoint": "时态",
         "question": "Look! The bus ___.", "options": ["comes", "is coming", "came", "will come"], "answer": 1,
         "hint": {"approach": "Look! 提示用现在进行时 is coming。", "pitfall": "看见now/look用进行时。", "extension": "现在进行时：be+doing。"}},
        {"id": "ej2", "type": "choice", "difficulty": "中等", "knowledgePoint": "比较级",
         "question": "This book is ___ than that one.", "options": ["interesting", "more interesting", "most interesting", "interestinger"], "answer": 1,
         "hint": {"approach": "多音节词比较级用 more+原级。", "pitfall": "interesting不是直接加er。", "extension": "长词比较级用more/most。"}},
        {"id": "ej3", "type": "choice", "difficulty": "基础", "knowledgePoint": "介词",
         "question": "He is good ___ math.", "options": ["in", "on", "at", "for"], "answer": 2,
         "hint": {"approach": "be good at 擅长。", "pitfall": "固定搭配 at。", "extension": "介词搭配靠积累。"}},
        {"id": "ej4", "type": "choice", "difficulty": "中等", "knowledgePoint": "被动语态",
         "question": "The window ___ yesterday.", "options": ["broke", "was broken", "breaks", "is breaking"], "answer": 1,
         "hint": {"approach": "yesterday用过去时被动 was broken。", "pitfall": "主语window不能主动break。", "extension": "被动：be+过去分词。"}},
        {"id": "ej5", "type": "choice", "difficulty": "基础", "knowledgePoint": "词汇",
         "question": "“医院”的英文是？", "options": ["hospital", "hotel", "house", "home"], "answer": 0,
         "hint": {"approach": "hospital 医院。", "pitfall": "hotel是旅馆。", "extension": "常见场所词汇要记。"}},
    ],
    "物理": [
        {"id": "pj1", "type": "choice", "difficulty": "基础", "knowledgePoint": "声现象",
         "question": "声音不能在下列哪种环境中传播？", "options": ["固体", "液体", "气体", "真空"], "answer": 3,
         "hint": {"approach": "声音靠介质振动传播，真空无介质。", "pitfall": "太空是真空，听不到声音。", "extension": "声音传播需要介质。"}},
        {"id": "pj2", "type": "choice", "difficulty": "基础", "knowledgePoint": "光的反射",
         "question": "光反射时，反射角与入射角的关系是？", "options": ["反射角大于入射角", "相等", "反射角小于入射角", "无关"], "answer": 1,
         "hint": {"approach": "反射角=入射角。", "pitfall": "别记反。", "extension": "反射定律是光学基础。"}},
        {"id": "pj3", "type": "choice", "difficulty": "中等", "knowledgePoint": "速度",
         "question": "某物体3秒运动了60米，它的速度是？", "options": ["20 m/s", "180 m/s", "0.05 m/s", "30 m/s"], "answer": 0,
         "hint": {"approach": "v=s/t=60/3=20 m/s。", "pitfall": "用除法不是乘法。", "extension": "速度=路程÷时间。"}},
        {"id": "pj4", "type": "choice", "difficulty": "基础", "knowledgePoint": "物态变化",
         "question": "冰化成水属于哪种物态变化？", "options": ["凝固", "熔化", "汽化", "升华"], "answer": 1,
         "hint": {"approach": "固态变液态是熔化。", "pitfall": "凝固是液态变固态。", "extension": "熔化吸热、凝固放热。"}},
        {"id": "pj5", "type": "choice", "difficulty": "中等", "knowledgePoint": "密度",
         "question": "同体积的水和铁，下列说法正确的是？", "options": ["水重", "铁重", "一样重", "无法判断"], "answer": 1,
         "hint": {"approach": "铁的密度远大于水，同体积铁更重。", "pitfall": "密度大则同体积质量大。", "extension": "m=ρV。"}},
    ],
}

Q_SENIOR = {
    "语文": [
        {"id": "ys1", "type": "choice", "difficulty": "中等", "knowledgePoint": "文言虚词",
         "question": "“之”字在“禽兽之变诈几何哉”中用法是？", "options": ["代词", "结构助词“的”", "动词“去”", "宾语前置标志"], "answer": 1,
         "hint": {"approach": "“禽兽的欺骗手段”，之=的。", "pitfall": "之有多种用法，要结合语境。", "extension": "文言虚词需逐句判断。"}},
        {"id": "ys2", "type": "choice", "difficulty": "中等", "knowledgePoint": "现代文阅读",
         "question": "下列对“比喻”作用的分析，正确的是？", "options": ["使抽象变具体、深奥变浅显", "增加字数", "为了押韵", "表示转折"], "answer": 0,
         "hint": {"approach": "比喻化抽象为形象，帮助理解。", "pitfall": "比喻目的不是凑字数。", "extension": "赏析修辞要从表达效果入手。"}},
        {"id": "ys3", "type": "choice", "difficulty": "基础", "knowledgePoint": "字音字形",
         "question": "下列没有错别字的是？", "options": ["再接再厉", "迫不急待", "一愁莫展", "穿流不息"], "answer": 0,
         "hint": {"approach": "再接再厉正确。", "pitfall": "及（急）待、筹（愁）莫展、川（穿）流不息均错。", "extension": "成语字形易错字要记。"}},
    ],
    "数学": [
        {"id": "ms1", "type": "choice", "difficulty": "中等", "knowledgePoint": "函数与导数",
         "question": "f(x)=x² 在 x=1 处的导数是？", "options": ["1", "2", "0", "3"], "answer": 1,
         "hint": {"approach": "f′(x)=2x，代入x=1得2。", "pitfall": "别把原函数值代入。", "extension": "导数即切线斜率。"}},
        {"id": "ms2", "type": "choice", "difficulty": "中等", "knowledgePoint": "三角函数",
         "question": "sin 30° 的值是？", "options": ["1/2", "√3/2", "1", "0"], "answer": 0,
         "hint": {"approach": "sin30°=1/2。", "pitfall": "cos30°才是√3/2。", "extension": "特殊角三角函数值要背。"}},
        {"id": "ms3", "type": "choice", "difficulty": "基础", "knowledgePoint": "数列",
         "question": "等差数列 2,5,8,11… 的第10项是？", "options": ["29", "30", "28", "31"], "answer": 0,
         "hint": {"approach": "公差3，a10=2+9×3=29。", "pitfall": "项数减一乘公差。", "extension": "an=a1+(n-1)d。"}},
    ],
    "英语": [
        {"id": "es1", "type": "choice", "difficulty": "中等", "knowledgePoint": "虚拟语气",
         "question": "If I ___ you, I would go.", "options": ["am", "was", "were", "be"], "answer": 2,
         "hint": {"approach": "与现在事实相反的虚拟，be用were。", "pitfall": "虚拟语气中不论人称都用were。", "extension": "if虚拟三类型要区分。"}},
        {"id": "es2", "type": "choice", "difficulty": "中等", "knowledgePoint": "非谓语",
         "question": "___ from the hill, the town looks beautiful.", "options": ["Seen", "Seeing", "To see", "See"], "answer": 0,
         "hint": {"approach": "town与see是被动关系，用过去分词Seen。", "pitfall": "主语是town不能主动看。", "extension": "非谓语看主被动。"}},
        {"id": "es3", "type": "choice", "difficulty": "基础", "knowledgePoint": "词汇",
         "question": "“环境”的英文是？", "options": ["environment", "experiment", "experience", "element"], "answer": 0,
         "hint": {"approach": "environment 环境。", "pitfall": "experiment实验、experience经验。", "extension": "环保话题词汇常用。"}},
    ],
    "物理": [
        {"id": "ps1", "type": "choice", "difficulty": "中等", "knowledgePoint": "牛顿第二定律",
         "question": "质量2kg的物体受4N合力，加速度是？", "options": ["2 m/s²", "8 m/s²", "0.5 m/s²", "6 m/s²"], "answer": 0,
         "hint": {"approach": "a=F/m=4/2=2 m/s²。", "pitfall": "用除法不是乘法。", "extension": "牛顿第二定律 F=ma。"}},
        {"id": "ps2", "type": "choice", "difficulty": "中等", "knowledgePoint": "机械能守恒",
         "question": "不计空气阻力，物体自由下落过程中哪个量守恒？", "options": ["动能", "重力势能", "机械能", "速度"], "answer": 2,
         "hint": {"approach": "只有重力做功，机械能守恒。", "pitfall": "动能和势能相互转化，总量不变。", "extension": "机械能=动能+势能。"}},
        {"id": "ps3", "type": "choice", "difficulty": "基础", "knowledgePoint": "电路",
         "question": "两电阻串联，总电阻与分电阻关系是？", "options": ["相加", "相乘", "倒数和", "相除"], "answer": 0,
         "hint": {"approach": "串联 R=R1+R2。", "pitfall": "并联才是倒数和。", "extension": "串并联规律要分清。"}},
    ],
    "化学": [
        {"id": "cs1", "type": "choice", "difficulty": "基础", "knowledgePoint": "物质分类",
         "question": "下列属于纯净物的是？", "options": ["空气", "蒸馏水", "海水", "牛奶"], "answer": 1,
         "hint": {"approach": "蒸馏水是单一物质H₂O。", "pitfall": "空气、海水、牛奶都是混合物。", "extension": "纯净物由一种物质组成。"}},
        {"id": "cs2", "type": "choice", "difficulty": "中等", "knowledgePoint": "化学方程式",
         "question": "2H₂+O₂=2H₂O 中，H₂与O₂的分子个数比是？", "options": ["1:1", "2:1", "1:2", "2:2"], "answer": 1,
         "hint": {"approach": "系数为2:1。", "pitfall": "看系数不是看原子数。", "extension": "方程式系数即个数比。"}},
        {"id": "cs3", "type": "choice", "difficulty": "基础", "knowledgePoint": "酸碱指示",
         "question": "石蕊试液遇酸变什么色？", "options": ["红", "蓝", "不变", "紫"], "answer": 0,
         "hint": {"approach": "石蕊遇酸红、遇碱蓝。", "pitfall": "酚酞才是遇碱红。", "extension": "常见指示剂变色要记。"}},
    ],
    "生物": [
        {"id": "bs1", "type": "choice", "difficulty": "基础", "knowledgePoint": "细胞结构",
         "question": "植物细胞特有的结构是？", "options": ["细胞膜", "细胞壁", "线粒体", "细胞核"], "answer": 1,
         "hint": {"approach": "细胞壁、叶绿体、液泡是植物细胞特有。", "pitfall": "细胞膜、线粒体、细胞核动植物都有。", "extension": "动植物细胞结构对比要清。"}},
        {"id": "bs2", "type": "choice", "difficulty": "中等", "knowledgePoint": "光合作用",
         "question": "光合作用主要在细胞的哪个结构进行？", "options": ["线粒体", "叶绿体", "细胞核", "液泡"], "answer": 1,
         "hint": {"approach": "叶绿体是光合作用场所。", "pitfall": "线粒体是呼吸作用的。", "extension": "叶绿体+光能→有机物+氧气。"}},
        {"id": "bs3", "type": "choice", "difficulty": "基础", "knowledgePoint": "遗传",
         "question": "控制生物性状的基本单位是？", "options": ["蛋白质", "基因", "细胞", "染色体"], "answer": 1,
         "hint": {"approach": "基因是有遗传效应的DNA片段。", "pitfall": "染色体由DNA和蛋白质组成。", "extension": "基因控制性状。"}},
    ],
}

NEWS_TIPS = [
    "读完新闻试着用自己的话讲一遍，记忆更牢。",
    "遇到不懂的词，查一查词典，会有新发现。",
    "关注新闻里的数字，它们常常说明问题的关键。",
    "把新闻和课本知识连起来想，理解会更透。",
    "每天读一点，慢慢就成了关心世界的小大人。",
    "可以和家长聊聊今天的新闻，听听不同看法。",
    "新闻里的科学原理，正是你课本要学的内容。",
    "看到感人的故事，想想自己能做什么。",
    "对比不同报道，学会独立思考。",
    "记录下喜欢的句子，写作文时能用上。",
    "新闻里的地名，去地图上找一找。",
    "坚持每天阅读，积少成多收获大。",
]

KNOWLEDGE_TIPS = [
    "把新常识和课本知识连起来想，理解更透。",
    "遇到有趣的现象，动手做小实验验证一下。",
    "画一张思维导图，把零散知识串起来。",
    "给家人讲一遍，能讲明白才是真懂了。",
    "生活中的为什么，都可以变成学习的小课题。",
    "记笔记时用自己的话，比抄写更有效。",
    "同一个知识点，换个角度问自己一遍。",
    "把常识编成小口诀，记得又快又牢。",
    "观察身边的事物，科学知识就在其中。",
    "每天学一点，知识像滚雪球越滚越大。",
    "不懂就问，问题是学习的起点。",
    "把相似的知识归类，不容易混淆。",
]

HOME_WELCOME = [
    "新版远程内容已上线，今天的内容每天都不一样哦！",
    "欢迎回来！读新闻、学常识、练题目，每天进步一点点。",
    "今天也要元气满满地学习呀～",
    "试试'每日训练'，系统会帮你挑出适合的题目。",
    "做完题记得看解析，错过的题下次就不怕啦。",
    "生活实践里学做一道菜，也是了不起的本领！",
]


def main():
    dn = day_number()
    today = datetime.date.today().isoformat()
    manifest = {
        "version": dn,
        "generatedAt": today,
        "stages": {
            "小学": {"file": "q-primary.json", "version": dn},
            "初中": {"file": "q-junior.json", "version": dn},
            "高中": {"file": "q-senior.json", "version": dn},
        },
        "retire": {"小学": [], "初中": [], "高中": []},
        "news": fetch_live_news() or pick(NEWS_POOL, 8, dn),
        "knowledge": pick(KNOWLEDGE_POOL, 10, dn * 7 + 3),
        "newsTips": NEWS_TIPS,
        "knowledgeTips": KNOWLEDGE_TIPS,
        "homeWelcome": HOME_WELCOME,
        "cooking": {
            "recipes": pick(COOKING_RECIPES, 8, dn * 3 + 1),
            "tips": pick(COOKING_TIPS, 3, dn * 5 + 2),
        },
        "cspLessons": pick(CSP_LESSONS, 4, dn * 2 + 1),
        "cspProblems": pick(CSP_PROBLEMS, 6, dn * 4 + 2),
    }

    here = os.path.dirname(os.path.abspath(__file__))
    # 写 manifest（同时保留 content.json 作为主入口，兼容 set_content_url.py）
    with open(os.path.join(here, "content.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    # 兼容旧文件名
    with open(os.path.join(here, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    # 分学段题库
    for fn, data in [("q-primary.json", Q_PRIMARY), ("q-junior.json", Q_JUNIOR), ("q-senior.json", Q_SENIOR)]:
        with open(os.path.join(here, fn), "w", encoding="utf-8") as f:
            json.dump({"questions": data}, f, ensure_ascii=False, indent=2)

    print("generated at", today, "version", dn)


if __name__ == "__main__":
    main()
