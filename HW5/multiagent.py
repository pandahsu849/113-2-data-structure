import os
import json
import pandas as pd
import time
from flask_socketio import SocketIO
from dotenv import load_dotenv
from google.generativeai import configure, GenerativeModel
from snownlp import SnowNLP
from EMOwithSnow import generate_analysis

# ✅ 設定 Gemini Flash 模型
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
configure(api_key=api_key)
gemini_model = GenerativeModel("gemini-1.5-flash")

def generate_gemini_feedback(summary_data):
    customer_lines = [
        f"- {name} 的對話類型順序為：{' ➜ '.join(seq)}"
        for name, seq in summary_data["customers"].items()
    ]
    joined_summary = "\n".join(customer_lines)

    prompt = f"""
以下是幾位顧客與客服的對話分析結果：

{joined_summary}

整體情緒平均值為：{summary_data["avg_sentiment"]:.2f}

請根據以上資訊，提出具建設性的客服服務改進建議，
幫助客服團隊提升顧客滿意度與服務品質。
請使用中文，語氣親切、具體。
"""

    response = gemini_model.generate_content(prompt)
    return response.text.strip()

def run_multiagent_analysis(file_path, socketio: SocketIO, sid: str):
    try:
        socketio.emit("status", {"message": "🔍 開始讀取客服對話紀錄..."}, to=sid)
        df = pd.read_csv(file_path)
        user_id = os.path.splitext(os.path.basename(file_path))[0]

        if "who" not in df.columns or "text" not in df.columns:
            socketio.emit("status", {"message": "❌ 錯誤：CSV 必須包含 'who' 和 'text' 欄位！"}, to=sid)
            return

        time.sleep(1)
        socketio.emit("status", {"message": "🤖 分析情緒變化中..."}, to=sid)

        time.sleep(1)
        socketio.emit("status", {"message": "📊 對話類型分類中..."}, to=sid)

        # 執行分析（畫圖、分類、輸出 JSON）
        result_paths = generate_analysis(user_id, df)

        # 重新計算平均情緒值
        df["text"] = df["text"].fillna("").astype(str)
        df = df[df["text"].str.len() > 2].reset_index(drop=True)
        df["sentiment"] = df["text"].apply(lambda x: SnowNLP(x).sentiments)
        avg_sentiment = df["sentiment"].mean()

        # 讀取對話類型順序 JSON
        aspect_seq_path = result_paths["aspect_sequence_json"]
        if os.path.exists(aspect_seq_path):
            with open(aspect_seq_path, "r", encoding="utf-8") as f:
                customer_sequences = json.load(f)
        else:
            customer_sequences = {}

        summary_data = {
            "avg_sentiment": avg_sentiment,
            "customers": customer_sequences
        }

        print("🧠 傳給 Gemini 的摘要內容如下：")
        print(json.dumps(summary_data, indent=2, ensure_ascii=False))

        socketio.emit("status", {"message": "✨ Gemini 正在產生客服建議中..."}, to=sid)

        feedback = generate_gemini_feedback(summary_data)

        print("✅ Gemini 回覆內容如下：")
        print(feedback)

        socketio.emit("status", {"message": "✅ 分析完成，結果生成中..."}, to=sid)

        socketio.emit("result", {
            "moodtrend_img": result_paths["moodtrend_img"],
            "aspect_bar_img": result_paths["aspect_bar_img"],
            "aspect_sequence_json": result_paths["aspect_sequence_json"],
            "ai_feedback": feedback
        }, to=sid)

    except Exception as e:
        socketio.emit("status", {"message": f"❌ 發生錯誤：{str(e)}"}, to=sid)
