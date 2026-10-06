#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国向去广告规则聚合器：抓取多个上游规则源 -> 归一化 -> 去重 -> 输出多格式。
仅用标准库，可本地或 GitHub Actions 运行。

用法: python build.py [--out output]
输出:
  output/adguard.txt    # AdGuard/adblock 语法（AGH 直接订阅）
  output/domains.txt    # 纯域名（每行一个）
  output/hosts.txt      # 0.0.0.0 域名
  output/dnsmasq.txt    # address=/域名/0.0.0.0
  output/manifest.json  # 统计（源、条数、时间）
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HDRS = {"User-Agent": "china-adblock-aggregator/1.0 (+github-actions)"}

# ---------------------------------------------------------------------------
# 源清单（K 核心档，2026-10-04 定稿）
#   依据「各源独占贡献」分析：
#     anti-AD            独占 37,679
#     Cats-Team/AdRules  独占 29,089   ← 两者合计占全量 ~97%
#     ADgk               独占  3,930   ← 中国手机/视频 App
#     xinggsf            独占    342
#   已剔除「零贡献」源：EasyListChina(独占1)/CJX(0)/AdGuard-ChineseFilter(0)/AWAvenue(13)。
#   每个源给多个候选 URL，取第一个成功的。
# ---------------------------------------------------------------------------
SOURCES = [
    ("anti-AD", [
        "https://raw.githubusercontent.com/privacy-protection-tools/anti-AD/master/anti-ad-domains.txt",
    ]),
    ("Cats-Team/AdRules", [
        "https://raw.githubusercontent.com/Cats-Team/AdRules/main/adblock.txt",
        "https://raw.githubusercontent.com/Cats-Team/AdRules/master/adblock.txt",
    ]),
    ("ADgk", [
        "https://raw.githubusercontent.com/banbendalao/ADgk/master/ADgk.txt",
    ]),
    ("xinggsf-Adblock-Plus-Rule", [
        "https://raw.githubusercontent.com/xinggsf/Adblock-Plus-Rule/master/rule.txt",
        "https://raw.githubusercontent.com/xinggsf/Adblock-Plus-Rule/master/ABP.txt",
    ]),
]

# 备选（需要时并入上表即可）：
#   EasyListChina  https://raw.githubusercontent.com/easylist/easylistchina/master/easylistchina.txt
#   CJX-Annoyance  https://raw.githubusercontent.com/cjx82630/cjxlist/master/cjx-annoyance.txt
#   AdGuard-CN     https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/ChineseFilter/sections/adservers.txt
#   AWAvenue       https://raw.githubusercontent.com/TG-Twilight/AWAvenue-Ads-Rule/main/AWAvenue-Ads-Rule.txt
#   zhiyuan1i      https://raw.githubusercontent.com/zhiyuan1i/adblock_list/master/adblock.txt

IP_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
# 严格域名：仅 [a-z0-9.-]，至少一个点，TLD 为字母；用于剔除被误转的 CSS/选项/正则残片
STRICT_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}$")

# 安全白名单：这些站点（含其子域）永不拦截，防止上游误报导致全屋断服
SAFELIST = {
    "baidu.com", "qq.com", "taobao.com", "tmall.com", "alipay.com", "alibaba.com",
    "alicdn.com", "alipayobjects.com", "weibo.com", "bilibili.com", "jd.com",
    "12306.cn", "wechat.com", "weixin.qq.com", "qqmail.com", "aliyun.com",
    "bdstatic.com", "bdimg.com", "xiaomi.com", "miui.com", "huawei.com",
    "hicloud.com", "apple.com", "icloud.com", "microsoft.com", "windowsupdate.com",
    "gov.cn", "people.com.cn", "cnnic.cn", "taobao.net", "amap.com",
}

# 补充：中国常见广告/跟踪平台（不在上游源内的少量精选）
EXTRA = {
    "mmstat.com", "sinaads.sina.com.cn", "pangle.io", "alimama.cn", "alimama.com",
    "adsmind.com", "adchina.com", "adwo.com", "domob.cn", "mobads.cn", "miaozhen.com",
    "admaster.com.cn", "admaster.cn", "irs01.com", "irs03.com", "youmi.net",
    "dianjoy.com", "mob.com", "umeng.com", "mediav.com", "allyes.com",
    "chuanshanjia.com", "dftoutiao.com", "adview.cn", "ipinyou.com",
}

