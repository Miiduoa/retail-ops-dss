# -*- coding: utf-8 -*-
"""Round 36 北科：r35 定稿只刪不增。對準 116 簡章 720／231、成大七項、中央職稱。"""
import os, re, html as htmlmod, hashlib, time
from fontTools.subset import Subsetter, Options
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from weasyprint import HTML
import pymupdf

ROOT = "/tmp/ntut-r36"
FONT_SRC = "/tmp/fju-r19/fonts"
FONT_OUT = os.path.join(ROOT, "fonts-sub")
OUT_DIR = "/opt/cursor/artifacts/ntut-r36"
STORE = "/cursor/stores/self/final/ntut-r36"
WS_DIR = "/workspace/final/ntut-r36"
for d in (FONT_OUT, os.path.join(OUT_DIR, "pages"), os.path.join(STORE, "pages"), os.path.join(WS_DIR, "pages")):
    os.makedirs(d, exist_ok=True)

REPO = "github.com/Miiduoa/retail-ops-dss"
NOW = [
    "GitHub Actions", "1535a052", "viewer.s02", "operator.s01",
    "RailFlow-DSS", "鐵道旅運負荷預測決策支援系統", "B123780665",
    "活動部部長", "Service Crew Leader",
    "資管四B", "資管三B", "Kaggriculture", "scripts_verify",
    "15/27", "30/40", "78.86", "77.53", "GP0115533440",
    "UPDATE／DELETE",
]


def nw(s):
    s = htmlmod.escape(s)
    for p in sorted(NOW, key=len, reverse=True):
        s = s.replace(htmlmod.escape(p), '<span class="nw">' + htmlmod.escape(p) + "</span>")
    return s


def kw(s):
    return f'<span class="kw">{nw(s)}</span>'


def wrap_open(inner):
    """Colour only the opening sentence so the eye lands there first. No new words."""
    i = inner.find("。")
    if i == -1:
        return f'<p><span class="open">{inner}</span></p>'
    return f'<p><span class="open">{inner[: i + 1]}</span>{inner[i + 1 :]}</p>'


def P(s):
    return wrap_open(nw(s))


def Pk(s):
    """Paragraph whose keywords are already marked with kw()/nw()."""
    return wrap_open(s)


def H(s, tag="h2"):
    return f"<{tag}>{nw(s)}</{tag}>"


CSS_CORE = r"""
@font-face { font-family: "Noto Serif CJK TC"; font-weight: 400; src: url("fonts-sub/NotoSerifTC-Regular.ttf"); }
@font-face { font-family: "Noto Serif CJK TC"; font-weight: 700; src: url("fonts-sub/NotoSerifTC-Bold.ttf"); }
@font-face { font-family: "Noto Sans CJK TC"; font-weight: 400; src: url("fonts-sub/NotoSansTC-Regular.ttf"); }
@font-face { font-family: "Noto Sans CJK TC"; font-weight: 700; src: url("fonts-sub/NotoSansTC-Bold.ttf"); }
@font-face { font-family: "DejaVu Sans Mono"; font-weight: 400; src: url("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"); }
html, body {
  background: #ffffff; color: #1c2733;
  font-family: "Noto Serif CJK TC", serif;
  font-size: 10.5pt; line-height: 1.66; margin: 0; padding: 0;
  word-break: keep-all; line-break: strict; hyphens: none;
}
h1 {
  font-family: "Noto Sans CJK TC", sans-serif; font-weight: 700;
  color: #1a4550; text-align: center; margin: 14px 0 4px 0; line-height: 1.3; font-size: 15pt;
}
h2 {
  font-family: "Noto Sans CJK TC", sans-serif; font-weight: 700;
  color: #1a4550; font-size: 11.6pt; border-bottom: 1.2pt solid #1a4550;
  padding: 0 0 4px 0; margin: 14px 0 8px 0;
}
h3 {
  font-family: "Noto Sans CJK TC", sans-serif; font-weight: 700;
  color: #1a4550; font-size: 10.5pt; margin: 12px 0 5px 0;
}
p { margin: 0 0 9px 0; text-align: justify; }
p .open { color: #1a4550; }
.keep { page-break-inside: avoid; }
.kicker { font-family: "Noto Sans CJK TC", sans-serif; font-size: 8.8pt; color: #5e5a55; text-align: center; margin: 0 0 3px 0; }
.sub { font-family: "Noto Sans CJK TC", sans-serif; color: #5e5a55; text-align: center; font-size: 9pt; margin: 0 0 14px 0; }
.nw { white-space: nowrap; }
.kw { color: #1a4550; font-weight: 700; }
a { color: #1c2733; text-decoration: none; }
thead { display: table-header-group; }
p.refs { text-align: left; margin-bottom: 8px; font-size: 9.4pt; line-height: 1.55; color: #1c2733; }
.num { font-weight: 700; color: #1a4550; }
table { border-collapse: collapse; width: 100%; margin: 0 0 14px 0; font-size: 9.5pt; }
th {
  background: #f2f3f3; color: #1c2733;
  font-family: "Noto Sans CJK TC", sans-serif; font-weight: 700;
  text-align: left; border: 0.6pt solid #c5cdd6; padding: 5px 8px;
}
td { border: 0.6pt solid #c5cdd6; padding: 5px 8px; vertical-align: top; }
td.lbl, th.lbl { white-space: nowrap; width: 18%; }
.okline {
  font-family: "Noto Sans CJK TC", sans-serif; font-size: 9.2pt; color: #1a4550;
  margin: 12px 0 0 0; padding-top: 8px; border-top: 0.6pt solid #c5cdd6;
}
code, pre { font-family: "DejaVu Sans Mono", monospace; font-size: 8.2pt; background: #f6f6f5; }
pre { border-left: 2.5pt solid #1a4550; padding: 8px 12px; margin: 8px 0 12px 0; line-height: 1.5; }
.figs { display: flex; gap: 14px; margin: 8px 0 12px 0; }
.figs figure { flex: 1; margin: 0; }
.figs img { width: 100%; border: 0.6pt solid #c5cdd6; }
.wide img { width: 100%; max-height: 148px; object-fit: contain; object-position: left top; border: 0.6pt solid #c5cdd6; }
.proof { page-break-inside: avoid; page-break-before: avoid; margin: 8px 0 12px 0; }
.proof img { width: 100%; max-height: 88mm; object-fit: contain; object-position: left top; border: 0.6pt solid #c5cdd6; }
figcaption { font-family: "Noto Sans CJK TC", sans-serif; font-size: 8.2pt; color: #5e5a55; margin-top: 4px; line-height: 1.4; }
.pagebreak { page-break-before: always; }
.block { margin-bottom: 6px; }
@page scan {
  size: A4; margin: 7mm 7mm 12mm 7mm;
  @bottom-left { content: var(--foot); font-family: "Noto Sans CJK TC"; font-size: 8pt; color: #5e5a55; }
  @bottom-right { content: "第 " counter(page) " 頁"; font-family: "Noto Sans CJK TC"; font-size: 8pt; color: #5e5a55; }
}
.scan { page: scan; page-break-before: always; }
.scan img { width: 100%; height: auto; }
"""


