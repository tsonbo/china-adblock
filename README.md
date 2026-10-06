# china-adblock（中国向去广告规则聚合）

每小时由 GitHub Actions 自动抓取若干「中国区去广告」上游规则，**归一化 + 去重**后输出多格式，
供路由器 AdGuardHome（或 dnsmasq / hosts）订阅。

## 产出

| 文件 | 用途 |
|---|---|
| `output/adguard.txt` | AdGuard/adblock 语法，**AGH 直接订阅** |
| `output/domains.txt` | 纯域名（每行一个） |
| `output/hosts.txt` | `0.0.0.0 域名` |
| `output/dnsmasq.txt` | `address=/域名/0.0.0.0` |
| `output/manifest.json` | 统计（各源条数 / 唯一域名 / 更新时间） |

## 订阅地址（示例，替换 `<用户>` / `<仓库>`）

- GitHub 直连：`https://raw.githubusercontent.com/<用户>/<仓库>/main/output/adguard.txt`
- 国内加速（jsDelivr）：`https://cdn.jsdelivr.net/gh/<用户>/<仓库>@main/output/adguard.txt`
  > jsDelivr 有缓存，更新不会即时；可加 `?t=` 或改用 ghproxy。

## 上游源（K 核心档，2026-10-04 定稿）

| 源 | 独占贡献 | 角色 |
|---|---|---|
| [anti-AD](https://github.com/privacy-protection-tools/anti-AD) | 37,679 | 中文广告/跟踪最全 |
| [Cats-Team/AdRules](https://github.com/Cats-Team/AdRules) | 29,089 | 中国区 ads/trackers |
| [ADgk](https://github.com/banbendalao/ADgk) | 3,930 | 手机/视频 App |
| [xinggsf/Adblock-Plus-Rule](https://github.com/xinggsf/Adblock-Plus-Rule) | 342 | 乘风规则 |

> **选型依据**：anti-AD 与 Cats-Team/AdRules 合计占全量约 **97%**，且各自独占 3 万+ 域名，**不可删**；
> ADgk / xinggsf 为高性价比补充。
> **已剔除零贡献源**：EasyListChina（独占 1）、CJX（0）、AdGuard-ChineseFilter（0）、AWAvenue（13）——
> 见 `build.py` 末尾的「备选」注释，需要时可随时并入。

定稿后聚合去重结果：**约 151,800 个唯一拦截域名**（未扣白名单前的估算）。

## 内置补充规则（EXTRA / EXTRA_HTTPDNS）

除上游源外，`build.py` 内置两组「精选补充域名」，与上游结果一并参与白名单过滤与去重后输出：

| 集合 | 内容 | 说明 |
|---|---|---|
| `EXTRA` | 中国常见广告/跟踪平台 | 上游未覆盖的少量精选（`mmstat.com`、`umeng.com`、`mobads.cn` 等） |
| `EXTRA_HTTPDNS` | App 内置 HTTPDNS / DoH 端点 | **2026-10-06 新增**，见下 |

### EXTRA_HTTPDNS：为什么要拦 App 自带的加密 DNS

很多国产 App（京东、知乎、快手、YY、淘宝系等）**自带加密 DNS 解析器（HTTPDNS / DoH）**，
不查系统 DNS，而是直接向自家端点发起加密请求解析域名。后果是：
**在路由器 / AdGuardHome 上做的去广告对这些 App 完全无效**——因为请求从未经过你的 DNS。

把这些端点加入拦截后，App 会**回落到系统 DNS**，其广告域名才能被正常过滤。

当前内置：

```
doh.jd.com                    京东 DoH
doh.zhihu.com                 知乎 DoH
httpdns.alicdn.com            阿里 HTTPDNS（淘宝/京东/知乎等共用）
httpdns.kwd.inkuai.com        字跳系 HTTPDNS
union-httpdns.gslb.yy.com     YY HTTPDNS
httpdns.c.cdnhwc2.com         华为 HTTPDNS
kuaishou.httpdns.pro          快手 HTTPDNS
```

> 公共 DoH/DoT（`doh.pub`、`dns.alidns.com`）默认**不拦**（可能影响设备「私人 DNS」）。
> 如需强制回落，可在 `build.py` 的 `EXTRA_HTTPDNS` 中取消注释。

> **已知局限**：App **开屏广告**若与主站同域（如 `api.m.jd.com`），DNS 层无法按路径拦截，
> 需应用层跳过工具（GKD、李跳跳等）。DNS 去广告只能拦「独立广告域名」。

## 本地运行

```sh
python build.py --out output
```

## 自动更新

`.github/workflows/hourly.yml`：每小时 `cron: 7 * * * *` 运行一次并提交变更。
也可在 Actions 页面手动 `Run workflow`。

## 许可与免责

本仓库仅做**规则聚合/去重**，规则版权归各上游作者所有。请遵守各上游许可。