# 补充：App 内置的 HTTPDNS / DoH 解析端点（2026-10-06 新增）
#   这些域名本身不是广告，但 App 用它们做「加密 DNS 解析」以**绕过系统 DNS**（AdGuard Home），
#   导致其广告域名无法被过滤。封堵后 App 会回落到系统 DNS，广告域名即可被拦截。
#   注意：会关闭对应 App 的私有加密 DNS，属预期行为（换取可过滤）。
EXTRA_HTTPDNS = {
    "doh.jd.com",                      # 京东 DoH
    "doh.zhihu.com",                   # 知乎 DoH
    "httpdns.alicdn.com",              # 阿里 HTTPDNS（淘宝/京东/知乎等大量 App 共用）
    "httpdns.kwd.inkuai.com",          # 快看点/字跳系 HTTPDNS
    "union-httpdns.gslb.yy.com",       # YY HTTPDNS
    "httpdns.c.cdnhwc2.com",           # 华为 HTTPDNS（部分 App 引用）
    "kuaishou.httpdns.pro",            # 快手 HTTPDNS
    # 如需一并封堵公共加密 DNS（会强制相关设备回落明文 DNS），可取消注释：
    # "doh.pub",                       # 腾讯公共 DoH
    # "dns.alidns.com",                # 阿里公共 DoT（Android「私人 DNS」常用）
}


def _parents(d):
    """严格父域（至少去掉一层标签），如 a.b.com -> b.com。"""
    parts = d.split(".")
    for i in range(1, len(parts) - 1):
        yield ".".join(parts[i:])


def _covered(d, S):
    return any(p in S for p in _parents(d))


def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


ANCHOR_RE = re.compile(r"^([a-z0-9][a-z0-9.-]*[a-z0-9])\^?$", re.I)