def css_for(foot):
    return CSS_CORE + f"""
:root {{ --foot: "{foot}"; }}
@page {{
  size: A4;
  margin: 14mm 16mm 16mm 16mm;
  @bottom-left {{
    content: "{foot}";
    font-family: "Noto Sans CJK TC"; font-size: 8pt; color: #5e5a55;
  }}
  @bottom-right {{
    content: "第 " counter(page) " 頁";
    font-family: "Noto Sans CJK TC"; font-size: 8pt; color: #5e5a55;
  }}
}}
"""


ALLOW = kw("允許")
DENY = kw("拒絕")
CHAL = kw("要求再驗證")

COND_TABLE = f"""
{H("預期表要寫的條件", "h3")}
<table>
<tr><th>條件</th><th>預計寫進預期表的內容</th></tr>
<tr><td class="lbl">角色與帳號</td><td>檢視者、門市營運、管理者；未登入、正常和已停用的帳號。</td></tr>
<tr><td class="lbl">動作與門市</td><td>要做的動作、目標單據或門市，以及帳號可操作的門市和主店。</td></tr>
<tr><td class="lbl">數量與時段</td><td>補貨或調整的數量、門檻上下的邊界。非營業時間加風險標記，不單獨拒絕。補貨核准有風險標記（含高影響數量）會{CHAL}；庫存調整則在高影響數量時才要求。</td></tr>
<tr><td class="lbl">再驗證狀態</td><td>還沒再驗證、仍在有效期內、已經過期。</td></tr>
</table>
{P("每筆案例的預期結果分成允許、拒絕、要求再驗證三種，也寫明原因碼、資料會不會改變、該留哪些紀錄。答案依門市作業先寫好並凍結。下面是其中一組例子：")}
<div class="keep">
{H("例：門市營運核准同店 500 件補貨", "h3")}
<table>
<tr><th>條件</th><th>預期結果</th></tr>
<tr><td>還沒完成再驗證</td><td>{CHAL}，單據不變</td></tr>
<tr><td>5 分鐘內已完成再驗證</td><td>{ALLOW}，單據改為核准</td></tr>
<tr><td>換成檢視者，即使完成再驗證</td><td>{DENY}，單據不變</td></tr>
</table>
{P("原型目前設定的高影響門檻是 300 件，再驗證有效期是 5 分鐘。")}
</div>
{H("研究做法", "h3")}
<table>
<tr><th>步驟</th><th>預計工作</th></tr>
<tr><td class="lbl">1　寫好預期表</td><td>依工作任務整理上面的條件和每筆案例的預期結果，答案事先固定。</td></tr>
<tr><td class="lbl">2　自動產生測試</td><td>由預期表展開成測試案例，授權判斷和實際寫入資料庫的流程都要測，接進 GitHub Actions，每次 push 執行。</td></tr>
<tr><td class="lbl">3　植入權限錯誤</td><td>每次只改一處規則或程式，例如替檢視者加上核准補貨、把某個動作移出門市範圍檢查、跳過再驗證、讓拒絕路徑不寫紀錄；另外準備一組正確的修改。</td></tr>
<tr><td class="lbl">4　比較與記錄</td><td>24 項手寫測試和新測試跑同一批修改，記錄抓到的錯誤、誤判次數與 CI 時間。</td></tr>
</table>
{P("目前已經有的是原型、24 項測試和 CI。")}
{P("停用帳號、再驗證是否過期，現有測試還沒打到，會寫進預期表。預期表、測試產生程式和植入錯誤實驗要入學後才做。")}
{H("衡量方式", "h3")}
<table>
<thead><tr><th>指標</th><th>預計衡量方式</th></tr></thead>
<tbody>
<tr><td class="lbl">偵測率</td><td>被測試抓到的植入錯誤數／植入錯誤數，依錯誤類型分開呈現；改了程式但行為沒變的植入另外判斷，不列入計算。</td></tr>
<tr><td class="lbl">誤報率</td><td>正確修改（例如新增合法動作並同步更新預期表）卻讓測試失敗的次數／正確修改總數。</td></tr>
<tr><td class="lbl">結果正確性</td><td>允許、拒絕、要求再驗證三種結果分開看，也檢查原因碼，以及單據、庫存有沒有照預期改變。</td></tr>
<tr><td class="lbl">紀錄完整性</td><td>應留紀錄的操作中、人員、時間、動作、門市、結果（拒絕時含原因）都齊全的比例。</td></tr>
<tr><td class="lbl">CI 增加時間</td><td>相同環境下重複執行，比較加入新測試前後的執行時間，呈現中位數與第 95 百分位數。</td></tr>
</tbody>
</table>
"""

