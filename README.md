# 西班牙语教材点读工具

把《新版现代西班牙语》第一册（扫描版 PDF）变成**可点读的电子教材**：完整保留原书版面，
鼠标点到任意西班牙语单词就能**听到发音**并**看到中文释义**。

---

## 快速开始

```powershell
cd spanish-reader          # 你克隆下来的目录
python serve.py
```

然后用 **Microsoft Edge** 打开提示的地址：

```
http://127.0.0.1:8765/web/index.html
```

> **为什么强调 Edge**：这台机器的 Windows 只装了中文语音（Huihui / Kangkang / Yaoyao），
> 没有西班牙语语音包。Edge 自带微软**在线自然语音**（Elvira / Álvaro / Dalia 等 es-ES / es-MX），
> 西语发音质量很好。Chrome 只能用系统语音，读不了西语。
> 用 Chrome 也能打开，此时会降级到 Google 在线 TTS 音频（需要联网）。

---

## 从仓库克隆后怎么跑

**这个仓库只有工具，没有教材内容。** 教材 PDF、扫描页、以及从课本词表抽取出来的
中文释义都是受版权保护的内容或其衍生作品，已通过 `.gitignore` 排除：

| 被排除的 | 为什么 | 怎么得到 |
|---|---|---|
| `textbook.pdf` | 教材原件；且 191 MB 超过 GitHub 单文件 100 MB 的硬限制 | 自备合法获得的 PDF |
| `pages_raw/`、`pages/` | 305 页教材扫描图 | 跑 `tools/run_all.py` 自动生成 |
| `data/pages.json`、`ocr_all.json` | 教材全文 OCR 结果 | 同上 |
| `data/dict.json`、`lex_glossary.json`、`vocab_raw.json` | 从课本词表抽取的释义 | 同上 |

仓库里**包含**的是通用数据，与任何教材无关：

- `data/dict_seed.json` —— 手写的 1569 个常用西语词
- `data/lex_irregular.json` —— 通用西语不规则动词变位
- `data/dict_extra.json` —— 手写的缩合词与物主形容词

完整流程：

```powershell
git clone <你的仓库地址>
cd spanish-reader
# 把你自己的 textbook.pdf 放到仓库根目录
python tools\run_all.py        # 抽出扫描页 → OCR → 纠错 → 建词典
python serve.py                # 打开 http://127.0.0.1:8765/web/index.html
```

**依赖**：Python 3.8+、Windows PowerShell 5.1（用系统自带 OCR）、Node.js（仅自检用）。
**第三方库一个都不需要** —— 整条流水线只用标准库。

> OCR 那一步用的是 `Windows.Media.Ocr`，所以**必须在 Windows 上跑**。
> 换别的 OCR 引擎需要重写 `tools/repair.py` 的纠错规则表（那套规则是针对
> Windows OCR 的错误模式总结出来的）。

---

## 功能

| 功能 | 说明 |
|---|---|
| **原版版面点读** | 完整保留课本扫描版面（插图、表格、双栏），逐词叠加点击热区，共 35572 个可点词 |
| **点词发音** | 三级降级链：Edge 西语自然语音 → Google 在线 TTS → 明确提示不可用 |
| **点词翻译** | 本地词库优先，未命中可一键在线查词 |
| **动词变位还原** | 点 `tengo` 会告诉你这是 `tener` 的现在时第一人称单数，并给出释义（64414 个词形，含 142 个不规则动词） |
| **整句朗读** | 点行号圆点或 Alt+点击句中任意词，朗读整行并高亮 |
| **全文搜索** | 忽略重音符号（`esta` 能搜到 `está`） |
| **生词本** | ⭐ 收藏、导出 txt；记录阅读进度，下次自动回到上次页码 |
| **缩放 / 缩略图侧栏 / 深浅色主题** | — |

快捷键：`←` `→` 翻页，`Esc` 关卡片，`Ctrl+滚轮` 缩放。

---

## 这个 PDF 有什么特殊之处

**这本教材是纯扫描件，没有文字层。** 191 MB 的 PDF 里是 305 张 JPEG 扫描图，
没有任何 `/Font` 或 `/ToUnicode` 表——也就是说，**任何 PDF 阅读器都选不中、搜不到里面的文字**。
所以整个工具的第一步是把它"读"出来。完整流程：

