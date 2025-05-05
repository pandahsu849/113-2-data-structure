# EMOwithSnow.py（客服對話分析版）

import os
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import json
from snownlp import SnowNLP
import re
from collections import Counter

matplotlib.use('Agg')
matplotlib.rc('font', family='Microsoft JhengHei')

# 🔐 確保 static 永遠指向 ./static（專案資料夾下）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(BASE_DIR, "static")
os.makedirs(output_dir, exist_ok=True)

# 🔍 客服對話分類關鍵字
keyword_map = {
    "抱怨": ["不好", "失望", "生氣", "爛", "壞掉", "差", "投訴", "抱怨", "不滿意"],
    "詢問": ["請問", "想知道", "怎麼", "可以嗎", "如何", "問一下", "什麼時候"],
    "感謝": ["謝謝", "感謝", "辛苦了", "讚", "很好", "滿意"],
    "建議": ["建議", "希望", "覺得可以", "應該", "如果能", "下次可以"]
}

def classify_aspects(text):
    found = set()
    for aspect, keywords in keyword_map.items():
        for kw in keywords:
            if re.search(kw, text, flags=re.IGNORECASE):
                found.add(aspect)
    return list(found)

def generate_analysis(user_id, df):
    moodtrend_path = os.path.join(output_dir, f"moodtrend_{user_id}.png")
    aspect_bar_path = os.path.join(output_dir, f"aspect_bar_{user_id}.png")
    sequence_json_path = os.path.join(output_dir, f"aspect_sequence_{user_id}.json")

    # ✅ 清洗資料
    df["text"] = df["text"].fillna("").astype(str)
    df = df[df["text"].str.len() > 2].reset_index(drop=True)

    if df.empty or "text" not in df.columns or "who" not in df.columns:
        raise ValueError("資料內容為空，或缺少 'text' 或 'who' 欄位，請確認格式。")

    # 情緒分析與分類
    df["sentiment"] = df["text"].apply(lambda x: SnowNLP(x).sentiments)
    df["aspects"] = df["text"].apply(classify_aspects)

    # 📈 畫情緒變化圖
    try:
        if not df["sentiment"].empty and df["sentiment"].nunique() > 1:
            plt.figure(figsize=(10, 4))
            plt.plot(df.index, df["sentiment"], marker="o")
            plt.title("客戶情緒變化趨勢")
            plt.xlabel("對話順序")
            plt.ylabel("情緒值 (0=負面, 1=正面)")
            plt.tight_layout()
            plt.savefig(moodtrend_path)
            plt.close()
    except Exception as e:
        print(f"[⚠️ 畫情緒圖失敗] {e}")

    # 📊 畫客服對話類型比例圖
    all_aspects = [aspect for aspects in df["aspects"] for aspect in aspects]
    aspect_counts = Counter(all_aspects)

    try:
        if aspect_counts:
            plt.figure(figsize=(8, 5))
            plt.bar(aspect_counts.keys(), aspect_counts.values())
            plt.title("客服對話類型分佈")
            plt.ylabel("出現次數")
            plt.xticks(rotation=30)
            plt.tight_layout()
            plt.savefig(aspect_bar_path)
            plt.close()
    except Exception as e:
        print(f"[⚠️ 畫類型圖失敗] {e}")

    # 📝 每位使用者對話類型順序
    customer_sequences = {}
    for customer, group in df.groupby("who"):
        sequence = []
        prev = None
        for text in group["text"]:
            for aspect in classify_aspects(text):
                if aspect != prev:
                    sequence.append(aspect)
                    prev = aspect
        customer_sequences[customer] = sequence

    with open(sequence_json_path, "w", encoding="utf-8") as f:
        json.dump(customer_sequences, f, ensure_ascii=False, indent=2)

    # ✅ 確認檔案
    print("🔍 實際儲存檔案：")
    print("情緒圖：", moodtrend_path, "✅" if os.path.exists(moodtrend_path) else "❌")
    print("類型圖：", aspect_bar_path, "✅" if os.path.exists(aspect_bar_path) else "❌")
    print("類型順序 JSON：", sequence_json_path, "✅" if os.path.exists(sequence_json_path) else "❌")

    return {
        "moodtrend_img": os.path.relpath(moodtrend_path, BASE_DIR),
        "aspect_bar_img": os.path.relpath(aspect_bar_path, BASE_DIR),
        "aspect_sequence_json": os.path.relpath(sequence_json_path, BASE_DIR)
    }