PLAN_BODY = [
    "權限規則改過幾次之後，常會有錯誤沒人發現。例如某個角色多了一個動作，或被擋下的操作沒留紀錄。",
    "OWASP Top 10:2025 把存取控制失效排在第一位，也建議把存取控制寫進單元與整合測試 [3][4]。",
    "我打算先依門市作業，把現階段最需要核對的條件寫成一張預期表。每次修改就讓 CI 照表產生測試，看能不能比現有手寫測試多抓到植入的權限錯誤，以及 CI 會多花多少時間。",
    "角色和權限的定義我參考 RBAC 標準 [1]。Martin 與 Xie 用植入錯誤評估權限測試 [2]，測的是 XACML 政策檔。我的原型把規則寫在 Python 裡，還要檢查再驗證和操作紀錄。",
]

ERR_PARAS = [
    "錯誤類型會先從原型裡現有的規則挑：角色權限表、門市範圍清單、再驗證清單和紀錄寫入。每一種都對每條規則逐一植入。",
    "原本那 24 項手寫測試是照既有案例寫的，所以結果會按類型列出兩邊各漏掉哪些。比較時，手寫測試會先補成涵蓋預期表的同一組條件，當作對照組。紀錄欄位和保護方式參考 OWASP 指引 [5]。一開始先用合成資料，結論只講這個原型。",
]
FUTURE_PARAS = [
    "權限切得越細，越權的操作越難得逞，但正常工作被誤擋的機會、管理權限的負擔也可能跟著變高。這個取捨能不能用一組固定的測試案例量出來、操作紀錄要留哪些欄位才夠事後追查又不會多到沒人看，這兩題入學後再做。",
]
CAREER_PARAS = [
    "畢業後我想先做資訊系統開發或維護，再做帳號與存取權限管理、系統安全維護。這兩年想把權限規則寫成能自動跑的測試：改程式時先核對。權限或程式一改，CI 照表跑一次，合併前就看得到改壞的地方。",
]

WHY_SEC = [
    "報資訊安全碩士學位學程，是因為分則列的研究領域有軟體與系統安全。",
    "學院學程介紹把工業物聯網與軟體安全、金融資訊安全管理與稽核列成兩大重點方向 [6]。我的原型處理的是應用層權限、再驗證和操作紀錄，比較接近軟體與系統安全這一頭。",
    "入學後想把測試補成一張預期表，改規則時讓 CI 照表跑。實際開課以入學當年度為準。",
]
WHY_CS = [
    "報資訊工程系碩士班甲組，是因為分則列的研究領域有軟體工程和資訊安全。",
    "我想做的是權限規則改完之後，用測試確認不該過的操作過不了。分則寫資訊工程相關系組原則報考甲組。",
    "我是靜宜資管四年級，修過程式語言、C 語言程式設計、程式設計、機器學習和系統分析與設計。實際開課以入學當年度為準。",
]


def mark_bio(text):
    text = nw(text)
    pairs = [
        "超出帳號授權門市範圍",
        "24 項測試",
        "軟體與系統安全",
        "軟體工程和資訊安全",
        "GitHub Actions",
        "1535a052",
    ]
    for raw in pairs:
        esc = htmlmod.escape(raw)
        marked = '<span class="kw nw">' + esc + "</span>"
        if esc in text and marked not in text:
            text = text.replace(esc, marked, 1)
    return text


def bio_html(why):
    blocks = [
        ("動機", [
            "我在自己做的零售營運小系統裡改管理者權限時，每改一次都要再查：這樣改合不合理，有沒有帳號因此多拿到操作。",
            "大學前幾年我大多在寫程式、做資料分析。",
            "功能做出來以後，碰到的是多人使用的問題：哪個帳號能看哪幾家門市、誰可以改庫存，被擋下的操作事後查不查得到。",
            "碩士班我想做資訊系統和資訊安全，用自動化測試核對權限規則改完對不對。",
        ]),
        ("學習", [
            "我是顧晉瑋，靜宜大學資訊管理學系四年級，預計民國 116 年 6 月畢業。",
            "跟這個方向最相關的課是程式語言、C 語言程式設計、程式設計、機器學習、專案實作（一）和系統分析與設計。",
            "需求預測用機器學習課的模型。角色和補貨單據用系統分析與設計課的方法整理。",
            "112 學年度第 2 學期平均 64，其後四學期都在 75 以上，最近兩學期是 78.86 和 77.53。班排名從 30/40 收到 15/27。",
        ]),
        ("作品", [
            "Retail Ops DSS 是個人作品，" + REPO + " 公開，固定版本 1535a052。資料是 4 間門市、4 個品類、約兩年日銷量。我花最多力氣的是需求、權限表和測試情境。",
            "系統分成檢視、門市營運、管理者三種角色。每個動作先查角色能不能做，權限表裡沒列的動作一律拒絕。門市營運人員只能看、只能改帳號授權範圍內的門市。",
            "超出帳號授權門市範圍的操作會被擋下並留下紀錄。數量很大的補貨核准、變更系統設定這類高影響操作，要近期再驗證一次身分才放行。成功和被拒絕的操作都寫進只能新增、不能修改或刪除的紀錄。",
        ]),
        ("測試", [
            "權限和紀錄這塊，我用自動測試來核對。檢視角色的帳號試著改庫存，會被拒絕。門市營運人員替別家門市補貨，會被拒絕並寫入紀錄。",
            "核准數量 500 的補貨，系統先要求再驗證一次身分，通過才放行。管理者帳號用錯誤密碼登入，會被拒絕並留下紀錄。",
            "我寫了 24 項測試，以存取控制為主。固定版本 2026-10-06 在 GitHub Actions 上驗證通過。畫面、案例和驗證紀錄放在備審資料的實作說明。",
        ]),
        ("比賽與幹部", [
            "比賽方面，我參加過 Kaggle Playground S6E9（公開分數 0.94540）和 DrivenData 帕金森症挑戰（公開分數 0.5591，指標是 log loss，越低越好）。Kaggriculture 已提交並完成評分。",
            "另外參加了臺鐵數據力 2026（民國 115 年）數據資料創意發想競賽（學生組），作品是 RailFlow-DSS 鐵道旅運負荷預測決策支援系統，2026/09 繳交海選企劃。",
            "113 學年度資管系學會活動部部長，負責規劃活動和跨年級協調。114-2 擔任資管三B 副班代。115-1 擔任資管四B 服務股長。",
        ]),
        ("報考", why),
    ]
    out = []
    for title, paras in blocks:
        if title == "測試":
            out.append('<div class="pagebreak"></div>')
            out.append('<p class="kicker">' + nw("自傳（續）　｜　顧晉瑋") + "</p>")
        out.append(H(title, "h3"))
        for p in paras:
            out.append(wrap_open(mark_bio(p)))
    return "\n".join(out)