```
textbook.pdf (191 MB, 305 页纯扫描)
  │
  ├─ ① 自写纯标准库 PDF 解析器      tools/extract_pages.py
  │     抽出 305 张 JPEG 页面图（原来嵌在 DCTDecode 流里）
  │
  ├─ ② WIC 缩放                    tools/resize_pages.ps1
  │     1600px 宽，供网页展示
  │
  ├─ ③ Windows 内置 OCR            tools/ocr_pages.ps1
  │     en-GB + zh-Hans-CN 双引擎，取得**单词级坐标框**
  │     305 页 × 2 语言 ≈ 3 分钟
  │
  ├─ ④ 热区构建                    tools/build_pages.py
  │     剔除中文区域的拉丁乱码（按坐标夹击判定）
  │
  ├─ ⑤ 词典与纠错                  tools/extract_glossary.py / conjugate.py / repair.py
  │
  ├─ ⑥ 抽取课本官方词表            tools/extract_dict.py
  │     总词汇表 969 条 + 单元生词表 584 条（含中文释义）
  │
  └─ ⑦ 合并词典                    tools/build_dict.py
        data/pages.json · dict.json · lemmas.json
```

一键重跑整条流水线：

```powershell
python tools\run_all.py
```

---

## OCR 纠错的思路（为什么不用现成库）

Windows OCR 对西班牙语的错误**高度规律**，不是随机噪声：

| 正确 | OCR 读成 | 出现次数 |
|---|---|---|
| `más` | `mås` | 96 |
| `están` | `estån` | 71 |
| `dónde` | `dönde` / `d6nde` | 32 |
| `español` | `espafiol` | 88 |
| `mañana` | `mafiana` | 62 |
| `los` | `Ios` | 117 |
| `Manolo` | `Man010` | — |
| `¿Cómo` | `i,C6mo` / `G'C6mo` | — |

所以 `tools/repair.py` 用**规则引擎 + 分级词库**来修，而不是靠模糊匹配硬猜：

- **规则**：`å→á`、`ö→ó`、词中数字还原（`0→o 1→l 6→ó`）、`元音+fi+元音 → ñ`
  （这条限定条件很关键：能修 `espafiol→español`，又不会误伤 `oficina`、`fiesta`、`suficiente`）
- **词库分级**：手写种子词库（干净）> 课本总词汇表（规范拼写）> 动词变位表 > 语料高频词
- **两条关键约束**：
  1. 含 `å/ö/词中数字` 的候选重罚——否则"高频出现的垃圾"会自我认证而存活
  2. 候选**或其单数形式**命中词库即接受——这样 `afios` 能通过已知的 `año` 修成 `años`

效果：`å/ä/ö` 误读从 **837 处降到 0**，全部 35572 个可点词中残留明显错误约 1%。

---

## 词典来源与优先级

| 优先级 | 来源 | 条数 | 说明 |
|---|---|---|---|
| 1 | `data/dict_extra.json` | 53 | 手工补充的缩合词/物主形容词（`al` `del` `sus`…） |
| 2 | 手写种子词库 | 3121 | 1569 个常用词的干净中文释义 |
| 3 | 课本总词汇表（294–304 页） | 1480 | 课本官方释义，如 `abrigo→大衣`、`altiplano→高原` |
| 4 | 单元生词表（16 页） | 98 | 补充 |

**为什么手写词库优先于课本词表**：课本词表的中文是 OCR 出来的，常见词反而容易受损，
例如 `de` 被读成"五突兀冒失"、`la` 被读成"您他她它第"。
手写词库覆盖的正是这些最高频的词，用干净释义覆盖更稳妥。

再加上 49875 个动词词形（规则变位 + 142 个不规则动词），最终
**离线查得率 83.8%**（29814 / 35572），其余点「🔍 在线查词」兜底。

---

## 已知限制

1. **发音依赖 Edge + 联网**。本机没有西语语音包；离线环境下西语发音不可用
   （中文语音读不了西语）。装一个西班牙语语音包可以彻底离线。
2. **OCR 残留约 1%**。约 300 个词仍有识别错误，集中在语法表、插图说明等区域
   （如 `[A`、`E]`、`Valk2nte`）。点读时会显示「本地词库未收录」，可用在线查词兜底。
3. **中文释义有少量缺失**。课本词表的中文列 OCR 偶有丢字（如 `siempre` 的释义读成了 `疋`），
   已用部首噪声过滤清理，但无法完全复原。