def normalize(line):
    """返回 (kind, domain)；kind in {"block","allow"}，或 None。

    安全策略（每一条都是踩坑换来的）：
      - 含 `$`（条件规则）、`#`（CSS/整型）、`=`（选项/列表）→ 一律跳过；
      - `||x^` 只接受**不带路径**的纯域名 —— 形如 `||youtube.com/*/log_interaction?`
        的"路径级"规则**绝不能**折叠成 `youtube.com`（否则整站被拦）；
      - `|x^` 同理（不含 `/`、`^`）；
      - 仅接受通过 STRICT_RE 的纯域名。
    """
    s = line.strip()
    if not s or s[0] in "!#[;":
        return None
    kind = "block"
    if s.startswith("@@"):
        kind = "allow"
        s = s[2:]
    if "$" in s or "#" in s or "=" in s:
        return None
    if s.startswith("||"):
        m = ANCHOR_RE.match(s[2:])
        if not m:
            return None
        dom = m.group(1)
    elif s.startswith("|"):
        s = s.strip("|")
        if "/" in s or "^" in s:
            return None
        dom = s
    else:
        parts = s.split()
        if len(parts) >= 2 and IP_RE.match(parts[0]):
            dom = parts[1]
        elif len(parts) == 1:
            dom = parts[0]
        else:
            return None
        if "/" in dom:
            return None
    dom = (dom or "").strip().lower().rstrip(".")
    if not STRICT_RE.match(dom):
        return None
    return (kind, dom)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output")
    ap.add_argument("--analyze", action="store_true", help="打印各源独占贡献与贪心边际")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    block = set()
    allow = set()
    stats = []
    src_sets = {}
    for name, urls in SOURCES:
        got = None
        for u in urls:
            try:
                txt = fetch(u)
                got = (u, txt)
                break
            except Exception as e:
                print("  失败 %s : %s" % (u, e))
        if not got:
            print("[跳过] %s 全部候选失败" % name)
            stats.append({"name": name, "url": None, "lines": 0, "block": 0, "allow": 0, "ok": False})
            continue
        u, txt = got
        n = b = a = 0
        sset = set()
        for ln in txt.splitlines():
            n += 1
            r = normalize(ln)
            if not r:
                continue
            if r[0] == "block":
                block.add(r[1])
                sset.add(r[1])
                b += 1
            else:
                allow.add(r[1])
                a += 1
        src_sets[name] = sset
        print("[OK] %-26s lines=%7d block=%7d allow=%5d  <- %s" % (name, n, b, a, u))
        stats.append({"name": name, "url": u, "lines": n, "block": b, "allow": a, "ok": True})
        time.sleep(0.3)

    # 0) 并入精选补充项（含 App 内置 HTTPDNS/DoH 端点）
    block |= EXTRA | EXTRA_HTTPDNS

    # 1) 白名单：精确 + **父域覆盖**（@@||a.com^ 应放行 a.com 及其子域）
    final = sorted(d for d in block if not _covered(d, allow))

    # 2) 安全白名单：仅保护"主域 + www"（避免整站误封，同时保留对广告子域的拦截）
    def _is_safe(d):
        for sw in SAFELIST:
            if d == sw or d == "www." + sw:
                return True
        return False

    removed = [d for d in final if _is_safe(d)]
    if removed:
        print("[safelist] 剔除核心站点/子域 %d 条：%s" % (len(removed), removed[:15]))
    final = [d for d in final if not _is_safe(d)]

    # 3) 父域冗余消除：某域若已被"另一个已拦父域"覆盖，则删除（AGH ||parent^ 已含子域）
    fset = set(final)
    before = len(final)
    final = sorted(d for d in final if not _covered(d, fset))
    print("[dedup] 父域冗余消除 %d 条（%d -> %d）" % (before - len(final), before, len(final)))

    if args.analyze:
        print("-" * 78)
        print("各源独占贡献（仅本源的域名；删掉该源则永久丢失）：")
        for name, s in sorted(src_sets.items(), key=lambda kv: -len(kv[1])):
            others = set()
            for o, so in src_sets.items():
                if o != name:
                    others |= so
            excl = s - others
            print("  %-28s block=%7d  独占=%7d" % (name, len(s), len(excl)))
        print("-" * 78)
        print("贪心边际（按“新增贡献”从大到小依次添加）：")
        remaining = dict(src_sets)
        cur = set()
        while remaining:
            best = max(remaining, key=lambda k: len(remaining[k] - cur))
            gain = len(remaining[best] - cur)
            cur |= remaining[best]
            print("  + %-28s 新增=%7d  累计=%7d" % (best, gain, len(cur)))
            del remaining[best]

        def U(*names):
            s = set()
            for n in names:
                s |= src_sets.get(n, set())
            return len(s)

        print("-" * 78)
        print("组合规模预估（唯一域名，未扣白名单；AGH 按 0.22KB/条）：")
        combos = [
            ("F 全量(现 9 源)", list(src_sets.keys())),
            ("K 核心 = anti-AD+Cats-Team+ADgk+xinggsf",
             ["anti-AD", "Cats-Team/AdRules", "ADgk", "xinggsf-Adblock-Plus-Rule"]),
            ("M = anti-AD+ADgk", ["anti-AD", "ADgk"]),
            ("N = Cats-Team+ADgk", ["Cats-Team/AdRules", "ADgk"]),
            ("L 轻量 = ADgk+zhiyuan1i+xinggsf",
             ["ADgk", "zhiyuan1i-adblock_list", "xinggsf-Adblock-Plus-Rule"]),
            ("P 极简 = ADgk+xinggsf", ["ADgk", "xinggsf-Adblock-Plus-Rule"]),
        ]
        for nm, names in combos:
            n = U(*names)
            print("  %-44s uniqDom=%7d  AGH≈%5.1f MB  (省约 %.0f MB)" % (nm, n, n * 0.22 / 1024, 43 - n * 0.22 / 1024))
        print("-" * 78)

    with open(os.path.join(args.out, "domains.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(final) + "\n")
    with open(os.path.join(args.out, "adguard.txt"), "w", encoding="utf-8") as f:
        f.write("! Title: china-adblock aggregated\n")
        f.write("! Updated: %s\n" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        f.write("! Count: %d\n" % len(final))
        f.write("! Homepage: (this repo)\n")
        for d in final:
            f.write("||%s^\n" % d)
    with open(os.path.join(args.out, "hosts.txt"), "w", encoding="utf-8") as f:
        for d in final:
            f.write("0.0.0.0 %s\n" % d)
    with open(os.path.join(args.out, "dnsmasq.txt"), "w", encoding="utf-8") as f:
        for d in final:
            f.write("address=/%s/0.0.0.0\n" % d)

    manifest = {
        "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "unique_block_domains": len(final),
        "allow_domains": len(allow),
        "sources": stats,
    }
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("-" * 60)
    print("唯一拦截域名: %d" % len(final))
    print("白名单域名  : %d" % len(allow))
    print("输出目录    : %s" % os.path.abspath(args.out))


if __name__ == "__main__":
    main()