def study_plan_table():
    return """
<div class="keep">
<table>
<tr><th class="lbl">時間</th><th>修課與研究安排</th></tr>
<tr><td class="lbl">一年級上</td><td>閱讀存取控制測試與植入錯誤的文獻，定下研究問題；先加強資料庫、研究方法和英文文獻閱讀；依開課修與軟體安全、系統安全相關的課程。</td></tr>
<tr><td class="lbl">一年級下</td><td>寫好預期表和測試產生程式並接進 CI，定義錯誤類型，小規模試做並檢查量測定義。</td></tr>
<tr><td class="lbl">二年級上</td><td>執行植入錯誤實驗並和手寫測試比較。</td></tr>
<tr><td class="lbl">二年級下</td><td>完成論文、口試與修訂；依研究成果及指導老師建議評估投稿。</td></tr>
</table>
</div>
"""


def refs_html(extra):
    return f"""
<p class="refs">[1] Ferraiolo, D. F., Sandhu, R., Gavrila, S., Kuhn, D. R., &amp; Chandramouli, R. (2001). Proposed NIST standard for role-based access control. ACM Transactions on Information and System Security, 4(3), 224–274。<br>
[2] Martin, E., &amp; Xie, T. (2007). A fault model and mutation testing of access control policies. In Proceedings of the 16th International Conference on World Wide Web (pp. 667–676). ACM. doi:10.1145/1242572.1242663。<br>
[3] OWASP. (2025). A01:2025 Broken Access Control. OWASP Top 10:2025。<br>
[4] OWASP. Authorization Cheat Sheet。<br>
[5] OWASP. Logging Cheat Sheet。<br>
{extra}</p>
"""


COMP_TABLE = """
<table>
<tr><th>項目</th><th class="lbl">公開結果</th><th>說明</th></tr>
<tr><td>Kaggle Playground S6E9</td><td class="num">0.94540</td><td>練習賽公開榜分數</td></tr>
<tr><td>Kaggriculture v2（Kaggle）</td><td>已提交並完成評分</td><td></td></tr>
<tr><td>DrivenData 帕金森症挑戰</td><td class="num">0.5591</td><td>指標 log loss，越低越好</td></tr>
<tr><td>臺鐵數據力 2026（民國 115 年）數據資料創意發想競賽（學生組）</td><td>—</td><td>RailFlow-DSS 鐵道旅運負荷預測決策支援系統，2026/09 繳交海選企劃</td></tr>
</table>
"""

ACADEMIC = """
<table>
<tr><th class="lbl">項目</th><th>內容</th></tr>
<tr><td class="lbl">六學期平均</td><td class="num">73.74</td></tr>
<tr><td class="lbl">六學期班排／系排</td><td>班排 <span class="num">19/27</span>　系排 <span class="num">40/59</span></td></tr>
<tr><td class="lbl">近期變化</td><td>112 學年度第 2 學期平均 64，其後四學期都在 75 以上，最近兩學期是 78.86 和 77.53；班排名從 30/40 收到 15/27。</td></tr>
<tr><td class="lbl">相關課程</td><td>程式語言 98、C 語言程式設計 96、程式設計 94、機器學習 93、專案實作（一）89、網頁前端程式設計 88、大數據分析 86、作業研究 85、系統分析與設計 83、行動應用軟體開發 81</td></tr>
</table>
<p>完整成績及各學期班／系排名以緊接本頁之後的歷年成績表為準。成績表已印班排與系排，依簡章名次證明可免另傳。</p>
"""


