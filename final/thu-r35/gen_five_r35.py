# -*- coding: utf-8 -*-
"""Round 35 分項：逢甲／東海／海大。r32 事實字句；無 AI 列；GitHub 純文字。"""
import os, re, html as htmlmod, hashlib, time
from fontTools.subset import Subsetter, Options
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from weasyprint import HTML
import pymupdf

ROOT = "/tmp/fcu-r35"
FONT_SRC = "/tmp/fju-r19/fonts"
FONT_OUT = os.path.join(ROOT, "fonts-sub")
os.makedirs(FONT_OUT, exist_ok=True)

SCHOOLS = {
    "fcu": ("/opt/cursor/artifacts/fcu-r35", "/cursor/stores/self/final/fcu-r35"),
    "thu": ("/opt/cursor/artifacts/thu-r35", "/cursor/stores/self/final/thu-r35"),
    "ntou": ("/opt/cursor/artifacts/ntou-r35", "/cursor/stores/self/final/ntou-r35"),
}
for out, store in SCHOOLS.values():
    os.makedirs(os.path.join(out, "pages"), exist_ok=True)
    os.makedirs(os.path.join(store, "pages"), exist_ok=True)

REPO = "github.com/Miiduoa/retail-ops-dss"
NOW = [
    "GitHub Actions", "1535a052", "viewer.s02", "operator.s01",
    "RailFlow-DSS", "負荷預測", "抓到多少", "B123780665",
    "活動部部長", "Service Crew Leader", "資管四B", "資管三B",
    "Kaggriculture", "scripts_verify", "15/27", "30/40", "78.86", "77.53",
    "GP0115533440", "CHIN-WEI",
]


def nw(s):
    s = htmlmod.escape(s)
    for p in sorted(NOW, key=len, reverse=True):
        s = s.replace(htmlmod.escape(p), '<span class="nw">' + htmlmod.escape(p) + "</span>")
    return s


def P(s):
    return f"<p>{nw(s)}</p>"


def H(s, tag="h2"):
    return f"<{tag}>{nw(s)}</{tag}>"


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s)