4. **页码即扫描页序**，与书本印刷页码可能相差 1–2 页（书前有扉页、目录）。
5. 首次打开需加载 4.4 MB 的 `pages.json` 与 3.1 MB 的 `lemmas.json`，本机约 1–2 秒。

---

## 文件结构

```
spanish-reader/
├─ serve.py                  本地服务器（仅标准库）+ /tts 缓存端点
├─ textbook.pdf              原始扫描版教材（191 MB）
├─ cache/tts/                发音缓存（自动生成，可随时删除）
├─ web/
│  └─ index.html             阅读器（单文件、零依赖、无 CDN）
├─ pages/                    305 张展示用页面图（1600px 宽）
├─ dist/                     便携版产物 + 可发送的 zip
├─ data/
│  ├─ pages.json             ★ 热区数据：每页的词 + 归一化坐标 + 文本
│  ├─ dict.json              ★ 词典：4752 条 西→中
│  ├─ lemmas.json            ★ 动词变位表：49875 个词形 → 原形/时式/人称
│  ├─ dict_extra.json        手工补充词条
│  ├─ dict_seed.json         手写常用词库（1569 条）
│  ├─ vocab_raw.json         从课本词表抽取的原始条目
│  ├─ lex_glossary.json      课本总词汇表 → 规范拼写
│  ├─ lex_verbs.json         动词变位表（生成结果）
│  ├─ lex_irregular.json     不规则动词数据（子任务产出）
│  ├─ ocr_all.json           Windows OCR 原始输出（双引擎、含坐标）
│  ├─ pages_ocr.json         热区中间产物（纠错前）
│  └─ _*.txt / _*.log        诊断报告（可删）
└─ tools/
   ├─ run_all.py             ★ 一键重跑数据流水线
   ├─ check_all.py           ★ 一键跑全部自检
   ├─ build_portable.py      ★ 生成免服务器便携版
   ├─ extract_pages.py       纯标准库 PDF 解析，抽页面图
   ├─ resize_pages.ps1       WIC 缩放
   ├─ ocr_pages.ps1          Windows OCR 批处理
   ├─ build_pages.py         OCR → 热区（剔中文区乱码）
   ├─ extract_glossary.py    总词汇表 → 规范拼写词库
   ├─ conjugate.py           西班牙语动词变位生成
   ├─ repair.py              OCR 纠错引擎（规则 + 分级词库）
   ├─ extract_dict.py        课本词表 → 词典条目（含中文）
   ├─ build_dict.py          合并词典
   ├─ dom_shim.js            可观测的 DOM/Audio 替身（供下面的检查用）
   ├─ check_ui.js            前端静态检查 + 查词覆盖率回放
   ├─ check_server_mode.js   服务器版阅读器行为断言
   ├─ check_portable.js      便携版阅读器行为断言
   ├─ check_tts_server.py    /tts 端点断言
   ├─ check_irregular.py     变位表交叉验证
   ├─ verify.py              残留错误模式统计
   ├─ verify_geometry.py     热区坐标与图片对齐验证
   └─ probe.py / inspect_pdf.py / dump_page.py …  诊断工具
```

---

## 分享给别人用（便携版）

当前这份是**服务器版**：数据靠 `fetch` 读取，所以需要跑 `serve.py`，而且
`127.0.0.1` 是回环地址，别人根本访问不到。

`file://` 页面被浏览器禁止 `fetch` 本地 JSON（同源策略），所以直接把文件夹打包发过去
对方双击也是白屏。解决办法是把数据**内联进 HTML**——图片走相对路径的 `<img>`，
而 `<img>` 在 `file://` 下不受限制。构建：

```powershell
python tools\build_portable.py     # 生成 dist\西班牙语点读便携版\
```

产物（约 100 MB，与服务器版共用同一份 `web/index.html`，靠 `window.__DSH_INLINE__`
是否存在决定走哪条加载路径）：

```
dist\西班牙语点读便携版\
  index.html      ← 7 MB，内联了 pages / dict / lemmas 三份数据
  pages\          ← 305 张页面图
  使用说明.txt     ← 给接收者看的说明
```

接收者**解压后双击 `index.html` 即可**，不需要 Python、不需要服务器、不需要装任何东西。

验证：

```powershell
node tools\check_portable.js
```

该脚本用 DOM 桩在 Node 里**真实执行**便携版的全部内联脚本，并把 `fetch` 与
`XMLHttpRequest` 设成"调用即抛异常"，以此证明它真的不依赖网络或服务器：