def works_html():
    return f"""
{H("一、Retail Ops DSS（主作品）")}
<p>{nw(REPO)}（公開，MIT 授權）　｜　固定版本 {kw("1535a052")}</p>
<table>
<tr><th class="lbl">項目</th><th>內容</th></tr>
<tr><td class="lbl">性質與工作</td><td>個人作品（非課內專題）；需求整理、權限表、測試情境設計與規則檢查。</td></tr>
<tr><td class="lbl">技術</td><td>Python、pandas、scikit-learn、Streamlit、SQLite；GitHub Actions 自動驗證。</td></tr>
<tr><td class="lbl">資料</td><td>程式產生的合成資料：4 間門市 × 4 個品類 × 約兩年日銷量；固定亂數種子。</td></tr>
</table>
{P("這個作品一開始做銷量預測，以及補貨、人力的文字建議。")}
{P("後來要處理的是：預測結果拿去用之後，誰能改庫存、核准補貨、看哪家門市的資料，事後查不查得到是誰做的。")}
<div class="keep">
<table>
<tr><th class="lbl">已完成功能</th><th>實作內容與範圍</th></tr>
<tr><td class="lbl">角色權限</td><td>檢視者、門市營運與管理者有不同操作權限；權限表沒有列的動作預設拒絕。</td></tr>
<tr><td class="lbl">門市資料範圍</td><td>操作同時檢查角色與可用門市；介面篩選和超出帳號授權門市範圍的拒絕分別有測試。</td></tr>
<tr><td class="lbl">高影響操作</td><td>大量補貨核准、敏感庫存調整及設定變更，依條件要求近期再次驗證身分。</td></tr>
<tr><td class="lbl">操作紀錄</td><td>改庫存、補貨申請與核准、設定變更等操作，允許、拒絕和要求再驗證都會記錄，可篩選、匯出；SQLite 觸發器阻擋對稽核表的 UPDATE／DELETE。</td></tr>
</table>
</div>
{H("二、介面畫面：可見範圍與拒絕提示")}
<div class="figs">
<figure>
<img src="shots/p1_7.png" alt="operator.s01 登入後側欄資料範圍">
<figcaption>圖 1　operator.s01 登入後，側欄顯示資料範圍為 S01，門市選單只列出台北信義店。</figcaption>
</figure>
<figure>
<img src="shots/p1_9.png" alt="檢視者核准被拒絕">
<figcaption>圖 2　介面示範：檢視者沒有核准權限，操作被拒絕。</figcaption>
</figure>
</div>
<div class="pagebreak"></div>
{H("三、測試案例與驗證紀錄")}
<figure class="wide">
<img src="shots/p2_14.png" alt="稽核頁 allow 與 deny">
<figcaption>圖 3　Demo 操作後的稽核頁（2026-10-06）：operator.s01 提出補貨為 {ALLOW}；viewer.s02 改庫存與核准補貨為 {DENY}。</figcaption>
</figure>
<table>
<thead><tr><th class="lbl">核對內容</th><th>固定版本中的案例</th><th>預期／驗證結果</th></tr></thead>
<tbody>
<tr><td class="lbl">同店／資料範圍外</td><td>已完成再驗證的 operator.s01，以相同數量嘗試核准 S01 與 S03 補貨</td><td>S01 {ALLOW}；S03 {DENY}</td></tr>
<tr><td class="lbl">正常作業流程</td><td>operator.s01 在 S01 建立並核准補貨單</td><td>{kw("建立成功")}，狀態為 approved</td></tr>
<tr><td class="lbl">越權作業與紀錄</td><td>operator.s01 向 S03 提出補貨；檢視者在可見門市建立補貨申請</td><td>兩筆都{DENY}；範圍外那筆留有 S03 的拒絕紀錄</td></tr>
<tr><td class="lbl">角色與敏感操作</td><td>檢視者改庫存；未再驗證者核准數量 500 的補貨</td><td>前者{DENY}；後者{CHAL}</td></tr>
<tr><td class="lbl">登入與稽核保護</td><td>正確／錯誤密碼登入；對稽核表執行 UPDATE／DELETE</td><td>登入結果都留紀錄；修改／刪除被{DENY}</td></tr>
</tbody>
</table>
{Pk("固定版本 " + kw("1535a052") + " 共 " + kw("24 項測試") + "（其中 23 項與授權或稽核有關）。GitHub Actions 第 16 次 verify 於 2026-10-06 完成，結果為 " + kw("success") + "。")}
{P("每次推送程式，GitHub Actions 會重跑測試、重新產生資料，並執行 scripts_verify（授權測試、資料、訓練、預測和 app 載入）。")}
{P("重跑方式：依 README 建立 Python 環境（CI 使用 3.12）並安裝依賴，再執行：")}
<pre>python -m unittest tests.test_access_control -v
python generate_data.py
python scripts_verify.py</pre>
{P("上列路徑在固定版本 1535a052 測試通過。觸發器擋的是應用程式對稽核表的改刪。")}
<pre>2026-10-06T10:31:07Z  Ran 24 tests in 2.128s
                      OK
2026-10-06T10:31:13Z  VERIFY_OK</pre>
{P("節錄自 GitHub Actions 第 16 次 verify 作業紀錄（固定版本 1535a052）。")}
<p class="okline">固定版本 1535a052　｜　24 項測試以存取控制為主　｜　GitHub Actions #16　2026-10-06　{kw("VERIFY_OK")}</p>
"""


