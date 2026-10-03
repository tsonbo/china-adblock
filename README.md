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

## 本地运行

```sh
python build.py --out output
```

## 自动更新

`.github/workflows/hourly.yml`：每小时 `cron: 7 * * * *` 运行一次并提交变更。
也可在 Actions 页面手动 `Run workflow`。

## 许可与免责

本仓库仅做**规则聚合/去重**，规则版权归各上游作者所有。请遵守各上游许可。
