#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
爱影坊 TVBox 蜘蛛脚本 v2
站点: https://www.iyf.lv/
系统: 苹果CMS (maccms) + mxtheme 主题
'''

import re
import json
import urllib.parse
import urllib.request

SITE_KEY = "iyf_lv"
SITE_NAME = "爱影坊"
BASE_URL = "https://www.iyf.lv"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

HEADERS = {
    "User-Agent": UA,
    "Referer": BASE_URL + "/",
}

CATEGORIES = [
    ("电影", 1),
    ("电视剧", 2),
    ("综艺", 3),
    ("动漫", 4),
    ("美剧", 16),
    ("韩剧", 15),
    ("日剧", 13),
    ("泰剧", 14),
]


def _fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="replace")


def _fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _img(path):
    if not path:
        return ""
    if path.startswith("http"):
        return path
    return BASE_URL + path


def _parse_module_items(html):
    '''解析 module-poster-item 结构的列表项'''
    items = []
    seen = set()
    # 匹配每个 module-poster-item 块
    # 格式: <a href="/iyftv/{id}/" title="名称" class="module-poster-item ...">
    #   <div class="module-item-cover">
    #     <div class="module-item-note">更新状态</div>
    #     <div class="module-item-pic">
    #       <img src="..." 或 data-original="..." alt="名称">
    #     </div>
    #   </div>
    #   <div class="module-poster-item-info">
    #     <div class="module-poster-item-title">名称</div>
    #   </div>
    # </a>
    block_pattern = re.compile(
        r'<a\s+href="(/iyftv/(\d+)/)"\s+title="([^"]*)"[^>]*class="module-poster-item[^"]*"[^>]*>'
        r'(.*?)</a>',
        re.DOTALL
    )

    for m in block_pattern.finditer(html):
        link, vid, title, content = m.group(1), m.group(2), m.group(3).strip(), m.group(4)

        if vid in seen:
            continue
        seen.add(vid)

        # 提取图片: 优先 data-original，其次 src
        pic = ""
        pic_m = re.search(r'data-original="([^"]+)"', content)
        if pic_m:
            pic = pic_m.group(1)
        else:
            pic_m = re.search(r'<img[^>]+src="([^"]+)"', content)
            if pic_m:
                pic = pic_m.group(1)

        # 提取更新状态
        remarks = ""
        note_m = re.search(r'class="module-item-note">([^<]*)</div>', content)
        if note_m:
            remarks = note_m.group(1).strip()

        # 提取名称: 优先 title 属性，其次 module-poster-item-title
        name = title
        if not name:
            name_m = re.search(r'class="module-poster-item-title">([^<]*)</div>', content)
            if name_m:
                name = name_m.group(1).strip()

        if not name:
            continue

        items.append({
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": _img(pic),
            "vod_remarks": remarks,
        })

    return items


# ==================== TVBox 协议方法 ====================

def homeContent(filterData):
    '''首页分类'''
    classes = []
    for name, tid in CATEGORIES:
        classes.append({
            "type_id": str(tid),
            "type_name": name,
        })
    return {"class": classes}


def homeVideoContent():
    '''首页推荐 - 从多个 module 区域提取'''
    try:
        html = _fetch(BASE_URL + "/")
    except Exception:
        return {"list": []}

    all_items = []
    seen = set()

    # 按 module 块分割，提取每个区域的内容
    # 跳过"即将开播"区域（那些是即将上映的，没有实际内容）
    module_pattern = re.compile(
        r'<div\s+class="module[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
        re.DOTALL
    )

    for mm in module_pattern.finditer(html):
        block = mm.group(1)
        # 跳过即将开播
        if "即将开播" in block:
            continue
        items = _parse_module_items(block)
        for item in items:
            if item["vod_id"] not in seen:
                seen.add(item["vod_id"])
                all_items.append(item)

    # 如果 module 提取失败，用简单正则兜底
    if not all_items:
        for m in re.finditer(r'href="(/iyftv/(\d+)/)"\s+title="([^"]+)"', html):
            vid, name = m.group(2), m.group(3).strip()
            if vid not in seen and name:
                seen.add(vid)
                all_items.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": "",
                    "vod_remarks": "",
                })

    return {"list": all_items[:30]}


def category(tid, pg, filter, extend):
    '''分类列表'''
    try:
        url = BASE_URL + "/t/" + str(tid) + "/" + str(pg) + "/"
        html = _fetch(url)
    except Exception:
        return {"page": pg, "pagecount": 1, "limit": 0, "total": 0, "list": []}

    items = _parse_module_items(html)

    return {
        "page": pg,
        "pagecount": max(1, pg),
        "limit": len(items),
        "total": len(items),
        "list": items[:72],
    }


def detail(id):
    '''详情页'''
    try:
        html = _fetch(BASE_URL + "/iyftv/" + str(id) + "/")
    except Exception:
        return {"list": []}

    # 标题
    tm = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    vod_name = tm.group(1).strip() if tm else ""

    # 封面: 优先 og:image，其次 vodPic 区域
    vod_pic = ""
    og_m = re.search(r'property="og:image"\s+content="([^"]+)"', html)
    if og_m:
        vod_pic = og_m.group(1)
    else:
        pm = re.search(r'<div[^>]*class="[^"]*vodPic[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.DOTALL)
        if pm:
            vod_pic = pm.group(1)
    vod_pic = _img(vod_pic)

    # 年份
    ym = re.search(r'上映[：:]\s*(\d{4}-\d{2}-\d{2})', html)
    vod_year = ym.group(1)[:4] if ym else ""

    # 地区
    am = re.search(r'<a[^>]+href="/k/\d+-([^"/]+)"[^>]*>\s*([^<]+)\s*</a>', html)
    vod_area = am.group(2).strip() if am else ""

    # 类型
    tms = re.findall(r'<a[^>]+href="/k/\d+---([^"-]+)"[^>]*>\s*([^<]+)\s*</a>', html)
    type_name = "/".join(t[1].strip() for t in tms if t[1].strip())

    # 导演
    dm = re.search(r'导演[：:]\s*(.*?)(?:</div>|<div)', html, re.DOTALL)
    vod_director = ""
    if dm:
        ds = re.findall(r'>([^<]+)<', dm.group(1))
        vod_director = ",".join(d.strip() for d in ds if d.strip() and len(d.strip()) > 1)

    # 主演
    acm = re.search(r'主演[：:]\s*(.*?)(?:</div>|<div)', html, re.DOTALL)
    vod_actor = ""
    if acm:
        acs = re.findall(r'>([^<]+)<', acm.group(1))
        vod_actor = ",".join(a.strip() for a in acs if a.strip() and len(a.strip()) > 1)

    # 简介
    cm = re.search(r'<div[^>]*class="[^"]*vodContent[^"]*"[^>]*>\s*<p[^>]*>(.*?)</p>', html, re.DOTALL)
    vod_content = cm.group(1).strip() if cm else ""

    # 更新时间
    um = re.search(r'更新[：:]\s*(\d{4}-\d{2}-\d{2})', html)
    vod_time = um.group(1) if um else ""

    # 选集解析
    play_from_list = []
    play_url_list = []

    sections = re.split(r'<div[^>]*class="[^"]*playlist[^"]*"[^>]*>', html)

    for sec in sections[1:]:
        sn = re.search(r'<h3[^>]*>([^<]+)</h3>', sec)
        if not sn:
            continue
        source_name = sn.group(1).strip()

        eps = re.findall(r'<a[^>]+href="(/iyfplay/(\d+)-(\d+)-(\d+)/)"[^>]*>([^<]*)</a>', sec)
        if eps:
            ep_list = []
            for link, vid, sid, nid, ep_name in eps:
                ep_name = ep_name.strip()
                if not ep_name:
                    ep_name = "第" + nid + "集"
                ep_list.append(ep_name + "$" + BASE_URL + link)
            play_from_list.append(source_name)
            play_url_list.append("#".join(ep_list))

    vod_play_from = "$$$".join(play_from_list)
    vod_play_url = "$$$".join(play_url_list)

    return {
        "list": [{
            "vod_id": id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "type_name": type_name,
            "vod_year": vod_year,
            "vod_area": vod_area,
            "vod_remarks": "",
            "vod_actor": vod_actor,
            "vod_director": vod_director,
            "vod_content": vod_content,
            "vod_time": vod_time,
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url,
        }]
    }


def search(wd, quick):
    '''搜索'''
    try:
        data = _fetch_json(BASE_URL + "/index.php/ajax/suggest?mid=1&wd=" + urllib.parse.quote(wd) + "&limit=20")
    except Exception:
        return {"list": []}

    items = []
    for item in data.get("list", []):
        items.append({
            "vod_id": str(item["id"]),
            "vod_name": item["name"],
            "vod_pic": _img(item.get("pic", "")),
            "vod_remarks": "",
        })
    return {"list": items}


def play(flag, id, flags):
    '''播放 - 提取 m3u8 地址'''
    try:
        html = _fetch(id)
    except Exception:
        return {"parse": 0, "playUrl": "", "url": ""}

    m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', html, re.DOTALL)
    if not m:
        return {"parse": 0, "playUrl": "", "url": ""}

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return {"parse": 0, "playUrl": "", "url": ""}

    url = data.get("url", "")
    encrypt = data.get("encrypt", 0)

    if encrypt == 1:
        url = urllib.parse.unquote(url)
    elif encrypt == 2:
        import base64
        url = urllib.parse.unquote(base64.b64decode(url).decode("utf-8"))

    if not url:
        return {"parse": 0, "playUrl": "", "url": ""}

    return {
        "parse": 0,
        "playUrl": "",
        "url": url,
        "header": {
            "User-Agent": UA,
            "Referer": BASE_URL + "/",
        },
    }


def localProxy(param):
    return ""