def build_html(kind):
    if kind == "sec":
        kicker = "國立臺北科技大學　資訊安全碩士學位學程（代碼 720）"
        foot = "顧晉瑋｜北科資安學程"
        why = WHY_SEC
        toc = """
<table>
<tr><th>簡章項目</th><th>本檔位置</th></tr>
<tr><td>三、歷年成績單</td><td>學業節錄之後的掃描頁</td></tr>
<tr><td>四、名次證明</td><td>成績表已印班排／系排，免另傳</td></tr>
<tr><td>五、自傳（含研究興趣及讀書計畫）</td><td>自傳；研究興趣與讀書計畫</td></tr>
<tr><td>六、備審 A　與資安之相關性</td><td>備審 A</td></tr>
<tr><td>六、備審 B　英文能力證明</td><td>無</td></tr>
<tr><td>六、備審 C　專長、專題與實作</td><td>專長課程；Retail Ops DSS</td></tr>
<tr><td>六、備審 D　產業工作經驗、實習或各項得獎證明</td><td>無</td></tr>
<tr><td>六、備審 E　其他</td><td>比賽表；幹部證明；ERP 規劃師 GP0115533440</td></tr>
</table>
"""
        rel_a = f"""
<div class="keep">
{H("備審 A　過去學習、專案與資安之相關性")}
<table>
<tr><th>已做的工作</th><th>對應分則／學程方向</th></tr>
<tr><td>角色權限表、預設拒絕、門市資料範圍</td><td>分則研究領域：{kw("軟體與系統安全")}</td></tr>
<tr><td>高影響操作前再驗證身分</td><td>應用層存取控制；身分核對</td></tr>
<tr><td>允許／拒絕／再驗證都留紀錄；稽核表擋 UPDATE／DELETE</td><td>操作可追查；與學程「金融資訊安全管理與稽核」方向裡的紀錄、查核有關</td></tr>
<tr><td>24 項自動測試，以存取控制為主，接進 GitHub Actions</td><td>規則改完之後用測試核對</td></tr>
</table>
{P("入學後再依開課和指導來選。實際開課以入學當年度為準。")}
</div>
"""
        extra_ref = "[6] 國立臺北科技大學創新前瞻科技研究學院。資訊安全學位學程簡介（2026 年 10 月 13 日查閱）。"
    else:
        kicker = "國立臺北科技大學　資訊工程系碩士班甲組（代碼 231）"
        foot = "顧晉瑋｜北科資工甲組"
        why = WHY_CS
        toc = """
<table>
<tr><th>簡章項目</th><th>本檔位置</th></tr>
<tr><td>三、歷年成績單</td><td>學業節錄之後的掃描頁</td></tr>
<tr><td>四、名次證明</td><td>成績表已印班排／系排，免另傳</td></tr>
<tr><td>五、自傳（含研究興趣及讀書計畫）</td><td>自傳；研究興趣與讀書計畫</td></tr>
<tr><td>六、1　英文能力證明</td><td>無</td></tr>
<tr><td>六、2　專長證明、特殊能力</td><td>相關課程；ERP 規劃師</td></tr>
<tr><td>六、3　著作、獲獎</td><td>無學術發表；比賽為參加，非得獎</td></tr>
<tr><td>六、4　實作成品</td><td>Retail Ops DSS</td></tr>
</table>
"""
        rel_a = ""
        extra_ref = "[6] 國立臺北科技大學。116 學年度研究所碩士班甄試入學招生簡章，資訊工程系碩士班分則。"

    skill_h = "備審 C　專長、專題與實作" if kind == "sec" else "專長證明"
    skill_courses = f"""
<div class="keep">
{H(skill_h)}
<table>
<tr><th>項目</th><th>內容</th></tr>
<tr><td class="lbl">程式與系統</td><td>程式語言 98、C 語言程式設計 96、程式設計 94、機器學習 93、系統分析與設計 83</td></tr>
{"<tr><td class='lbl'>證照</td><td>民國 114 年 12 月取得 ERP 規劃師，中華企業資源規劃學會，證書編號 " + kw("GP0115533440") + "</td></tr>" if kind != "sec" else ""}
</table>
</div>
"""
    if kind == "sec":
        contest_cadre = f"""
<div class="pagebreak"></div>
{H("備審 D　產業工作經驗、實習或各項得獎證明")}
<p>無。</p>
<div class="keep">
{H("備審 E　其他有利於審查之證明文件")}
<p>無學術發表。下列為比賽參加紀錄。</p>
{COMP_TABLE}
{H("幹部經驗")}
<p>113 學年度資管系學會活動部部長；114-2 資管三B 副班代；115-1 資管四B 服務股長。</p>
<figure class="proof"><img src="cadre.png" alt="靜宜 e-Portfolio 擔任幹部"></figure>
</div>
"""
    else:
        contest_cadre = f"""
<div class="keep">
{H("著作、獲獎")}
<p>無學術發表。下列為比賽參加紀錄。</p>
{COMP_TABLE}
{H("幹部經驗")}
<p>113 學年度資管系學會活動部部長；114-2 資管三B 副班代；115-1 資管四B 服務股長。</p>
<figure class="proof"><img src="cadre.png" alt="靜宜 e-Portfolio 擔任幹部"></figure>
</div>
"""
    works_lead = '<div class="pagebreak"></div>' if kind != "sec" else ""
    works_block = f"""
{works_lead}
<p class="kicker">{nw(kicker)}</p>
<h1>實作成品：Retail Ops DSS 的存取控管與操作紀錄</h1>
<p class="sub">個人作品　｜　{nw(REPO)}　｜　固定版本 1535a052</p>
{works_html()}
"""
    erp_e = f"""
<table>
<tr><th>項目</th><th>內容</th></tr>
<tr><td class="lbl">證照</td><td>民國 114 年 12 月取得 ERP 規劃師，中華企業資源規劃學會，證書編號 {kw("GP0115533440")}</td></tr>
</table>
<div class="scan"><img src="cert.jpg" alt="ERP 規劃師證書 GP0115533440"></div>
"""
    cert_scan = """<div class="scan"><img src="cert.jpg" alt="ERP 規劃師證書 GP0115533440"></div>"""
    if kind == "sec":
        dossier = rel_a + H("備審 B　英文能力證明") + "<p>無。</p>" + skill_courses + works_block + contest_cadre + erp_e
    else:
        dossier = H("英文能力證明") + "<p>無。</p>" + skill_courses + cert_scan + contest_cadre + works_block

    html = f"""<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8"><style>{css_for(foot)}</style></head><body>
<p class="kicker">{nw(kicker)}</p>
<h1>116 學年度碩士班甄試　審查資料</h1>
<p class="sub">顧晉瑋　靜宜大學資訊管理學系四年級｜預計民國 116 年 6 月畢業</p>
{H("目錄")}
{toc}
{H("學業節錄")}
{ACADEMIC}
<div class="scan"><img src="transcript_p1.jpg" alt="靜宜大學學士班歷年成績表 第 1 頁"></div>
<div class="scan"><img src="transcript_p2.jpg" alt="靜宜大學學士班歷年成績表 第 2 頁"></div>
<div class="pagebreak"></div>
<p class="kicker">{nw(kicker)}</p>
<h1>自傳</h1>
<p class="sub">含研究興趣及讀書計畫　｜　顧晉瑋</p>
{bio_html(why)}
{H("研究興趣與讀書計畫")}
<p><b>權限規則修改後的存取控制迴歸測試：以零售營運原型為例</b></p>
{"".join(P(x) for x in PLAN_BODY)}
{H("碩士班的安排", "h3")}
{study_plan_table()}
{COND_TABLE}
{"".join(P(x) for x in ERR_PARAS)}
<div class="keep">
{H("畢業之後", "h3")}
{"".join(P(x) for x in CAREER_PARAS)}
{"".join(P(x) for x in FUTURE_PARAS)}
</div>
{H("初步參考資料", "h3")}
{refs_html(extra_ref)}
{H("備審資料")}
{dossier}
</body></html>
"""
    return html, foot


