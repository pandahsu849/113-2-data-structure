import os
import sys
import time
import json
import re
import pandas as pd
from io import StringIO
from dotenv import load_dotenv
import google.generativeai as genai

# ---------- 設定與初始化 ----------

load_dotenv()
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("請設定環境變數 GEMINI_API_KEY")
genai.configure(api_key=gemini_api_key)

ITEMS = [
    "內向 (I)", "外向 (E)", "判斷 (J)", "感知 (P)",
    "實感 (S)", "直覺 (N)", "思考 (T)", "情感 (F)",
]

# ---------- 工具函式 ----------

def parse_response(response_text):
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"): lines = lines[1:]
        if lines and lines[-1].strip() == "```": lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        result = json.loads(cleaned)
        for item in ITEMS:
            if item not in result:
                result[item] = ""
        return result
    except Exception:
        fallback_result = {}
        for item in ITEMS:
            pattern = re.escape(item) + r"\s*[:：]\s*1"
            fallback_result[item] = "1" if re.search(pattern, cleaned) else ""
        return fallback_result

def select_dialogue_column(df: pd.DataFrame) -> str:
    return "Text"

def process_batch_dialogue(dialogues: list, delimiter="-----"):
    prompt = (
        "你是一位精神科醫師兼精神分析師，請根據以下編碼規則評估每一句對話所表現出的 MBTI 類型傾向：\n"
        + "\n".join(ITEMS) +
        "\n請針對每筆逐字稿回傳一個 JSON 格式結果，每個項目若有表現請標記為 \"1\"，否則為空字串。請以下列分隔線區分每筆結果：\n"
        f"{delimiter}\n"
        "格式範例如下：\n"
        "```json\n{\n  \"內向 (I)\": \"1\",\n  \"外向 (E)\": \"\",\n  ...\n}\n```\n"
    )
    batch_text = f"\n{delimiter}\n".join(dialogues)
    full_prompt = prompt + "\n\n" + batch_text

    print(f"\n📤 傳送 Prompt（長度 {len(full_prompt)} 字元）...\n")

    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        response = model.generate_content(full_prompt, generation_config={"timeout": 30})
        print("🔎 Gemini 回傳內容：\n", response.text)

        # 將 raw 回傳寫入檔案供除錯
        with open("trip_raw_output.txt", "a", encoding="utf-8") as f:
            f.write("\n=== 新一批 ===\n")
            f.write(response.text)
            f.write("\n")

    except Exception as e:
        print(f"❌ Gemini API 呼叫失敗：{e}")
        return [{item: "" for item in ITEMS} for _ in dialogues], ["Gemini 呼叫失敗"] * len(dialogues)
    
    print("批次 API 回傳內容：", response.text)
    parts = response.text.split(delimiter)
    results = []
    raw_parts = []
    for part in parts:
        part = part.strip()
        if part:
            results.append(parse_response(part))
            raw_parts.append(part)
    while len(results) < len(dialogues):
        results.append({item: "" for item in ITEMS})
        raw_parts.append("")
    return results[:len(dialogues)], raw_parts[:len(dialogues)]

# ---------- 主流程 ----------

def main():
    print("🔐 載入 API Key 成功")

    if len(sys.argv) < 2:
        print("📎 用法：python DRai.py trip_utf8.csv")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_csv = "trip_result.csv"

    try:
        with open(input_csv, "r", encoding="utf-8-sig", errors="ignore") as f:
            content = f.read()
        df = pd.read_csv(StringIO(content), on_bad_lines="skip")
    except Exception as e:
        print(f"❌ 無法讀取 CSV：{e}")
        sys.exit(1)

    print(f"✅ 成功讀入 {input_csv}，共 {len(df)} 筆資料")

    dialogue_col = select_dialogue_column(df)
    print(f"🗣 使用欄位作為逐字稿：{dialogue_col}")

    if os.path.exists(output_csv):
        os.remove(output_csv)

    batch_size = 3
    total = len(df)
    for start_idx in range(0, total, batch_size):
        end_idx = min(start_idx + batch_size, total)
        batch = df.iloc[start_idx:end_idx]
        dialogues = batch[dialogue_col].astype(str).str.strip().tolist()

        print(f"\n🔄 處理第 {start_idx + 1} ~ {end_idx} 筆對話")
        batch_results, raw_parts = process_batch_dialogue(dialogues)

        batch_df = batch.copy()
        for item in ITEMS:
            batch_df[item] = [res.get(item, "") for res in batch_results]

        batch_df["Gemini原始回應"] = raw_parts

        batch_df.to_csv(
            output_csv,
            index=False,
            header=(start_idx == 0),
            mode="a",
            encoding="utf-8-sig"
        )

        for sec in range(3, 0, -1):
            print(f"⏳ 等待 {sec} 秒再處理下一批...", end="\r")
            time.sleep(1)

    print("\n🎉 全部處理完成！結果已儲存至：", output_csv)

if __name__ == "__main__":
    main()
