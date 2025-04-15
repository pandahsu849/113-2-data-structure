import os
import asyncio
import pandas as pd

from dotenv import load_dotenv

# 根據你的專案結構調整下列 import
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.agents.web_surfer import MultimodalWebSurfer

load_dotenv()

async def process_chunk(chunk, start_idx, total_records, model_client, termination_condition):
    chunk_data = chunk.to_dict(orient='records')
    prompt = (
        f"目前正在處理第 {start_idx} 至 {start_idx + len(chunk) - 1} 筆資料（共 {total_records} 筆）。\n"
        f"以下為該批次學生學習行為紀錄:\n{chunk_data}\n\n"
        "請根據以上資料進行分析，提供學生的學習行為總結與建議，特別注意以下事項：\n"
        "  1. 分析學生學習活動類型（如自習、上課、考試、課外活動）及其表現；\n"
        "  2. 請 MultimodalWebSurfer 搜尋外部網站，找出有效的學習方法或活動建議，並將資訊整合進回覆中；\n"
        "  3. 最後請提供具體的改善建議與相關參考資訊。\n"
        "請各代理人協同合作，提供一份完整且具參考價值的學習行為分析與建議。"
    )

    local_data_agent = AssistantAgent("data_agent", model_client)
    local_web_surfer = MultimodalWebSurfer("web_surfer", model_client)
    local_assistant = AssistantAgent("assistant", model_client)
    local_user_proxy = UserProxyAgent("user_proxy")
    local_team = RoundRobinGroupChat(
        [local_data_agent, local_web_surfer, local_assistant, local_user_proxy],
        termination_condition=termination_condition
    )

    messages = []
    async for event in local_team.run_stream(task=prompt):
        if isinstance(event, TextMessage):
            print(f"[{event.source}] => {event.content}\n")
            messages.append({
                "batch_start": start_idx,
                "batch_end": start_idx + len(chunk) - 1,
                "source": event.source,
                "content": event.content,
                "type": event.type,
                "prompt_tokens": event.models_usage.prompt_tokens if event.models_usage else None,
                "completion_tokens": event.models_usage.completion_tokens if event.models_usage else None
            })
    return messages

async def main():
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        print("請檢查 .env 檔案中的 GEMINI_API_KEY。")
        return

    model_client = OpenAIChatCompletionClient(
        model="gemini-2.0-flash",
        api_key=gemini_api_key.encode('utf-8').decode('ascii', 'ignore'),
    )

    termination_condition = TextMentionTermination("exit")

    csv_file_path = "student_learning_records.csv"  # 已抽換的資料檔案名稱
    chunk_size = 1000
    chunks = [chunk.fillna("") for chunk in pd.read_csv(csv_file_path, chunksize=chunk_size, encoding='utf-8')]
    total_records = sum(chunk.shape[0] for chunk in chunks)

    tasks = list(map(
        lambda idx_chunk: process_chunk(
            idx_chunk[1],
            idx_chunk[0] * chunk_size,
            total_records,
            model_client,
            termination_condition
        ),
        enumerate(chunks)
    ))

    results = await asyncio.gather(*tasks)
    all_messages = [msg for batch in results for msg in batch]

    df_log = pd.DataFrame(all_messages)
    output_file = "student_activity_log.csv"
    df_log.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"已將所有對話紀錄輸出為 {output_file}")

if __name__ == '__main__':
    asyncio.run(main())
