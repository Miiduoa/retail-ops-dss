# Retail Ops DSS｜零售營運決策支援原型

[![verify](https://github.com/Miiduoa/retail-ops-dss/actions/workflows/verify.yml/badge.svg)](https://github.com/Miiduoa/retail-ops-dss/actions/workflows/verify.yml)

**預測＋可解釋儀表板** — 個人作品（非課內專題題目）｜MIT License

English: A lightweight retail operations decision-support prototype — daily sales forecasting, feature importance, and rule-based replenishment / staffing suggestions in Streamlit.

作者：顧晉瑋（靜宜大學資訊管理學系）｜Contact: demohan513@gmail.com

## 30 秒 Demo 路徑

如果只看一輪，建議依這個順序：

1. **預測頁**：選門市與品類，看 MA-7 baseline 與 Random Forest 預測差異。
2. **操作補貨**：用 `operator.s01` 提出補貨，觀察 store scope 與敏感操作條件。
3. **切換帳號**：改用 `viewer.s02` 嘗試寫入，確認預設拒絕。
4. **稽核頁**：用 `admin` 查看成功／拒絕事件、request id 與匯出紀錄。

| 審查重點 | 直接看 |
|---|---|
| 模型方法與時間切分 | 本 README 的「方法」 |
| 實際介面 | [docs/screenshots](docs/screenshots/) |
| 存取控制 | `src/access/` |
| UI 權限與風險提示 | `src/ui_security.py` |
| 自動驗證 | `scripts_verify.py`、`tests/test_access_control.py` |

這個專案的價值不在「Random Forest 比 baseline 高多少」這一個數字，而是**預測結果如何進入一個有權限、資料範圍與稽核邊界的營運流程**。

---

## 問題

連鎖零售門市在補貨與排班上常依賴經驗法則，面對促銷、假日與品類差異時，容易出現**缺貨或過剩**、**尖峰人力不足**。本專案建構可 Demo 的決策支援系統（DSS）原型：以日銷量預測為核心，搭配可解釋資訊與規則型建議，協助管理者快速掌握「會賣多少、為什麼、該怎麼做」。

敏感營運動作（庫存調整、補貨核准、設定與帳號變更）另以**應用層授權與稽核**關進可課責流程：不是任何人打開儀表板就能改數、也不是「有登入就等於什麼都能做」。

## 存取控制與稽核設計

本原型在預測與決策支援之外，加入應用層的存取控制與稽核機制：**細粒度授權、可追查的操作紀錄、資料範圍隔離，以及將存取風險帶入 DSS 操作流程**。目前實作以 Streamlit session + SQLite 為主，定位是可重現的系統原型，不等同企業級身分平台、網路隔離或端點防護產品，也未進行滲透測試或漏洞掃描。

| 設計面向 | 本原型實際做法 | 實作邊界 |
|----------|-------------------|----------------|
| 最小權限／細粒度授權 | 授權看「資源＋動作」（如 `inventory.write`、`reorder.approve`、`settings.admin`），**未列即預設拒絕**；敏感操作要求較高信任條件（近期再驗證，或僅管理者工作階段） | 沒有裝置憑證、網路微隔離、持續裝置健康評分 |
| 操作稽核可觀測 | 追加寫入、不可 UPDATE/DELETE；可篩選、可匯出 CSV。欄位含 actor、action、resource、outcome、timestamp、request_id／correlation_id | 不是 SIEM／SOC 產品，也不是異常偵測專題 |
| 資料範圍（store scope） | 同一 `operator` 角色仍只能看／改被指派門市；跨店在政策層拒絕並寫稽核 | 合成資料上的邏輯隔離，非正式資料庫 RLS 產品 |
| 決策支援 × 存取風險 | 補貨／庫存等動作標示高影響、非營業時間、跨店（相對主店），提示與稽核同一套旗標 | 可解釋的營運規則，不是 ML 風險分數或威脅情報 |

核心設計：預測建議仍要經過「使用者是否具有該動作權限、是否能存取指定門市、操作是否屬於較高風險，以及事後能否追查成功或拒絕紀錄」才進入營運流程。

## 截圖

| 資料概覽 | 預測與建議 |
|:---:|:---:|
| ![overview](docs/screenshots/04_overview_trend.png) | ![forecast](docs/screenshots/01_forecast.png) |
| **特徵重要性** | **模型評估** |
| ![importance](docs/screenshots/02_feature_importance.png) | ![eval](docs/screenshots/03_eval_compare.png) |

> 若截圖路徑在你的 clone 中顯示為破圖，請確認 `docs/screenshots/` 已一併 clone；亦可自行執行 App 後重新截圖替換。

## 資料

| 項目 | 說明 |
|------|------|
| 類型 | 可重現之**合成**零售日銷量（4 門市 × 4 品類 × 約 730 日） |
| 產生 | `python generate_data.py`（固定 `SEED=42`） |
| 輸出 | `data/retail_daily_sales.csv`（repo 已附一份預產樣本，可重跑覆蓋） |
| 授權 | 專案內合成，無第三方版權限制 |

## 方法（簡述）

1. **特徵**：lag 1/7/14、滾動均值／標準差、星期／週末／假日、促銷、單價、月份  
2. **Baseline**：7 日移動平均（MA-7）  
3. **進階**：`RandomForestRegressor`（特徵重要性可解釋）  
4. **評估**：最後 60 日 chronological hold-out；採 rolling one-step-ahead，僅使用預測日前已觀測歷史；缺值填補統計只由訓練區間估計；指標為 **MAE**、**MAPE**  
5. **決策**：依預測產生補貨量與人力工時之**規則型文字建議**  
6. **解釋**：全域特徵重要性＋「類似歷史日」對照  

訓練結果快取於 `models/rf_bundle.joblib`（首次載入 App 時自動訓練；已列入 `.gitignore`）。

## 如何執行

```bash
git clone https://github.com/Miiduoa/retail-ops-dss.git
cd retail-ops-dss

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python generate_data.py            # 產生／覆寫合成資料
streamlit run app.py
```

瀏覽器開啟終端機提示的本機網址（預設 `http://localhost:8501`）。首次啟動會種子合成帳號與空的稽核庫（`data/ops_control.db`，不進版控）。

### Demo 帳號（合成，非正式憑證）

| 帳號 | 密碼 | 角色 | 資料範圍 | 適合演示 |
|------|------|------|----------|----------|
| `operator.s01` | `demo-op-s01` | 門市營運 | 僅 S01 台北信義店 | 單店隔離、補貨／庫存 |
| `operator.north` | `demo-op-north` | 門市營運 | S01、S04（北區） | 同角色、不同範圍；對 S04 核准會標「跨店」 |
| `operator.s03` | `demo-op-s03` | 門市營運 | 僅 S03 高雄夢時代店 | 與 S01 對照，互不可見 |
| `viewer.s02` | `demo-view-s02` | 檢視者 | 僅 S02 台中逢甲店 | 預設拒絕寫入／核准 |
| `admin` | `demo-admin-2026` | 系統管理者 | 全門市（`*`） | 稽核儀表、匯出、帳號與設定 |

側欄可快速填入帳號。高影響數量或政策設定會要求**再輸入密碼**（預設 5 分鐘內有效）。側欄「Demo：模擬非營業時間」只為讓面試不必等到晚上也能看到風險旗標。

### Demo 操作路徑

1. `streamlit run app.py`，用 `operator.s01` 登入 → 預測頁只能選信義店 → 提出或核准補貨，看「存取風險」。
2. 勾選「模擬非營業時間」再操作一次；必要時用同一密碼再驗證。換 `operator.s03` 確認看不到信義店。
3. 用 `admin` 開「操作稽核」：看近 24h 拒絕與敏感成功、篩選、匯出 CSV。再用 `viewer.s02` 嘗試核准，應被拒絕並入稽核。

### 快速驗證（非互動）

```bash
python generate_data.py
python scripts_verify.py
# 或
python -c "from src.data_loader import load_sales; from src.models import get_or_train; df=load_sales(); fc=get_or_train(df); print(fc.eval_results_)"
```

## 介面功能

| 頁面 | 內容 | 誰看得到 |
|------|------|----------|
| 資料概覽 | 資料規模、可見範圍趨勢、品類結構 | 有 `dashboard.read` 且僅自己的門市列 |
| 預測與決策建議 | 選門市／品類、未來 N 日預測、補貨／人力建議、**存取風險**、提出／核准補貨 | 門市清單已過濾；寫入另要 `reorder.*` |
| 庫存與補貨作業 | 庫存調整、補貨單核准／駁回 | 敏感動作可要求再驗證 |
| 模型評估對照 | MA-7 vs RandomForest 的 MAE／MAPE | `eval.read` |
| 操作稽核 | 篩選、失敗授權、敏感成功、匯出 CSV | `audit.read`／`audit.export`（管理者） |
| 帳號與設定 | 角色、門市範圍、高影響門檻、營業時段 | `user.admin`／`settings.admin`（僅管理者工作階段） |

## 目錄結構

```text
retail-ops-dss/
├── app.py                 # Streamlit 入口
├── generate_data.py       # 合成資料一鍵產生
├── scripts_verify.py      # 非互動驗證（含授權／稽核測試）
├── requirements.txt
├── LICENSE                # MIT
├── README.md
├── data/                  # CSV；ops_control.db 於本機種子
├── models/                # 模型快取（.gitkeep；*.joblib 不進版控）
├── src/
│   ├── data_loader.py
│   ├── features.py
│   ├── models.py
│   ├── explain.py
│   ├── recommend.py
│   ├── ui_security.py     # 登入、風險、作業／稽核／設定頁
│   └── access/            # 政策引擎、稽核、種子帳號
├── tests/
│   └── test_access_control.py
└── docs/
    ├── 備審專題說明.md
    ├── 架構說明.md
    └── screenshots/
```

## 限制

- 資料為合成情境，未涵蓋實際供應鏈延遲、競品、天候等  
- 多步預測採遞迴方式，誤差可能隨 horizon 累積  
- 補貨／人力建議為規則引擎示意，非 OR 最佳化  
- 未串接真實 POS／ERP，僅供學習與展示  
- 授權與稽核是**應用層 Demo**（本機 SQLite、合成密碼雜湊、Streamlit 工作階段），不能當成已上線的零信任或資安認證證據  
- 不含滲透測試、攻擊手法、漏洞利用或網路攻擊防護產品功能  

## 授權

[MIT License](LICENSE) — Copyright (c) 2026 顧晉瑋