```
OK   all 2 script blocks executed without throwing
OK   inlined pages: 305 / dict 4752 / lemmas 49875
OK   no literal "<" inside the data blob (so no premature </script>)
OK   PORTABLE mode detected (IMG_BASE = pages/)
变位表已加载：49875 个词形          ← 阅读器完整启动
OK   lookupDict("tengo") -> tener pres. 1s = 有；拥有…
OK   all 305 referenced page images exist on disk
ALL CHECKS PASSED
```

### 两种版本的区别

| | 服务器版 | 便携版 |
|---|---|---|
| 启动方式 | `python serve.py` 后开浏览器 | **双击 index.html** |
| 依赖 | 需要 Python | **无** |
| 数据加载 | `fetch('/data/*.json')` | 内联在 HTML 里 |
| 图片路径 | `/pages/`（绝对） | `pages/`（相对） |
| 交付形态 | 文件夹 | 单个 zip |

两版功能完全一致，都要求接收者用 **Edge** 才有最好的西语发音，且发音需要联网。

### 版权提醒

教材内容版权归原出版社所有。私下发给同学做学习用途是一回事，
**公开发布到网上或用于商业用途是明确的侵权行为**，请自行把握。

---

## 语音响应速度

点一个词到听见声音之间的延迟，来自四个地方，其中两个是原始实现的缺陷：

| 来源 | 原实现 | 现在 |
|---|---|---|
| 重复 `cancel()` | 每次点击都无条件 `cancel()`，**并且连着 cancel 两次** | 只在真的在播时才 cancel |
| 音频元素 | 每次点击 `new Audio(url)`，不复用不缓存 | 缓存池复用，同一个词重播零延迟 |
| 网络往返 | 全部发生在点击**之后** | 鼠标**悬停**时就开始预取 |
| 云端合成 | Edge 在线自然语音**每个词都要云端合成一次** | 无法优化，是这条路的天然短板 |

**核心洞察：音质最好的那条路，往往是最慢的。**
Edge 的「在线自然语音」音质最好，但每个词都要一次云端合成，且 `speechSynthesis`
API 拿不到音频数据，**根本无法缓存或预取**。而 Google TTS 返回的是普通 MP3，
可以悬停预取、可以缓存重播——所以对「点词」这种极短文本，它经常反而更快。

因此工具栏加了**引擎选择**：

- `自动` —— 有西班牙语系统语音就用系统语音
- `在线音频·可预取` —— 强制走可预取的音频路径，**点词通常立刻出声**
- `系统语音` —— 音质优先

状态栏会实时显示 **`上次 XXms`**，这是从点击到 `playing` 事件的实际耗时。
不要凭感觉选，切两次引擎各点几个词，比一比数字。

### 预取策略

- 悬停 70ms 后开始拉音频（防抖，避免鼠标扫过一整行时发出几十个请求）
- 同时最多 4 个预取请求
- 缓存上限 48 条（每条约 20–50KB），按最近使用淘汰，**正在播放的永不淘汰**
- 淘汰尚在加载中的条目时会把预取配额还回去，否则配额只减不增、预取会慢慢停摆

### 验证

语音行为没法在无浏览器环境里试听，但可以断言其**逻辑**。
`tools/check_portable.js` 用一个可观测的 `Audio` 替身（记录构造次数、`play()` 次数，
并可手动触发 `canplay`/`playing`）跑 17 项断言：

```
--- 语音响应速度相关行为 ---
OK   preloadWord() created exactly 1 <audio> element
OK   prefetch does NOT start playback
OK   second hover on the same word reuses the cached element (no new request)
OK   prefetch quota is returned once buffering completes
OK   playing a prefetched word creates no new element (cache hit)
OK   status bar shows the latency: 朗读：在线音频（已缓存 1 词） · 上次 0ms
OK   cache stays bounded: 48 entries (max 48)
OK   no prefetch quota leaked over 122 prefetches (inflight=0)
OK   engine=system switches to the system voice path
```

这套断言在开发中抓到了两个真 bug：淘汰加载中条目导致的**配额泄漏**，
以及延迟为 0 时状态栏不显示的判断错误。

### 服务端 TTS 缓存（已实现）

`serve.py` 多了一个缓存端点：

```
GET /tts?w=hola     -> audio/mpeg   第一次：服务端代拉 Google 并落盘
GET /tts?w=hola     -> audio/mpeg   之后：直接从 cache/tts/ 读，不联网
GET /tts-stats      -> {"files": N, "bytes": M, "mb": x}
```