html_sec, _ = build_html("sec")
html_cs, _ = build_html("cs")
joined = html_sec + html_cs

for bad in ["活動長", "Demand Sensing", "我習慣", "而是", "我會在分工", "看紀錄就知道",
            "公開分數 600", "公開分數600", "AI 工具使用揭露", "<a href",
            "跨店拒絕", "跨店那筆", "同店／跨店", "因此要求再驗證",
            "不是", "而不是", "而不只", "目前只做到", "比賽參與、幹部",
            "漸層", "box-shadow", "border-radius"]:
    assert bad not in joined, bad
assert "活動部部長" in html_sec and "活動部部長" in html_cs
assert "113 學年度資管系學會活動部部長" in html_sec
assert "ERP 規劃師" in html_sec and "GP0115533440" in html_sec
assert "114 年 12 月" in html_sec
assert "已提交並完成評分" in html_sec
assert "超出帳號授權門市範圍" in joined
assert "當作對照組" in joined
assert "入學後再做" in joined
assert "\u2060" not in joined
assert "下列為比賽參加紀錄" in html_sec
html_plain = re.sub(r"<[^>]+>", "", joined)
assert "鐵道旅運負荷預測決策支援系統" in html_plain
assert "需求預測用機器學習課的模型" in html_plain
assert "替檢視者加上核准補貨" in html_plain
assert "照既有案例寫的" in html_plain
assert "比較接近軟體與系統安全這一頭" in html_plain
assert "管理者帳號用錯誤密碼登入" in html_plain
assert "Ran 24 tests in 2.128s" in html_plain
assert "原型沒有做到" not in html_plain
assert "公開榜分數已變動" not in html_plain
assert "目前只做到" not in html_plain
assert "而不是" not in html_plain
assert "備審 D　產業工作經驗、實習或各項得獎證明" in html_sec
assert "備審 E　其他有利於審查之證明文件" in html_sec
assert "比賽參與、幹部" not in html_sec
html_flat = re.sub(r"\s+", "", html_plain)
assert "班排名從30/40收到15/27" in html_flat
assert "github.com/Miiduoa/retail-ops-dss" in joined
assert "#1a4550" in joined
assert "#1f3a5f" not in joined
assert "#9b3b32" not in joined and "#2e6b4f" not in joined and "#9a6a12" not in joined
assert "linear-gradient" not in joined and "#6b4" not in joined
assert 'class="open"' in joined

need = re.sub(r"<[^>]+>", "", joined)
need += "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ　、。，．：；！？「」『』（）【】—－–…·／｜＋＝＊＆％＃＠～顧晉瑋北科資安資工甲組"


def inst_subset(vf_name, wght, dst_name):
    vf = TTFont(os.path.join(FONT_SRC, vf_name), recalcBBoxes=False, recalcTimestamp=False)
    font = instantiateVariableFont(vf, {"wght": wght}, inplace=False)
    opt = Options(); opt.hinting = False; opt.layout_features = ["*"]; opt.name_IDs = ["*"]; opt.name_languages = ["*"]
    s = Subsetter(options=opt); s.populate(text=need); s.subset(font)
    dst = os.path.join(FONT_OUT, dst_name); font.save(dst)
    print("subset", dst_name, os.path.getsize(dst))


for a, w, b in [
    ("NotoSansTC-VF.ttf", 400, "NotoSansTC-Regular.ttf"),
    ("NotoSansTC-VF.ttf", 700, "NotoSansTC-Bold.ttf"),
    ("NotoSerifTC-VF.ttf", 400, "NotoSerifTC-Regular.ttf"),
    ("NotoSerifTC-VF.ttf", 700, "NotoSerifTC-Bold.ttf"),
]:
    inst_subset(a, w, b)


def to_pdf(html, name):
    path = os.path.join(ROOT, name + ".html")
    open(path, "w", encoding="utf-8").write(html)
    out = os.path.join(ROOT, name + ".raw.pdf")
    HTML(filename=path, base_url=ROOT).write_pdf(out)
    return out


def strip_meta(doc, title, subject):
    doc.set_metadata({
        "title": title, "author": "顧晉瑋", "subject": subject,
        "keywords": "", "creator": "", "producer": "",
        "creationDate": "", "modDate": "",
    })
    doc.del_xml_metadata()
    for page in doc:
        for link in page.get_links():
            try:
                page.delete_link(link)
            except Exception:
                pass


def save_clean(doc, dest):
    tmp = dest + ".tmp"
    doc.save(tmp, garbage=4, deflate=True, no_new_id=True)
    bb = open(tmp, "rb").read()
    bb = re.sub(rb"% Written by MuPDF[^\r\n]*", lambda m: b"%" + b" " * (len(m.group(0)) - 1), bb)
    open(dest, "wb").write(bb); os.remove(tmp)


def write_bytes(path, data, do_fsync=True):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
        f.flush()
        if do_fsync:
            try:
                os.fsync(f.fileno())
            except OSError:
                pass


