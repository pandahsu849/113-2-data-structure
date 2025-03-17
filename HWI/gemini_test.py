import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
print(f"Gemini API key: {api_key}")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

try:
    response = model.generate_content("Hello Gemini!")
    print("成功回應：", response.text)
except Exception as e:
    print("Gemini API 錯誤訊息：", e)

