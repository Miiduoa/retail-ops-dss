#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速驗證：資料、訓練、預測、app import。"""
from src.data_loader import load_sales
from src.models import get_or_train, eval_to_frame

def main():
    df = load_sales()
    assert len(df) > 1000, "資料列數過少"
    fc = get_or_train(df, force_retrain=False)
    assert fc.trained_
    assert len(fc.eval_results_) >= 2
    pred = fc.forecast("S01", "C01", horizon=5)
    assert len(pred) == 5
    import app  # noqa: F401
    print("VERIFY_OK")
    print(eval_to_frame(fc.eval_results_).to_string(index=False))

if __name__ == "__main__":
    main()