**为什么要绕这一道**：客户端原本把 `<audio>` 直接指向 Google。那样能播，
但浏览器读不到那些字节（没有 CORS），除了元素自身的生命周期之外什么都缓存不了。
经由本地服务端就成了**同源**，于是可以落盘、可以跨会话复用 ——
一个词听过一次，之后**断网也能重播**。

响应带 `Cache-Control: public, max-age=31536000, immutable`，
浏览器自己也会长缓存，热词连本地服务端都不用问。

**缓存是自热的**：悬停预取本身就会经过 `/tts`，所以正常使用就在填缓存，
不需要也不建议批量预下载（批量拉取 Google TTS 违反其服务条款）。

**安全边界**：只绑 `127.0.0.1`，上游 URL 是固定模板（不是任意 URL 转发），
`w` 限制在 120 字符以内且只允许西语文本字符，因此无法被当作开放代理滥用。
路径穿越、HTML 注入、超长输入都返回 400。

**失败降级**：代理拉不到时（比如服务端没网）自动退回直连 Google，
并置上 `proxyDown` 标记，之后所有词都不再走代理，免得每次都白等一次超时。

删除 `cache/` 目录即可清空缓存，不影响其他任何功能。

### 验证

```powershell
python tools\check_all.py        # 全部 8 个自检套件
```

语音行为没法在无浏览器环境里试听，但可以断言其**逻辑**。
`tools/dom_shim.js` 提供一个可观测的 DOM + `Audio` 替身（记录构造次数、
`play()` 次数，可手动触发 `canplay`/`playing`/`error`），
`check_portable.js` 与 `check_server_mode.js` 用它分别验证两种构建：

```
--- 语音响应速度相关行为 ---
OK   preloadWord() created exactly 1 <audio> element
OK   prefetch does NOT start playback
OK   second hover on the same word reuses the cached element (no new request)
OK   prefetch quota is returned once buffering completes
OK   playing a prefetched word creates no new element (cache hit)
OK   cache stays bounded: 48 entries (max 48)
OK   no prefetch quota leaked over 122 prefetches (inflight=0)
--- 服务器模式 ---
OK   prefetch goes through the local cache, not straight to Google: /tts?w=hola
OK   a proxy error sets proxyDown
OK   the same element retries against the upstream URL
OK   later words go straight upstream once the proxy is known bad
```

这套断言在开发中抓到了三个真 bug：淘汰加载中条目导致的**预取配额泄漏**、
延迟为 0 时状态栏不显示的判断错误，以及 `settle` 回调注册太晚引发的**竞态**。

`tools/check_tts_server.py` 另外对 `/tts` 端点做 24 项检查：
输入校验（缺参/超长/路径穿越/HTML 注入全部 400）、
缓存命中与响应头、HEAD 不触发下载、上游不可达时干净地返回 502 而非挂起、
以及确认静态资源没被这个端点影响。

### 还没做、但能进一步提速的

1. **装本机西班牙语语音包**（收益最大、零成本）。本地语音启动只要几十毫秒，
   而在线语音要几百毫秒。Windows 设置 → 时间和语言 → 语言和区域 →
   添加「西班牙语(西班牙)」并勾选语音。装完在「引擎」里选系统语音即可。
2. ~~服务端 TTS 磁盘缓存~~ —— **已完成**，见上一节。
3. **预生成常用词音频**：把最高频的 1–2 千个词预先合成好打进包里（约 10MB），
   这些词就永久零延迟。但**批量下载 Google TTS 违反其服务条款**，
   要用就得换有明确授权的引擎（Piper、Azure Speech 等）。

---

## 换成别的教材能用吗

可以，但需要改两处（这本教材的版式是硬编码的）：

1. `tools/build_pages.py` 直接在 `textbook.pdf` 上跑，**换书即用**（纯扫描件都行）。
2. `tools/extract_dict.py` 里的 `GLOSARIO_PAGES` / `VOCAB_PAGES` 页码，以及
   `find_chinese_column()` 的列检测阈值，需要按新书调整；若新书没有词表页，
   跳过 ⑥ 直接用手写词库 + 在线查词也能工作。

`tools/repair.py` 的纠错规则是针对 **Windows OCR 引擎**的，换引擎（如 Tesseract）需要重写规则表。
