import os
import json
import time
import pandas as pd
import sys
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError  # type: ignore

# 載入 .env 中的 GEMINI_API_KEY
load_dotenv()

# HW2
ITEMS = [
    "定義與解釋",
    "延伸建議",
    "實際應用",
    "外部資源",
    "觀念題目"
]

def parse_response(response_text):
    """
    嘗試解析 Gemini API 回傳的 JSON 格式結果。
    如果回傳內容被 markdown 的反引號包圍，則先移除這些標記。
    若解析失敗，則回傳所有項目皆為空的字典。
    """
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    
    try:
        result = json.loads(cleaned)
        for item in ITEMS:
            if item not in result:
                result[item] = "" if item != "觀念題目" else []
        return result
    except Exception as e:
        print(f"解析 JSON 失敗：{e}")
        print("原始回傳內容：", response_text)
        return {item: "" if item != "觀念題目" else [] for item in ITEMS}
#HW2
def process_batch_dialogue(client, dialogues: list, delimiter="-----"):
    """
    將多筆知識名詞合併成一個批次請求。
    提示中要求模型對每筆知識名詞進行分析並提供完整的學習建議。
    """
    prompt = (
        f"目前正在處理 {len(dialogues)} 筆知識名詞資料。\n"
        f"以下為該批次知識名詞資料:\n{dialogues}\n\n"
        "請根據以上知識名詞資料進行分析，並提供完整的學習建議。請特別注意以下要求：\n"
        "  1. 對該知識名詞提供清晰的定義與解釋；\n"
        "  2. 延伸建議：根據該知識名詞，推薦可以進一步學習的相關知識或領域；\n"
        "  3. 實際應用：說明該知識如何應用在現實生活中，並提供具體範例；\n"
        "  4. 搜尋外部網站，找出與該知識名詞相關的最新資訊或學習資源，並將搜尋結果整合進回覆中；\n"
        "  5. 最後請生成 3-5 個簡單的基本觀念題目（選擇題或問答題），以確認使用者是否理解該知識。\n"
        "請對每筆知識名詞產生 JSON 格式回覆，並在各筆結果間用下列分隔線隔開：\n"
        f"{delimiter}\n"
        "例如：\n"
        "```json\n"
        "{\n  \"定義與解釋\": \"...\",\n  \"延伸建議\": \"...\",\n  \"實際應用\": \"...\",\n  \"外部資源\": \"...\",\n  \"觀念題目\": [\"題目1\", \"題目2\", \"題目3\"]\n}\n"
        f"{delimiter}\n"
        "{{...}}\n```"
    )
    batch_text = f"\n{delimiter}\n".join(dialogues)
    content = prompt + "\n\n" + batch_text

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=content
        )
    except ServerError as e:
        print(f"API 呼叫失敗：{e}")
        return [{item: "" if item != "觀念題目" else [] for item in ITEMS} for _ in dialogues]
    
    print("批次 API 回傳內容：", response.text)
    parts = response.text.split(delimiter)
    results = []
    for part in parts:
        part = part.strip()
        if part:
            results.append(parse_response(part))
    if len(results) > len(dialogues):
        results = results[:len(dialogues)]
    elif len(results) < len(dialogues):
        results.extend([{item: "" if item != "觀念題目" else [] for item in ITEMS}] * (len(dialogues) - len(results)))
    return results

def main():
    if len(sys.argv) < 2:
        print("Usage: python DRai.py <path_to_csv>")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_csv = "knowledge_learning_output.csv"  # 修改輸出檔名以反映內容
    if os.path.exists(output_csv):
        os.remove(output_csv)
    
    df = pd.read_csv(input_csv)
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("請設定環境變數 GEMINI_API_KEY")
    client = genai.Client(api_key=gemini_api_key)
    
    # 明確指定使用 "knowledge_term" 欄位
    dialogue_col = "knowledge_term"
    print(f"使用欄位作為知識名詞：{dialogue_col}")
    
    batch_size = 10
    total = len(df)
    for start_idx in range(0, total, batch_size):
        end_idx = min(start_idx + batch_size, total)
        batch = df.iloc[start_idx:end_idx]
        dialogues = batch[dialogue_col].tolist()
        dialogues = [str(d).strip() for d in dialogues]
        batch_results = process_batch_dialogue(client, dialogues)
        batch_df = batch.copy()
        for item in ITEMS:
            batch_df[item] = [res.get(item, "" if item != "觀念題目" else []) for res in batch_results]
        if start_idx == 0:
            batch_df.to_csv(output_csv, index=False, encoding="utf-8-sig")
        else:
            batch_df.to_csv(output_csv, mode='a', index=False, header=False, encoding="utf-8-sig")
        print(f"已處理 {end_idx} 筆 / {total}")
        time.sleep(1)
    
    print("全部處理完成。最終結果已寫入：", output_csv)

if __name__ == "__main__":
    main()
