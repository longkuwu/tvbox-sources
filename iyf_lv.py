#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import json
import urllib.parse
import urllib.request

BASE = "https://www.iyf.lv"
UA = "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HD = {"User-Agent": UA, "Referer": BASE + "/"}

def get(url):
    req = urllib.request.Request(url, headers=HD)
    return urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")

def getJson(url):
    return json.loads(get(url))

def pic(p):
    return p if (p and p.startswith("http")) else (BASE + p if p else "")

# ========== 首页分类 ==========
def homeContent(filterData):
    cls = [
        {"type_id": "1", "type_name": "电影"},
        {"type_id": "2", "type_name": "电视剧"},
        {"type_id": "3", "type_name": "综艺"},
        {"type_id": "4", "type_name": "动漫"},
        {"type_id": "16", "type_name": "美剧"},
        {"type_id": "15", "type_name": "韩剧"},
        {"type_id": "13", "type_name": "日剧"},
        {"type_id": "14", "type_name": "泰剧"},
    ]
    return {"class": cls}

# ========== 首页推荐 ==========
def homeVideoContent():
    try:
        html = get(BASE + "/")
    except:
        return {"list": []}
    items = []
    ids = []
    # 匹配: <a href="/iyftv/123/" title="名称" class="module-poster-item
    for m in re.finditer(r'href="(/iyftv/(\d+)/)"\s+title="([^"]+)"', html):
        vid, name = m.group(2), m.group(3).strip()
        if vid in ids or not name:
            continue
        ids.append(vid)
        # 在这个链接后面找图片
        after = html[m.start():m.start()+500]
        p = ""
        # 优先 data-original (懒加载)
        pm = re.search(r'data-original="([^"]+)"', after)
        if pm:
            p = pm.group(1)
        if not p:
            pm = re.search(r'<img[^>]+src="([^"]+)"', after)
            if pm:
                p = pm.group(1)
        # 找更新状态
        r = ""
        rm = re.search(r'module-item-note">([^<]+)<', after)
        if rm:
            r = rm.group(1).strip()
        items.append({"vod_id": vid, "vod_name": name, "vod_pic": pic(p), "vod_remarks": r})
    return {"list": items[:30]}

# ========== 分类列表 ==========
def category(tid, pg, filter, extend):
    try:
        html = get(BASE + "/t/" + str(tid) + "/" + str(pg) + "/")
    except:
        return {"page": pg, "pagecount": 1, "limit": 0, "total": 0, "list": []}
    items = []
    ids = []
    for m in re.finditer(r'href="(/iyftv/(\d+)/)"\s+title="([^"]+)"', html):
        vid, name = m.group(2), m.group(3).strip()
        if vid in ids or not name:
            continue
        ids.append(vid)
        after = html[m.start():m.start()+500]
        p = ""
        pm = re.search(r'data-original="([^"]+)"', after)
        if pm:
            p = pm.group(1)
        if not p:
            pm = re.search(r'<img[^>]+src="([^"]+)"', after)
            if pm:
                p = pm.group(1)
        r = ""
        rm = re.search(r'module-item-note">([^<]+)<', after)
        if rm:
            r = rm.group(1).strip()
        items.append({"vod_id": vid, "vod_name": name, "vod_pic": pic(p), "vod_remarks": r})
    return {"page": pg, "pagecount": max(1, pg), "limit": len(items), "total": len(items), "list": items[:72]}

# ========== 详情页 ==========
def detail(id):
    try:
        html = get(BASE + "/iyftv/" + str(id) + "/")
    except:
        return {"list": []}

    # 标题
    t = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    name = t.group(1).strip() if t else ""

    # 封面: og:image
    t = re.search(r'og:image"\s+content="([^"]+)"', html)
    cover = pic(t.group(1)) if t else ""

    # 年份
    t = re.search(r'(\d{4})[<-]', html[:5000])
    year = t.group(1) if t else ""

    # 简介
    t = re.search(r'vodContent[^>]*>.*?<p[^>]*>(.*?)</p>', html, re.S)
    desc = t.group(1).strip() if t else ""

    # 播放源名称: data-dropdown-value="自营1线"
    sources = re.findall(r'data-dropdown-value="([^"]+)"', html)

    # 播放地址解析
    from_list = []
    url_list = []

    # 按集数面板分割
    panels = re.split(r'class="module-list\s', html)
    for i, panel in enumerate(panels[1:], 0):
        src = sources[i] if i < len(sources) else ("线路" + str(i+1))
        eps = re.findall(r'href="(/iyfplay/[^"]+)"[^>]*>\s*<span>([^<]*)</span>', panel)
        if eps:
            el = []
            for link, ename in eps:
                ename = ename.strip()
                if not ename:
                    ename = "播放"
                el.append(ename + "$" + BASE + link)
            from_list.append(src)
            url_list.append("#".join(el))

    return {"list": [{"vod_id": id, "vod_name": name, "vod_pic": cover, "vod_year": year, "vod_area": "", "type_name": "", "vod_remarks": "", "vod_actor": "", "vod_director": "", "vod_content": desc, "vod_time": "", "vod_play_from": "$$$".join(from_list), "vod_play_url": "$$$".join(url_list)}]}

# ========== 搜索 ==========
def search(wd, quick):
    try:
        data = getJson(BASE + "/index.php/ajax/suggest?mid=1&wd=" + urllib.parse.quote(wd) + "&limit=20")
    except:
        return {"list": []}
    items = []
    for v in data.get("list", []):
        items.append({"vod_id": str(v["id"]), "vod_name": v["name"], "vod_pic": pic(v.get("pic", "")), "vod_remarks": ""})
    return {"list": items}

# ========== 播放 ==========
def play(flag, id, flags):
    try:
        html = get(id)
    except:
        return {"parse": 0, "playUrl": "", "url": ""}
    t = re.search(r'player_aaaa\s*=\s*(\{.*?\});', html, re.S)
    if not t:
        return {"parse": 0, "playUrl": "", "url": ""}
    try:
        d = json.loads(t.group(1))
    except:
        return {"parse": 0, "playUrl": "", "url": ""}
    u = d.get("url", "")
    e = d.get("encrypt", 0)
    if e == 1:
        u = urllib.parse.unquote(u)
    elif e == 2:
        import base64
        u = urllib.parse.unquote(base64.b64decode(u).decode("utf-8"))
    if not u:
        return {"parse": 0, "playUrl": "", "url": ""}
    return {"parse": 0, "playUrl": "", "url": u, "header": {"User-Agent": UA, "Referer": BASE + "/"}}

def localProxy(param):
    return ""
