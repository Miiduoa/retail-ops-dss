# Retail Ops DSS｜零售營運決策支援原型

[![verify](https://github.com/Miiduoa/retail-ops-dss/actions/workflows/verify.yml/badge.svg)](https://github.com/Miiduoa/retail-ops-dss/actions/workflows/verify.yml)

**預測＋可解釋儀表板** — 個人作品（非課內專題題目）｜MIT License

English: A lightweight retail operations decision-support prototype — daily sales forecasting, feature importance, and rule-based replenishment / staffing suggestions in Streamlit.

作者：顧晉瑋（靜宜大學資訊管理學系）｜Contact: demohan513@gmail.com

---

## 問題

連鎖零售門市在補貨與排班上常依賴經驗法則，面對促銷、假日與品類差異時，容易出現**缺貨或過剩**、**尖峰人力不足**。本專案建構可 Demo 的決策支援系統（DSS）原型：以日銷量預測為核心，搭配可解釋資訊與規則型建議，協助管理者快速掌握「會賣多少、為什麼、該怎麼做」。

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
4. **評估**：時間切分最後 60 日；**MAE**、**MAPE**  
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

瀏覽器開啟終端機提示的本機網址（預設 `http://localhost:8501`）。

### 快速驗證（非互動）

```bash
python generate_data.py
python scripts_verify.py
# 或
python -c "from src.data_loader import load_sales; from src.models import get_or_train; df=load_sales(); fc=get_or_train(df); print(fc.eval_results_)"
```

## 介面功能

| 頁面 | 內容 |
|------|------|
| 資料概覽 | 資料規模、全通路趨勢、品類結構 |
| 預測與決策建議 | 選門市／品類、未來 N 日預測、補貨／人力建議、特徵重要性、類似歷史日 |
| 模型評估對照 | MA-7 vs RandomForest 的 MAE／MAPE |

## 目錄結構

```text
retail-ops-dss/
├── app.py                 # Streamlit 入口
├── generate_data.py       # 合成資料一鍵產生
├── scripts_verify.py      # 非互動驗證
├── requirements.txt
├── LICENSE                # MIT
├── README.md
├── data/                  # CSV（generate 後產生）
├── models/                # 模型快取（.gitkeep；*.joblib 不進版控）
├── src/
│   ├── data_loader.py
│   ├── features.py
│   ├── models.py
│   ├── explain.py
│   └── recommend.py
└── docs/
    ├── 備審專題說明.md
    ├── 架構說明.md
    └── screenshots/
```

## 限制（誠實）

- 資料為合成情境，未涵蓋實際供應鏈延遲、競品、天候等  
- 多步預測採遞迴方式，誤差可能隨 horizon 累積  
- 補貨／人力建議為規則引擎示意，非 OR 最佳化  
- 未串接真實 POS／ERP，僅供學習與展示  

## 授權

[MIT License](LICENSE) — Copyright (c) 2026 顧晉瑋