def cjk(s):
    return len(re.findall(r"[\u4e00-\u9fff]", strip_tags(s)))


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
  color: #1f3a5f; text-align: center; margin: 0 0 2px 0; line-height: 1.3; font-size: 15pt;
}
h2 {
  font-family: "Noto Sans CJK TC", sans-serif; font-weight: 700;
  color: #1f3a5f; font-size: 11.5pt; border-bottom: 1.4pt solid #1f3a5f;
  padding: 0 0 3px 0; margin: 10px 0 6px 0;
}
h3 {
  font-family: "Noto Sans CJK TC", sans-serif; font-weight: 700;
  color: #1f3a5f; font-size: 10.4pt; margin: 8px 0 4px 0;
}
p { margin: 0 0 9px 0; text-align: justify; }
.kicker { font-family: "Noto Sans CJK TC", sans-serif; font-size: 8.8pt; color: #5e5a55; text-align: center; margin: 0 0 2px 0; }
.sub { font-family: "Noto Sans CJK TC", sans-serif; color: #5e5a55; text-align: center; font-size: 9pt; margin: 0 0 8px 0; }
.nw { white-space: nowrap; }
a { color: #1c2733; text-decoration: none; }
thead { display: table-header-group; }
p.refs { text-align: left; }
.num { font-weight: 700; color: #1c2733; }
.allow { color: #1f3a5f; font-weight: 700; white-space: nowrap; }
.deny { color: #1f3a5f; font-weight: 700; white-space: nowrap; }
.chal { color: #1f3a5f; font-weight: 700; white-space: nowrap; }
table { border-collapse: collapse; width: 100%; margin: 0 0 7px 0; font-size: 9.4pt; }
th {
  background: #eef1f4; color: #1f3a5f;
  font-family: "Noto Sans CJK TC", sans-serif; font-weight: 700;
  text-align: left; border: 0.6pt solid #c5cdd6; padding: 3.5px 6px;
}
td { border: 0.6pt solid #c5cdd6; padding: 3.5px 6px; vertical-align: top; }
tr:nth-child(even) td { background: #fbfbfa; }
td.lbl, th.lbl { white-space: nowrap; width: 18%; }
.okline {
  font-family: "Noto Sans CJK TC", sans-serif; font-size: 9.2pt; color: #1f3a5f;
  margin: 10px 0 0 0; padding-top: 6px; border-top: 0.6pt solid #c5cdd6;
}
code, pre { font-family: "DejaVu Sans Mono", monospace; font-size: 8.2pt; background: #f6f6f5; }
pre { border-left: 2.5pt solid #8a8178; padding: 6px 10px; margin: 6px 0 8px 0; line-height: 1.45; }
.figs { display: flex; gap: 10px; margin: 6px 0 8px 0; }
.figs figure { flex: 1; margin: 0; }
.figs img { width: 100%; border: 0.6pt solid #c5cdd6; }
.wide img { width: 100%; max-height: 148px; object-fit: contain; object-position: left top; border: 0.6pt solid #c5cdd6; }
.proof { page-break-inside: avoid; }
.proof img { width: 100%; max-height: 88mm; object-fit: contain; object-position: left top; border: 0.6pt solid #c5cdd6; }
figcaption { font-family: "Noto Sans CJK TC", sans-serif; font-size: 8.2pt; color: #5e5a55; margin-top: 3px; line-height: 1.4; }
.pagebreak { page-break-before: always; }
.tight p { margin: 0 0 4px 0; }
.tight table { font-size: 9pt; margin: 0 0 5px 0; }
"""


def css_for(foot):
    return CSS_CORE + f"""
:root {{ --foot: "{foot}"; }}
@page {{
  size: A4;
  margin: 12.5mm 15mm 15mm 15mm;
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


COND_TABLE = """
<h3>預期表要寫的條件</h3>
<table>
<tr><th>條件</th><th>預計寫進預期表的內容</th></tr>
<tr><td class="lbl">角色與帳號</td><td>檢視者、門市營運、管理者；未登入、正常和已停用的帳號。</td></tr>
<tr><td class="lbl">動作與門市</td><td>要做的動作、目標單據或門市，以及帳號可操作的門市和主店。</td></tr>
<tr><td class="lbl">數量與時段</td><td>補貨或調整的數量、門檻上下的邊界。非營業時間加風險標記，不單獨拒絕。補貨核准有風險標記（含高影響數量）會要求再驗證；庫存調整則在高影響數量時才要求。</td></tr>
<tr><td class="lbl">再驗證狀態</td><td>還沒再驗證、仍在有效期內、已經過期。</td></tr>
</table>
<p>每筆案例的預期結果分成允許、拒絕、要求再驗證三種，也寫明原因碼、資料會不會改變、該留哪些紀錄。答案依門市作業先寫好並凍結。下面是其中一組例子：</p>
<h3>例：門市營運核准同店 500 件補貨</h3>
<table>
<tr><th>條件</th><th>預期結果</th></tr>
<tr><td>還沒完成再驗證</td><td><span class="chal">要求再驗證</span>，單據不變</td></tr>
<tr><td>5 分鐘內已完成再驗證</td><td><span class="allow">允許</span>，單據改為核准</td></tr>
<tr><td>換成檢視者，即使完成再驗證</td><td><span class="deny">拒絕</span>，單據不變</td></tr>
</table>
<p>原型目前設定的高影響門檻是 300 件，再驗證有效期是 5 分鐘。</p>
<h3>研究做法</h3>
<table>
<tr><th>步驟</th><th>預計工作</th></tr>
<tr><td class="lbl">1　寫好預期表</td><td>依工作任務整理上面的條件和每筆案例的預期結果，答案事先固定。</td></tr>
<tr><td class="lbl">2　自動產生測試</td><td>由預期表展開成測試案例，授權判斷和實際寫入資料庫的流程都要測，接進 GitHub Actions，每次 push 執行。</td></tr>
<tr><td class="lbl">3　植入權限錯誤</td><td>每次只改一處規則或程式，例如替檢視者加上核准補貨、把某個動作移出門市範圍檢查、跳過再驗證、讓拒絕路徑不寫紀錄；另外準備一組正確的修改。</td></tr>
<tr><td class="lbl">4　比較與記錄</td><td>24 項手寫測試和新測試跑同一批修改，記錄抓到的錯誤、誤判次數與 CI 時間。</td></tr>
</table>
<p>目前已經有的是原型、24 項測試和 CI。停用帳號、再驗證是否過期，現有測試還沒打到，會寫進預期表。預期表、測試產生程式和植入錯誤實驗要入學後才做。</p>
<h3>衡量方式</h3>
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

ERR_TYPE = "錯誤類型會先從原型裡現有的規則挑，也就是角色權限表、門市範圍清單、再驗證清單和紀錄寫入。每一種都對每條規則逐一植入。原本那 24 項手寫測試是照既有案例寫的，所以結果會按類型列出兩邊各漏掉哪些。比較時，手寫測試會先補成涵蓋預期表的同一組條件，當作對照組。紀錄欄位和保護方式參考 OWASP 指引 [5]。一開始先用合成資料，結論只講這個原型。"
CAREER = "畢業後我想先做資訊系統開發或維護，再做帳號與存取權限管理、系統安全維護。這兩年想把權限規則寫成能自動跑的測試：改程式時先核對。權限或程式一改，CI 照表跑一次，合併前就看得到改壞的地方。"
MARTIN = "角色和權限的定義我參考 RBAC 標準 [1]。Martin 與 Xie 用植入錯誤評估權限測試 [2]，測的是 XACML 政策檔。我的原型把規則寫在 Python 裡，還要檢查再驗證和操作紀錄。"
QUESTION = "權限規則改過幾次之後，常會有錯誤沒人發現，例如某個角色多了一個動作，或被擋下的操作沒留紀錄。OWASP Top 10:2025 把存取控制失效排在第一位，也建議把存取控制寫進單元與整合測試 [3][4]。我打算先依門市作業，把現階段最需要核對的條件寫成一張預期表，每次修改就讓 CI 照表產生測試，看能不能比現有手寫測試多抓到植入的權限錯誤，以及 CI 會多花多少時間。"
FUTURE = "權限切得越細，越權的操作越難得逞，但正常工作被誤擋的機會、管理權限的負擔也可能跟著變高。這個取捨能不能用一組固定的測試案例量出來、操作紀錄要留哪些欄位才夠事後追查又不會多到沒人看，這兩題入學後再做。"
RANK = "112 學年度第 2 學期平均 64，其後四學期都在 75 以上，最近兩學期是 78.86 和 77.53；班排名從 30/40 收到 15/27。"
COURSES = "修過的課裡，跟這個方向最相關的是程式語言、C 語言程式設計、程式設計、機器學習、專案實作（一）和系統分析與設計。原型裡的需求預測，用到機器學習課學的模型；角色和補貨單據的流程，則是用系統分析與設計課的方法整理的。"

WHY = {
    "fcu_ics": (
        "報逢甲資通安全碩士學位學程，是因為指定繳交資料含讀書計畫與專題報告，方向對準資通安全。"
        "我想做的是權限規則改完之後，用測試確認不該過的操作過不了；原型處理的是應用層權限、再驗證和操作紀錄。"
        "入學後想把測試補成一張預期表，改規則時讓 CI 照表跑。實際開課以入學當年度為準。"
    ),
    "fcu_cs": (
        "報逢甲資訊工程學系碩士班。系上研究領域含資通安全。"
        "我想做的是權限規則改完之後，用測試確認不該過的操作過不了；原型處理的是應用層權限和操作紀錄。"
        "入學後想把測試補成一張預期表。實際開課以入學當年度為準。"
    ),
    "thu_mis": (
        "報東海資管。分則兩大發展主軸是大數據與人工智慧應用、數位行銷與電子商務應用 [6]。"
        "我想做的是權限規則改完之後，用測試確認不該過的操作過不了；原型處理的是應用層權限和操作紀錄。"
        "入學後依開課選系統與資料相關課程，把測試補成一張預期表。實際開課以入學當年度為準。"
    ),
    "thu_cs": (
        "報東海資工，是因為系所特色列資訊安全技術應用：資通訊安全、網路安全、資訊安保、新興AI資安議題 [6]。"
        "我想做的是權限規則改完之後，用測試確認不該過的操作過不了；原型處理的是應用層權限和操作紀錄。"
        "入學後想把測試補成一張預期表。實際開課以入學當年度為準。"
    ),
    "ntou_cs": (
        "報海大資工。系上課程地圖把資訊安全列成一個領域 [6]。"
        "我想做的是權限規則改完之後，用測試確認不該過的操作過不了；原型處理的是應用層權限和操作紀錄。"
        "入學後想把測試補成一張預期表。實際開課以入學當年度為準。"
    ),
}

REF6 = {
    "fcu_ics": "[6] 逢甲大學。116 學年度碩士班甄試入學招生簡章，資通安全碩士學位學程分則。",
    "fcu_cs": "[6] 逢甲大學。116 學年度碩士班甄試入學招生簡章，資訊工程學系碩士班分則。",
    "thu_mis": "[6] 東海大學。116 學年度碩士班甄試入學招生簡章，資訊管理學系分則。",
    "thu_cs": "[6] 東海大學。116 學年度碩士班甄試入學招生簡章，資訊工程學系分則。",
    "ntou_cs": "[6] 國立臺灣海洋大學資訊工程學系。課程地圖（資訊安全領域；2026 年 10 月 13 日查閱）。",
}

COURSE_LINE = {
    "fcu_ics": "依開課修資通安全相關課程。實際開課以入學當年度為準。",
    "fcu_cs": "依開課修系統或資訊安全相關課程。實際開課以入學當年度為準。",
    "thu_mis": "依開課修系統與資料相關課程。實際開課以入學當年度為準。",
    "thu_cs": "依開課修資訊安全技術應用或系統相關課程。實際開課以入學當年度為準。",
    "ntou_cs": "依開課修資訊安全領域或系統相關課程。實際開課以入學當年度為準。",
}


def bio_paras(why, short=False):
    if short:
        return [
            "我在自己做的零售營運小系統裡改管理者權限時，每改一次都要再查：這樣改合不合理，有沒有帳號因此多拿到操作。",
            "大學前幾年我大多在寫程式、做資料分析。",
            "功能做出來以後，碰到的是多人使用的問題：哪個帳號能看哪幾家門市、誰可以改庫存，被擋下的操作事後查不查得到。",
            "碩士班我想做資訊系統和資訊安全，用自動化測試核對權限規則改完對不對。",
            "我是顧晉瑋，靜宜大學資訊管理學系四年級，預計民國 116 年 6 月畢業。",
            "需求預測用機器學習課的模型。角色和補貨單據用系統分析與設計課的方法整理。",
            RANK,
            "Retail Ops DSS 是個人作品，固定版本 1535a052。角色權限、門市資料範圍、再驗證和操作紀錄已經寫進原型。我寫了 24 項測試，以存取控制為主；固定版本 2026-10-06 在 GitHub Actions 上驗證通過。",
            "民國 114 年 12 月取得 ERP 規劃師，證書編號 GP0115533440。113 學年度資管系學會活動部部長。114-2 擔任資管三B 副班代。115-1 擔任資管四B 服務股長。另外參加了臺鐵數據力 2026（民國 115 年）數據資料創意發想競賽（學生組），作品是 RailFlow-DSS 鐵道旅運負荷預測決策支援系統，2026/09 繳交海選企劃。",
            why,
        ]
    return [
        "我在自己做的零售營運小系統裡改管理者權限時，每改一次都要再查：這樣改合不合理，有沒有帳號因此多拿到操作。",
        "大學前幾年我大多在寫程式、做資料分析。",
        "功能做出來以後，碰到的是多人使用的問題：哪個帳號能看哪幾家門市、誰可以改庫存，被擋下的操作事後查不查得到。",
        "碩士班我想做資訊系統和資訊安全，用自動化測試核對權限規則改完對不對。",
        "我是顧晉瑋，靜宜大學資訊管理學系四年級，預計民國 116 年 6 月畢業。",
        "跟這個方向最相關的課是程式語言、C 語言程式設計、程式設計、機器學習、專案實作（一）和系統分析與設計。",
        "需求預測用機器學習課的模型。角色和補貨單據用系統分析與設計課的方法整理。",
        RANK,
        "Retail Ops DSS 是我用合成資料做的個人作品，" + REPO + " 公開，固定版本 1535a052。資料是 4 間門市、4 個品類、約兩年日銷量。我花最多力氣的是需求、權限表和測試情境。系統分成檢視、門市營運、管理者三種角色。每個動作先查角色能不能做，權限表裡沒列的動作一律拒絕。門市營運人員只能看、只能改帳號授權範圍內的門市。",
        "超出帳號授權門市範圍的操作會被擋下並留下紀錄。數量很大的補貨核准、變更系統設定這類高影響操作，要近期再驗證一次身分才放行。成功和被拒絕的操作都寫進只能新增、不能修改或刪除的紀錄。",
        "權限和紀錄這塊，我用自動測試來核對。檢視角色的帳號試著改庫存，會被拒絕。門市營運人員替別家門市補貨，會被拒絕並寫入紀錄。",
        "核准數量 500 的補貨，系統先要求再驗證一次身分，通過才放行。管理者帳號用錯誤密碼登入，會被拒絕並留下紀錄。",
        "我寫了 24 項測試，以存取控制為主。固定版本 2026-10-06 在 GitHub Actions 上驗證通過。畫面、案例和驗證紀錄放在其他有利於審查之資料。",
        "比賽方面，我參加過 Kaggle Playground S6E9（公開分數 0.94540）和 DrivenData 帕金森症挑戰（公開分數 0.5591，指標是 log loss，越低越好）；Kaggriculture 已提交並完成評分。另外參加了臺鐵數據力 2026（民國 115 年）數據資料創意發想競賽（學生組），作品是 RailFlow-DSS 鐵道旅運負荷預測決策支援系統，2026/09 繳交海選企劃。",
        "113 學年度資管系學會活動部部長，負責規劃活動和跨年級協調。114-2 擔任資管三B 副班代。115-1 擔任資管四B 服務股長。",
        why,
    ]


def study_plan_table(course_line):
    return f"""
<table>
<tr><th class="lbl">時間</th><th>修課與研究安排</th></tr>
<tr><td class="lbl">一年級上</td><td>閱讀存取控制測試與植入錯誤的文獻，定下研究問題；先加強資料庫、研究方法和英文文獻閱讀；{htmlmod.escape(course_line)}</td></tr>
<tr><td class="lbl">一年級下</td><td>寫好預期表和測試產生程式並接進 CI，定義錯誤類型，小規模試做並檢查量測定義。</td></tr>
<tr><td class="lbl">二年級上</td><td>執行植入錯誤實驗並和手寫測試比較。</td></tr>
<tr><td class="lbl">二年級下</td><td>完成論文、口試與修訂；依研究成果及指導老師建議評估投稿。</td></tr>
</table>
"""


def refs_html(extra):
    return f"""
<p class="refs">[1] Ferraiolo, D. F., Sandhu, R., Gavrila, S., Kuhn, D. R., &amp; Chandramouli, R. (2001). Proposed NIST standard for role-based access control. ACM Transactions on Information and System Security, 4(3), 224–274。<br>
[2] Martin, E., &amp; Xie, T. (2007). A fault model and mutation testing of access control policies. In Proceedings of the 16th International Conference on World Wide Web (pp. 667–676). ACM. doi:10.1145/1242572.1242663。<br>
[3] OWASP. (2025). A01:2025 Broken Access Control. OWASP Top 10:2025。<br>
[4] OWASP. Authorization Cheat Sheet。<br>
[5] OWASP. Logging Cheat Sheet。<br>
{htmlmod.escape(extra)}</p>
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


def works_html():
    return f"""
{H("一、Retail Ops DSS（主作品）")}
<p>{nw(REPO)}（公開，MIT 授權）　｜　固定版本 1535a052</p>
<table>
<tr><th class="lbl">項目</th><th>內容</th></tr>
<tr><td class="lbl">性質與工作</td><td>個人作品（非課內專題）；需求整理、權限表、測試情境設計與規則檢查。</td></tr>
<tr><td class="lbl">技術</td><td>Python、pandas、scikit-learn、Streamlit、SQLite；GitHub Actions 自動驗證。</td></tr>
<tr><td class="lbl">資料</td><td>程式產生的合成資料：4 間門市 × 4 個品類 × 約兩年日銷量；固定亂數種子。</td></tr>
</table>
<p>這個作品一開始做銷量預測，以及補貨、人力的文字建議。後來要處理的是：預測結果拿去用之後，誰能改庫存、核准補貨、看哪家門市的資料，事後查不查得到是誰做的。</p>
<table>
<tr><th class="lbl">已完成功能</th><th>實作內容與範圍</th></tr>
<tr><td class="lbl">角色權限</td><td>檢視者、門市營運與管理者有不同操作權限；權限表沒有列的動作預設拒絕。</td></tr>
<tr><td class="lbl">門市資料範圍</td><td>操作同時檢查角色與可用門市；介面篩選和超出帳號授權門市範圍的拒絕分別有測試。</td></tr>
<tr><td class="lbl">高影響操作</td><td>大量補貨核准、敏感庫存調整及設定變更，依條件要求近期再次驗證身分。</td></tr>
<tr><td class="lbl">操作紀錄</td><td>改庫存、補貨申請與核准、設定變更等操作，允許、拒絕和要求再驗證都會記錄，可篩選、匯出；SQLite 觸發器阻擋對稽核表的 UPDATE／DELETE。</td></tr>
</table>
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
<figcaption>圖 3　Demo 操作後的稽核頁（2026-10-06）：operator.s01 提出補貨為 <span class="allow">allow</span>；viewer.s02 改庫存與核准補貨為 <span class="deny">deny</span>。</figcaption>
</figure>
<table>
<thead><tr><th class="lbl">核對內容</th><th>固定版本中的案例</th><th>預期／驗證結果</th></tr></thead>
<tbody>
<tr><td class="lbl">同店／資料範圍外</td><td>已完成再驗證的 operator.s01，以相同數量嘗試核准 S01 與 S03 補貨</td><td>S01 <span class="allow">允許</span>；S03 <span class="deny">拒絕</span></td></tr>
<tr><td class="lbl">正常作業流程</td><td>operator.s01 在 S01 建立並核准補貨單</td><td><span class="allow">建立成功</span>，狀態為 approved</td></tr>
<tr><td class="lbl">越權作業與紀錄</td><td>operator.s01 向 S03 提出補貨；檢視者在可見門市建立補貨申請</td><td>兩筆都<span class="deny">拒絕</span>；範圍外那筆留有 S03 的拒絕紀錄</td></tr>
<tr><td class="lbl">角色與敏感操作</td><td>檢視者改庫存；未再驗證者核准數量 500 的補貨</td><td>前者<span class="deny">拒絕</span>；後者<span class="chal">要求再驗證</span></td></tr>
<tr><td class="lbl">登入與稽核保護</td><td>正確／錯誤密碼登入；對稽核表執行 UPDATE／DELETE</td><td>登入結果都留紀錄；修改／刪除被<span class="deny">拒絕</span></td></tr>
</tbody>
</table>
<p>固定版本 1535a052 共 24 項自動測試（其中 23 項與授權或稽核有關）。上表是其中與示範最相關的幾項。GitHub Actions 第 16 次 verify 於 2026-10-06 完成，結果為 <span class="allow">success</span>。重跑方式：依 README 建立 Python 環境（CI 使用 3.12）並安裝依賴，再執行：</p>
<pre>python -m unittest tests.test_access_control -v
python generate_data.py
python scripts_verify.py</pre>
<pre>2026-10-06T10:31:07Z  Ran 24 tests in 2.128s
                      OK
2026-10-06T10:31:13Z  VERIFY_OK</pre>
<p>節錄自 GitHub Actions 第 16 次 verify 作業紀錄（固定版本 1535a052）。</p>
<p>上列路徑在固定版本 1535a052 測試通過。觸發器擋的是應用程式對稽核表的改刪。</p>
<p class="okline">固定版本 1535a052　｜　24 項測試以存取控制為主　｜　GitHub Actions #16　2026-10-06　<span class="allow">VERIFY_OK</span></p>
"""


def other_html(include_works=False):
    body = ""
    if include_works:
        body += works_html()
    body += f"""
{H("專長與證照")}
<table>
<tr><th>項目</th><th>內容</th></tr>
<tr><td class="lbl">程式與系統</td><td>程式語言 98、C 語言程式設計 96、程式設計 94、機器學習 93、系統分析與設計 83</td></tr>
<tr><td class="lbl">證照</td><td>民國 114 年 12 月取得 ERP 規劃師，中華企業資源規劃學會，證書編號 GP0115533440</td></tr>
</table>
{H("比賽參加紀錄")}
<p>無學術發表。下列為比賽參加紀錄。</p>
{COMP_TABLE}
{H("幹部經驗")}
<p>113 學年度資管系學會活動部部長；114-2 資管三B 副班代；115-1 資管四B 服務股長。</p>
<figure class="proof"><img src="cadre.png" alt="靜宜 e-Portfolio 擔任幹部"></figure>
{H("證照掃描")}
<figure class="proof"><img src="cert.jpg" alt="ERP 規劃師證書 GP0115533440"></figure>
"""
    return body


def resume_html():
    return f"""
<div class="tight">
<table>
<tr><td class="lbl">姓名</td><td>顧晉瑋　英文 KU CHIN-WEI</td></tr>
<tr><td class="lbl">身分證字號</td><td>B123780665</td></tr>
<tr><td class="lbl">出生</td><td>民國 94 年 07 月 29 日</td></tr>
<tr><td class="lbl">電話</td><td>0966198826</td></tr>
<tr><td class="lbl">Email</td><td>demohan513@gmail.com</td></tr>
<tr><td class="lbl">通訊地址</td><td>402 台中市南區學府路200號14樓之1</td></tr>
<tr><td class="lbl">學歷</td><td>靜宜大學資訊管理學系四年級，日間部，應屆；預計民國 116 年 6 月畢業</td></tr>
<tr><td class="lbl">成績</td><td>六學期平均 <span class="num">73.74</span>；班排 <span class="num">19/27</span>、系排 <span class="num">40/59</span>。112 學年度第 2 學期平均 64，其後四學期都在 75 以上，最近兩學期是 78.86 和 77.53；班排名從 30/40 收到 15/27。</td></tr>
<tr><td class="lbl">作品</td><td>Retail Ops DSS（個人作品，固定版本 1535a052）：角色權限、門市資料範圍、再驗證、操作紀錄；24 項測試，GitHub Actions 驗證通過</td></tr>
<tr><td class="lbl">幹部</td><td>113 學年度資管系學會活動部部長；114-2 資管三B 副班代；115-1 資管四B 服務股長</td></tr>
<tr><td class="lbl">證照</td><td>民國 114 年 12 月取得 ERP 規劃師，中華企業資源規劃學會，證書編號 GP0115533440</td></tr>
<tr><td class="lbl">專長</td><td>應用層存取控制測試與操作紀錄</td></tr>
<tr><td class="lbl">論文著作</td><td>無</td></tr>
</table>
</div>
"""


def fcu_ics_sheet():
    return f"""
<table>
<tr><td class="lbl">報考系所</td><td>資通安全碩士學位學程（CI273100）</td></tr>
<tr><td class="lbl">姓名</td><td>顧晉瑋　英文 KU CHIN-WEI</td></tr>
<tr><td class="lbl">就讀學校／科系</td><td>靜宜大學資訊管理學系四年級</td></tr>
<tr><td class="lbl">學歷</td><td>日間部　一般大學（四年制）　應屆；預計民國 116 年 6 月畢業。六學期平均 73.74；班排 19/27、系排 40/59。</td></tr>
<tr><td class="lbl">電話／Email</td><td>0966198826　／　demohan513@gmail.com</td></tr>
<tr><td class="lbl">通訊地址</td><td>402 台中市南區學府路200號14樓之1</td></tr>
<tr><td class="lbl">工作、研究、實習</td><td>Retail Ops DSS 個人作品（固定版本 1535a052）：角色權限、門市資料範圍、再驗證、操作紀錄。113 學年度資管系學會活動部部長。</td></tr>
<tr><td class="lbl">證照</td><td>民國 114 年 12 月取得 ERP 規劃師，中華企業資源規劃學會，證書編號 GP0115533440</td></tr>
<tr><td class="lbl">專長與研究方向</td><td>應用層存取控制測試與操作紀錄</td></tr>
<tr><td class="lbl">論文著作</td><td>無</td></tr>
</table>
"""


def fcu_cs_form():
    return f"""
<p class="sub">格式依招生網頁指定表格（006.odt）欄位填寫　｜　填表日期：民國 115 年 10 月 13 日</p>
{H("一、基本資料")}
<table>
<tr><td class="lbl">中文姓名</td><td>顧晉瑋</td></tr>
<tr><td class="lbl">英文姓名</td><td>Last Name：KU　First Name：CHIN-WEI</td></tr>
<tr><td class="lbl">聯絡電話</td><td>0966198826</td></tr>
<tr><td class="lbl">行動電話</td><td>0966198826</td></tr>
<tr><td class="lbl">E-MAIL</td><td>demohan513@gmail.com</td></tr>
<tr><td class="lbl">欲研究領域</td><td>☑ 資通安全　☐ 人工智慧　☐ 網路工程與網路管理　☐ 軟體工程與應用　☐ 電腦系統與物聯網　☐ 生物資訊　☐ 其他</td></tr>
</table>
{H("二、主要學歷")}
<table>
<tr><th>畢／肄業學校</th><th>國籍</th><th>主修學門系所</th><th>學位</th><th>起訖年月</th><th>學業成績</th><th>系排名</th></tr>
<tr><td>靜宜大學</td><td>中華民國</td><td>資訊管理學系</td><td>在學中</td><td>112/9～116/6</td><td class="num">73.74</td><td>40/59</td></tr>
</table>
{H("三、學術發表")}
<table>
<tr><td class="lbl">專題報告</td><td>無課內專題。個人作品 Retail Ops DSS（固定版本 1535a052）見專題報告檔。</td></tr>
<tr><td class="lbl">期刊論文</td><td>無</td></tr>
<tr><td class="lbl">會議論文</td><td>無</td></tr>
<tr><td class="lbl">研究計畫</td><td>無</td></tr>
</table>
{H("四、CPE 考試成果")}
<p>無。</p>
{H("五、其他專業表現與相關特殊專長")}
<table>
<tr><th>類別</th><th>名稱</th></tr>
<tr><td class="lbl">證照</td><td>民國 114 年 12 月取得 ERP 規劃師，中華企業資源規劃學會，證書編號 GP0115533440</td></tr>
<tr><td class="lbl">幹部</td><td>113 學年度資管系學會活動部部長；114-2 資管三B 副班代；115-1 資管四B 服務股長</td></tr>
<tr><td class="lbl">比賽參加</td><td>Kaggle Playground S6E9；Kaggriculture（已提交並完成評分）；DrivenData 帕金森症挑戰；臺鐵數據力 2026（民國 115 年）數據資料創意發想競賽（學生組），RailFlow-DSS 鐵道旅運負荷預測決策支援系統，2026/09 繳交海選企劃</td></tr>
</table>
"""


def plan_full(kind):
    return f"""
<p><b>權限規則修改後的存取控制迴歸測試：以零售營運原型為例</b></p>
{P(QUESTION)}
{P(MARTIN)}
{H("碩士班的安排", "h3")}
{study_plan_table(COURSE_LINE[kind])}
{COND_TABLE}
{P(ERR_TYPE)}
{P(FUTURE)}
{H("畢業之後", "h3")}
{P(CAREER)}
{H("初步參考資料", "h3")}
{refs_html(REF6[kind])}
"""


def plan_compact(kind):
    body = f"""
<p><b>權限規則修改後的存取控制迴歸測試：以零售營運原型為例</b></p>
{P(QUESTION)}
{P(MARTIN)}
{H("碩士班的安排", "h3")}
{study_plan_table(COURSE_LINE[kind])}
{H("預期表要寫的條件", "h3")}
<p>角色與帳號、動作與門市、數量與時段、再驗證狀態。非營業時間加風險標記，不單獨拒絕。補貨核准有風險標記（含高影響數量）會要求再驗證；庫存調整則在高影響數量時才要求。</p>
{H("例：門市營運核准同店 500 件補貨", "h3")}
<table>
<tr><th>條件</th><th>預期結果</th></tr>
<tr><td>還沒完成再驗證</td><td><span class="chal">要求再驗證</span>，單據不變</td></tr>
<tr><td>5 分鐘內已完成再驗證</td><td><span class="allow">允許</span>，單據改為核准</td></tr>
<tr><td>換成檢視者，即使完成再驗證</td><td><span class="deny">拒絕</span>，單據不變</td></tr>
</table>
<p>目前已經有的是原型、24 項測試和 CI。原型目前設定的高影響門檻是 300 件，再驗證有效期是 5 分鐘。做法：先寫好預期表並凍結答案；由預期表展開測試並接進 GitHub Actions；每次只改一處規則或程式來植入權限錯誤；24 項手寫測試和新測試跑同一批修改。比較時，手寫測試會先補成涵蓋預期表的同一組條件，當作對照組。預期表、測試產生程式和植入錯誤實驗要入學後才做。</p>
{P(ERR_TYPE)}
{P(FUTURE)}
{H("畢業之後", "h3")}
{P(CAREER)}
{H("初步參考資料", "h3")}
{refs_html(REF6[kind])}
"""
    n = cjk(body)
    print("THU MIS plan CJK", n)
    assert n <= 1500, n
    return body


def wrap(foot, kicker, title, body):
    return f"""<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8"><style>{css_for(foot)}</style></head><body>
<p class="kicker">{nw(kicker)}</p>
<h1>{nw(title)}</h1>
<p class="sub">顧晉瑋　靜宜大學資訊管理學系四年級｜預計民國 116 年 6 月畢業</p>
{body}
</body></html>
"""


def bio_block(kind, short=False, split=False):
    paras = [P(p) for p in bio_paras(WHY[kind], short=short)]
    if split:
        return (
            "\n".join(paras[:10])
            + '<div class="pagebreak"></div><p class="kicker">自傳（續）　｜　顧晉瑋</p>\n'
            + "\n".join(paras[10:])
        )
    return "\n".join(paras)


# --- documents ---
docs = []

# FCU ICS
k_ics, f_ics = "逢甲大學　資通安全碩士學位學程（CI273100）", "顧晉瑋｜逢甲資通安全"
docs.append(("fcu", "ics_form", "逢甲資通安全_4_個人基本資料表含自傳_顧晉瑋.pdf", "fcu35_ics_form.pdf",
             "個人基本資料表含自傳－顧晉瑋", "逢甲大學資通安全碩士學位學程甄試",
             wrap(f_ics, k_ics, "個人基本資料表（含自傳）",
                  fcu_ics_sheet() + H("自傳") + bio_block("fcu_ics"))))
docs.append(("fcu", "ics_plan", "逢甲資通安全_5_讀書計畫_顧晉瑋.pdf", "fcu35_ics_plan.pdf",
             "讀書計畫－顧晉瑋", "逢甲大學資通安全碩士學位學程甄試",
             wrap(f_ics, k_ics, "讀書計畫（含研究方向）", plan_full("fcu_ics"))))
docs.append(("fcu", "ics_other", "逢甲資通安全_6_其他有助甄試資料_顧晉瑋.pdf", "fcu35_ics_other.pdf",
             "其他有助甄試資料－顧晉瑋", "逢甲大學資通安全碩士學位學程甄試",
             wrap(f_ics, k_ics, "其他有助於甄試之資料", other_html(include_works=True))))

# FCU CS
k_fcs, f_fcs = "逢甲大學　資訊工程學系碩士班（CE073100）", "顧晉瑋｜逢甲資工"
docs.append(("fcu", "cs_form", "逢甲資工_3_個人基本資料表含自傳_顧晉瑋.pdf", "fcu35_cs_form.pdf",
             "個人基本資料表含自傳－顧晉瑋", "逢甲大學資訊工程學系碩士班甄試",
             wrap(f_fcs, k_fcs, "個人基本資料表（含自傳）",
                  fcu_cs_form() + '<div class="pagebreak"></div>' + H("六、自傳") + bio_block("fcu_cs", split=True))))
docs.append(("fcu", "cs_plan", "逢甲資工_4_研究計畫書_顧晉瑋.pdf", "fcu35_cs_plan.pdf",
             "研究計畫書－顧晉瑋", "逢甲大學資訊工程學系碩士班甄試",
             wrap(f_fcs, k_fcs, "研究計畫書", plan_full("fcu_cs"))))
docs.append(("fcu", "cs_work", "逢甲資工_5_專題報告_顧晉瑋.pdf", "fcu35_cs_work.pdf",
             "專題報告－顧晉瑋", "逢甲大學資訊工程學系碩士班甄試",
             wrap(f_fcs, k_fcs, "專題報告：Retail Ops DSS 的存取控管與操作紀錄", works_html())))
docs.append(("fcu", "cs_other", "逢甲資工_6_其他有助甄試資料_顧晉瑋.pdf", "fcu35_cs_other.pdf",
             "其他有助甄試資料－顧晉瑋", "逢甲大學資訊工程學系碩士班甄試",
             wrap(f_fcs, k_fcs, "其他有助於甄試之資料", other_html(include_works=False))))

# THU MIS
k_tmis, f_tmis = "東海大學　資訊管理學系（4901）", "顧晉瑋｜東海資管"
thu_mis_bio = bio_block("thu_mis", short=True)
print("THU MIS bio CJK", cjk(thu_mis_bio))
assert cjk(thu_mis_bio) <= 1000
docs.append(("thu", "mis_cv", "東海資管_2a_個人簡歷_顧晉瑋.pdf", "thu35_mis_cv.pdf",
             "個人簡歷－顧晉瑋", "東海大學資訊管理學系碩士班甄試",
             wrap(f_tmis, k_tmis, "個人簡歷", resume_html()), True))  # expect 1 page
docs.append(("thu", "mis_bio", "東海資管_2b_自傳_顧晉瑋.pdf", "thu35_mis_bio.pdf",
             "自傳－顧晉瑋", "東海大學資訊管理學系碩士班甄試",
             wrap(f_tmis, k_tmis, "自傳", thu_mis_bio)))
docs.append(("thu", "mis_plan", "東海資管_3_研究或讀書計畫_顧晉瑋.pdf", "thu35_mis_plan.pdf",
             "研究或讀書計畫－顧晉瑋", "東海大學資訊管理學系碩士班甄試",
             wrap(f_tmis, k_tmis, "研究或讀書計畫", plan_compact("thu_mis"))))
docs.append(("thu", "mis_other", "東海資管_4_其他有利佐證_顧晉瑋.pdf", "thu35_mis_other.pdf",
             "其他有利佐證－顧晉瑋", "東海大學資訊管理學系碩士班甄試",
             wrap(f_tmis, k_tmis, "其他有利佐證文件", other_html(include_works=True))))

# THU CS
k_tcs, f_tcs = "東海大學　資訊工程學系（3501）", "顧晉瑋｜東海資工"
docs.append(("thu", "cs_bio", "東海資工_3_履歷自傳_顧晉瑋.pdf", "thu35_cs_bio.pdf",
             "履歷自傳－顧晉瑋", "東海大學資訊工程學系碩士班甄試",
             wrap(f_tcs, k_tcs, "履歷自傳", H("簡歷") + resume_html() + H("自傳") + bio_block("thu_cs"))))
docs.append(("thu", "cs_plan", "東海資工_2_研究所讀書計畫_顧晉瑋.pdf", "thu35_cs_plan.pdf",
             "研究所讀書計畫－顧晉瑋", "東海大學資訊工程學系碩士班甄試",
             wrap(f_tcs, k_tcs, "研究所讀書計畫", plan_full("thu_cs"))))
docs.append(("thu", "cs_work", "東海資工_4_研究報告_顧晉瑋.pdf", "thu35_cs_work.pdf",
             "研究報告－顧晉瑋", "東海大學資訊工程學系碩士班甄試",
             wrap(f_tcs, k_tcs, "研究報告：Retail Ops DSS 的存取控管與操作紀錄", works_html())))
docs.append(("thu", "cs_other", "東海資工_5_其他有利審查資料_顧晉瑋.pdf", "thu35_cs_other.pdf",
             "其他有利審查資料－顧晉瑋", "東海大學資訊工程學系碩士班甄試",
             wrap(f_tcs, k_tcs, "其他有利審查之相關資料", other_html(include_works=False))))

# NTOU CS
k_n, f_n = "國立臺灣海洋大學　資訊工程學系碩士班", "顧晉瑋｜海大資工"
docs.append(("ntou", "cs_bio", "海大資工_自傳_顧晉瑋.pdf", "ntou35_bio.pdf",
             "自傳－顧晉瑋", "國立臺灣海洋大學資訊工程學系碩士班甄試",
             wrap(f_n, k_n, "自傳", H("簡歷") + resume_html() + H("自傳") + bio_block("ntou_cs"))))
docs.append(("ntou", "cs_plan", "海大資工_讀書計畫_顧晉瑋.pdf", "ntou35_plan.pdf",
             "讀書計畫－顧晉瑋", "國立臺灣海洋大學資訊工程學系碩士班甄試",
             wrap(f_n, k_n, "讀書計畫（研究構想）", plan_full("ntou_cs"))))
docs.append(("ntou", "cs_work", "海大資工_專題報告_顧晉瑋.pdf", "ntou35_work.pdf",
             "專題報告－顧晉瑋", "國立臺灣海洋大學資訊工程學系碩士班甄試",
             wrap(f_n, k_n, "專題報告：Retail Ops DSS 的存取控管與操作紀錄", works_html())))
docs.append(("ntou", "cs_other", "海大資工_其他有利審查資料_顧晉瑋.pdf", "ntou35_other.pdf",
             "其他有利審查資料－顧晉瑋", "國立臺灣海洋大學資訊工程學系碩士班甄試",
             wrap(f_n, k_n, "其他有利審查資料", other_html(include_works=False))))

joined = "".join(d[6] for d in docs)
mis_plan_html = next(d[6] for d in docs if d[1] == "mis_plan")
assert "目前已經有的是原型、24 項測試和 CI" in mis_plan_html
assert "入學後才做" in mis_plan_html
if os.environ.get("ONLY"):
    docs = [d for d in docs if d[1] == os.environ["ONLY"]]
for bad in ["活動長", "Demand Sensing", "我習慣", "而是", "我會在分工", "看紀錄就知道",
            "公開分數 600", "公開分數600", "AI 工具使用揭露", "<a href",
            "跨店拒絕", "跨店那筆", "同店／跨店", "因此要求再驗證", "不是", "而不只"]:
    assert bad not in joined, bad
assert "活動部部長" in joined
assert "113 學年度資管系學會活動部部長" in joined
assert "ERP 規劃師" in joined and "GP0115533440" in joined
assert "114 年 12 月" in joined
assert "鐵道旅運負荷預測決策支援系統" in joined
assert "而不只" not in joined
assert "已提交並完成評分" in joined
assert "超出帳號授權門市範圍" in joined
assert "當作對照組" in joined
assert "入學後再做" in joined
assert "\u2060" not in joined
assert "下列為比賽參加紀錄" in joined
html_flat = re.sub(r"\s+", "", strip_tags(joined))
assert "班排名從30/40收到15/27" in html_flat
assert "github.com/Miiduoa/retail-ops-dss" in joined
assert "☑ 資通安全" in joined

need = strip_tags(joined)
need += "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ　、。，．：；！？「」『』（）【】—－–…·／｜＋＝＊＆％＃＠～☑☐顧晉瑋逢甲資通安全資工東海海大"


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


print("weasyprint…", len(docs), "docs")
sums = {"fcu": [], "thu": [], "ntou": []}
page_info = []

for item in docs:
    school, tag, fname, ascii_name, title, subj, html = item[:7]
    expect_one = len(item) > 7 and item[7]
    outdir, store = SCHOOLS[school]
    raw = to_pdf(html, tag)
    d = pymupdf.open(raw)
    print(tag, "pages", d.page_count, "links", sum(len(p.get_links()) for p in d))
    if expect_one:
        assert d.page_count == 1, (tag, d.page_count)
    strip_meta(d, title, subj)
    dest = os.path.join(outdir, fname)
    save_clean(d, dest)
    d2 = pymupdf.open(dest)
    fonts = {(f[1], f[2]) for p in d2 for f in p.get_fonts(full=True)}
    text = "\n".join(p.get_text("text") for p in d2)
    nlinks = sum(len(p.get_links()) for p in d2)
    print(tag, "bytes", os.path.getsize(dest), "WJ", text.count("\u2060"),
          "Type3", any(t == "Type3" for _, t in fonts), "links", nlinks)
    assert text.count("\u2060") == 0
    assert not any(t == "Type3" for _, t in fonts)
    assert nlinks == 0
    assert "活動長" not in text
    assert "AI 工具使用揭露" not in text
    pdir = os.path.join(outdir, "pages")
    for old in os.listdir(pdir):
        if old.startswith(tag + "_"):
            try:
                os.remove(os.path.join(pdir, old))
            except OSError:
                pass
    for i, p in enumerate(d2):
        pix = p.get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4), alpha=False)
        pix.save(os.path.join(pdir, f"{tag}_p{i+1:02d}.png"))
    h = hashlib.sha256(open(dest, "rb").read()).hexdigest()
    sums[school].append(f"{h}  {fname}")
    sums[school].append(f"{h}  {ascii_name}")
    page_info.append((school, fname, d2.page_count, h, os.path.getsize(dest)))
    try_copy(dest, os.path.join(store, fname), do_fsync=False)
    try_copy(dest, os.path.join(outdir, ascii_name))
    try_copy(dest, os.path.join(store, ascii_name), do_fsync=False)

# merge THU MIS 簡歷+自傳 into slot 2
thu_out, thu_store = SCHOOLS["thu"]
cv = os.path.join(thu_out, "東海資管_2a_個人簡歷_顧晉瑋.pdf")
bio = os.path.join(thu_out, "東海資管_2b_自傳_顧晉瑋.pdf")
merged = pymupdf.open()
merged.insert_pdf(pymupdf.open(cv))
merged.insert_pdf(pymupdf.open(bio))
strip_meta(merged, "個人簡歷與自傳－顧晉瑋", "東海大學資訊管理學系碩士班甄試")
slot2 = os.path.join(thu_out, "東海資管_2_個人簡歷與自傳_顧晉瑋.pdf")
save_clean(merged, slot2)
h2 = hashlib.sha256(open(slot2, "rb").read()).hexdigest()
sums["thu"].append(f"{h2}  東海資管_2_個人簡歷與自傳_顧晉瑋.pdf")
sums["thu"].append(f"{h2}  thu35_mis_cvbio.pdf")
try_copy(slot2, os.path.join(thu_store, "東海資管_2_個人簡歷與自傳_顧晉瑋.pdf"), do_fsync=False)
try_copy(slot2, os.path.join(thu_out, "thu35_mis_cvbio.pdf"))
try_copy(slot2, os.path.join(thu_store, "thu35_mis_cvbio.pdf"), do_fsync=False)
page_info.append(("thu", "東海資管_2_個人簡歷與自傳_顧晉瑋.pdf", pymupdf.open(slot2).page_count, h2, os.path.getsize(slot2)))

tr_src = os.path.join(ROOT, "transcript.pdf")
tr_h = hashlib.sha256(open(tr_src, "rb").read()).hexdigest()
assert tr_h.startswith("b6f874ca8b71"), tr_h
tr_names = {
    "fcu": [
        ("歷年成績單_顧晉瑋.pdf", "fcu35_transcript.pdf"),
        ("逢甲資通安全_1_歷年成績單_顧晉瑋.pdf", "fcu35_ics_tr.pdf"),
        ("逢甲資工_1_歷年成績單_顧晉瑋.pdf", "fcu35_cs_tr.pdf"),
    ],
    "thu": [
        ("歷年成績單_顧晉瑋.pdf", "thu35_transcript.pdf"),
        ("東海資管_1_歷年成績單_顧晉瑋.pdf", "thu35_mis_tr.pdf"),
        ("東海資工_1_歷年成績單_顧晉瑋.pdf", "thu35_cs_tr.pdf"),
    ],
    "ntou": [
        ("歷年成績單_顧晉瑋.pdf", "ntou35_transcript.pdf"),
        ("海大資工_歷年成績單_顧晉瑋.pdf", "ntou35_tr.pdf"),
    ],
}
if os.environ.get("ONLY"):
    tr_names = {}
for school, names in tr_names.items():
    outdir, store = SCHOOLS[school]
    for cn, ascii_n in names:
        try_copy(tr_src, os.path.join(outdir, cn))
        try_copy(tr_src, os.path.join(store, cn), do_fsync=False)
        try_copy(tr_src, os.path.join(outdir, ascii_n))
        try_copy(tr_src, os.path.join(store, ascii_n), do_fsync=False)
        sums[school].append(f"{tr_h}  {cn}")
        sums[school].append(f"{tr_h}  {ascii_n}")

for school, (outdir, store) in SCHOOLS.items():
    pdir = os.path.join(outdir, "pages")
    spdir = os.path.join(store, "pages")
    if os.path.isdir(pdir):
        for fn in os.listdir(pdir):
            try_copy(os.path.join(pdir, fn), os.path.join(spdir, fn), do_fsync=False)
    try_copy(__file__, os.path.join(outdir, "gen_five_r35.py"))
    try_copy(__file__, os.path.join(store, "gen_five_r35.py"), do_fsync=False)
    if os.environ.get("ONLY"):
        continue
    txt = "\n".join(sums[school]) + "\n"
    write_bytes(os.path.join(outdir, "SHA256SUMS.txt"), txt.encode())
    write_bytes(os.path.join(store, "SHA256SUMS.txt"), txt.encode(), do_fsync=False)

print("done")
for row in page_info:
    print(row)