def try_copy(src, dest, do_fsync=True):
    data = open(src, "rb").read()
    for attempt in range(4):
        try:
            write_bytes(dest, data, do_fsync=do_fsync)
            if os.path.getsize(dest) == len(data):
                print("copied", dest, len(data))
                return dest
        except OSError as e:
            print("copy fail", dest, attempt, type(e).__name__, e)
            time.sleep(0.4 * (2 ** attempt))
    return None


jobs = [
    (html_sec, "sec", "北科資安學程_審查資料_顧晉瑋.pdf", "ntut36_sec.pdf",
     "審查資料－顧晉瑋", "國立臺北科技大學資訊安全碩士學位學程甄試"),
    (html_cs, "cs", "北科資工甲組_審查資料_顧晉瑋.pdf", "ntut36_cs.pdf",
     "審查資料－顧晉瑋", "國立臺北科技大學資訊工程系碩士班甲組甄試"),
]

print("weasyprint…")
results = []
for html, tag, fname, ascii_name, title, subj in jobs:
    raw = to_pdf(html, tag)
    d = pymupdf.open(raw)
    print(tag, "pages", d.page_count, "links", sum(len(p.get_links()) for p in d))
    strip_meta(d, title, subj)
    dest = os.path.join(OUT_DIR, fname)
    save_clean(d, dest)
    results.append((tag, dest, fname, ascii_name, d.page_count))

sums = []
for tag, dest, fname, ascii_name, n in results:
    d = pymupdf.open(dest)
    fonts = {(f[1], f[2]) for p in d for f in p.get_fonts(full=True)}
    text = "\n".join(p.get_text("text") for p in d)
    nlinks = sum(len(p.get_links()) for p in d)
    meta = d.metadata
    print(tag, "pages", d.page_count, "bytes", os.path.getsize(dest),
          "WJ", text.count("\u2060"), "Type3", any(t == "Type3" for _, t in fonts),
          "links", nlinks, "creator", repr(meta.get("creator")), "producer", repr(meta.get("producer")))
    assert text.count("\u2060") == 0
    assert not any(t == "Type3" for _, t in fonts)
    assert nlinks == 0
    assert not meta.get("creator")
    assert not meta.get("producer")
    assert "活動長" not in text
    assert "AI 工具使用揭露" not in text
    assert "而是" not in text
    assert "GP0115533440" in text
    assert "超出帳號授權門市範圍" in text
    assert "github.com/Miiduoa/retail-ops-dss" in text
    pdir = os.path.join(OUT_DIR, "pages")
    for old in os.listdir(pdir):
        if old.startswith(tag + "_"):
            try:
                os.remove(os.path.join(pdir, old))
            except OSError:
                pass
    for i, p in enumerate(d):
        pix = p.get_pixmap(matrix=pymupdf.Matrix(1.55, 1.55), alpha=False)
        pix.save(os.path.join(pdir, f"{tag}_p{i+1:02d}.png"))
    h = hashlib.sha256(open(dest, "rb").read()).hexdigest()
    line = f"{h}  {fname}"
    print("SHA", line)
    sums.append(line)
    try_copy(dest, dest)
    try_copy(dest, os.path.join(STORE, fname), do_fsync=False)
    try_copy(dest, os.path.join(WS_DIR, fname), do_fsync=False)
    try_copy(dest, os.path.join(OUT_DIR, ascii_name))
    try_copy(dest, os.path.join(STORE, ascii_name), do_fsync=False)
    try_copy(dest, os.path.join(WS_DIR, ascii_name), do_fsync=False)

tr_src = os.path.join(ROOT, "transcript.pdf")
try_copy(tr_src, os.path.join(OUT_DIR, "歷年成績單_顧晉瑋.pdf"))
try_copy(tr_src, os.path.join(OUT_DIR, "ntut36_transcript.pdf"))
try_copy(tr_src, os.path.join(STORE, "歷年成績單_顧晉瑋.pdf"), do_fsync=False)
try_copy(tr_src, os.path.join(STORE, "ntut36_transcript.pdf"), do_fsync=False)
try_copy(tr_src, os.path.join(WS_DIR, "歷年成績單_顧晉瑋.pdf"), do_fsync=False)
try_copy(tr_src, os.path.join(WS_DIR, "ntut36_transcript.pdf"), do_fsync=False)
tr_h = hashlib.sha256(open(tr_src, "rb").read()).hexdigest()
assert tr_h.startswith("b6f874ca8b71")
sums.append(f"{tr_h}  歷年成績單_顧晉瑋.pdf")
sums.append(f"{tr_h}  ntut36_transcript.pdf")

pdir = os.path.join(OUT_DIR, "pages")
spdir = os.path.join(STORE, "pages")
wpdir = os.path.join(WS_DIR, "pages")
if os.path.isdir(pdir):
    for fn in os.listdir(pdir):
        try_copy(os.path.join(pdir, fn), os.path.join(spdir, fn), do_fsync=False)
        try_copy(os.path.join(pdir, fn), os.path.join(wpdir, fn), do_fsync=False)

try_copy(__file__, os.path.join(OUT_DIR, "gen_ntut_r36.py"))
try_copy(__file__, os.path.join(STORE, "gen_ntut_r36.py"), do_fsync=False)
try_copy(__file__, os.path.join(WS_DIR, "gen_ntut_r36.py"), do_fsync=False)

txt = "\n".join(sums) + "\n"
write_bytes(os.path.join(OUT_DIR, "SHA256SUMS.txt"), txt.encode())
write_bytes(os.path.join(STORE, "SHA256SUMS.txt"), txt.encode(), do_fsync=False)
write_bytes(os.path.join(WS_DIR, "SHA256SUMS.txt"), txt.encode(), do_fsync=False)
print("done")
print("\n".join(sums))
