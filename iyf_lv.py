#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
爱影坊 TVBox 蜘蛛脚本
站点: https://www.iyf.lv/
系统: 苹果CMS (maccms)
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

# 分类配置: (分类名, maccms type_id)
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


# ==================== TVBox 协议方法 ====================

def homeContent(filterData):
    '''首页分类'''
    classes = []
    for name, tid in CATEGORIES:
        classes.append({
            "type_id": str(tid),
            "type_name": name,
        })
    result = {
        "class": classes,
    }
    return result


def homeVideoContent():
    '''首页推荐'''
    try:
        html = _fetch(BASE_URL + "/")
    except Exception:
        return {"list": []}

    items = []
    seen = set()
    # 匹配: /iyftv/{id}/
    pattern = re.compile(r'href="(/iyftv/(\d+)/)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?(?:<[^>]*>)*([^<]*(?:第\d+集|完结|正片|抢先版|更新至|集)[^<]*)', re.DOTALL)

    for m in pattern.finditer(html):
        link, vid, pic, remarks = m.group(1), m.group(2), m.group(3), m.group(4).strip()
        if vid in seen:
            continue
        seen.add(vid)
        items.append({
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": _img(pic),
            "vod_remarks": remarks,
        })

    # 二次提取名称: 在链接附近找标题
    name_pattern = re.compile(r'href="/iyftv/(\d+)/"[^>]*>(?:<[^>]*>)*([^<]{2,50})</a>', re.DOTALL)
    name_map = {}
    for m in name_pattern.finditer(html):
        vid, name = m.group(1), m.group(2).strip()
        if vid not in name_map and len(name) >= 2:
            name_map[vid] = name

    for item in items:
        vid = item["vod_id"]
        if vid in name_map:
            item["vod_name"] = name_map[vid]

    return {"list": items[:30]}


def category(tid, pg, filter, extend):
    '''分类列表'''
    try:
        url = BASE_URL + "/t/" + str(tid) + "/" + str(pg) + "/"
        html = _fetch(url)
    except Exception:
        return {"page": pg, "pagecount": 1, "limit": 0, "total": 0, "list": []}

    items = []
    seen = set()

    # 提取图片
    img_map = {}
    for m in re.finditer(r'<img[^>]+src="([^"]+)"[^>]*>', html):
        pos = m.start()
        # 向后查找最近的 /iyftv/ 链接
        after = html[pos:pos+300]
        link_m = re.search(r'href="(/iyftv/(\d+)/)"', after)
        if link_m:
            img_map[link_m.group(2)] = m.group(1)

    # 提取名称和更新状态
    for m in re.finditer(r'href="(/iyftv/(\d+)/)"[^>]*>(?:<[^>]*>)*([^<]{2,60})</a>', html):
        vid = m.group(2)
        name = m.group(3).strip()
        if vid in seen or not name:
            continue
        seen.add(vid)

        # 检查是否是更新状态
        if re.match(r'^(第?\d+集|完结|正片|抢先版|高清版|更新至|HD|BD)', name):
            continue

        pic = _img(img_map.get(vid, ""))

        # 在附近查找更新状态
        section = html[m.start():m.start()+300]
        remarks = ""
        rm = re.search(r'href="/iyftv/' + vid + '/"[^>]*>(?:<[^>]*>)*([^<]*(?:第\d+集|完结|正片|抢先版|更新至|集)[^<]*)', section)
        if rm:
            remarks = rm.group(1).strip()

        items.append({
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
        })

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

    # 封面
    pm = re.search(r'<div[^>]*class="[^"]*vodPic[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.DOTALL)
    vod_pic = _img(pm.group(1)) if pm else ""

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

    # 按播放源区块分割
    sections = re.split(r'<div[^>]*class="[^"]*playlist[^"]*"[^>]*>', html)

    for sec in sections[1:]:
        # 播放源名称
        sn = re.search(r'<h3[^>]*>([^<]+)</h3>', sec)
        if not sn:
            continue
        source_name = sn.group(1).strip()

        # 集数链接
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
