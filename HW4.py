import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
import google.generativeai as genai
import pdfkit
from jinja2 import Template
from playwright.sync_api import sync_playwright
import random
import requests  # For simulating file upload

# 設定環境變數
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")

# 檢查環境變數
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")
if not REDDIT_USERNAME or not REDDIT_PASSWORD:
    raise ValueError("Reddit credentials not found in environment variables")

# 設定 wkhtmltopdf 路徑
WKHTMLTOPDF_PATH = "C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe"
config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

# HTML 模板（從 getPDF2.py 保留）
HTML_TEMPLATE = """
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; }
        h2 { color: #333; text-align: center; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
        th { background-color: #f0f0f0; font-weight: bold; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .text-content { line-height: 1.6; white-space: pre-wrap; margin-top: 20px; }
    </style>
</head>
<body>
    <h2>知識學習報表</h2>
    {% if table is not none %}
    <table>
        <thead>
            <tr>
                {% for col in table.columns %}
                <th>{{ col }}</th>
                {% endfor %}
            </tr>
        </thead>
        <tbody>
            {% for row in table.values %}
            <tr>
                {% for cell in row %}
                <td>{{ cell }}</td>
                {% endfor %}
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="text-content">{{ text }}</div>
    {% endif %}
</body>
</html>
"""

# 初始化 Gemini API
genai.configure(api_key=GEMINI_API_KEY)

def parse_markdown_table(markdown_text: str) -> pd.DataFrame:
    """從 Markdown 表格解析資料"""
    lines = markdown_text.strip().splitlines()
    lines = [line.strip() for line in lines if line.strip()]
    table_lines = [line for line in lines if line.startswith("|")]
    if not table_lines or len(table_lines) < 3:
        return None
    headers = [h.strip() for h in table_lines[0].strip("|").split("|")]
    data = []
    for line in table_lines[2:]:
        row = [cell.strip() for cell in line.strip("|").split("|")]
        if len(row) == len(headers):
            data.append(row)
    return pd.DataFrame(data, columns=headers)

def generate_html(text: str = None, df: pd.DataFrame = None) -> str:
    """生成 HTML 內容"""
    template = Template(HTML_TEMPLATE)
    return template.render(table=df, text=text)

def generate_pdf(text: str = None, df: pd.DataFrame = None) -> str:
    """生成 PDF 檔案"""
    print("開始生成 PDF")
    html_content = generate_html(text, df)
    pdf_filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    try:
        pdfkit.from_string(html_content, pdf_filename, configuration=config)
        print(f"PDF 生成完成，檔案：{pdf_filename}")
    except Exception as e:
        error_msg = f"PDF 生成失敗：{str(e)}"
        print(error_msg)
        raise Exception(error_msg)
    return pdf_filename

def simulate_file_upload(pdf_path: str) -> str:
    """模擬將 PDF 上傳到文件分享服務，返回分享連結"""
    # 注意：這是模擬，實際應用需要使用真實的文件分享 API（如 Google Drive、Dropbox）
    print(f"模擬上傳 PDF：{pdf_path}")
    # 假設上傳成功，返回一個假連結
    return f"https://example.com/shared/{os.path.basename(pdf_path)}"

def process_csv_and_generate_report(csv_path: str, user_prompt: str) -> tuple:
    """處理 CSV 並生成報表"""
    model_name = "gemini-1.5-flash"
    try:
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        raise Exception(f"無法初始化模型 {model_name}：{str(e)}")

    print("讀取 CSV 檔案")
    try:
        df = pd.read_csv(csv_path)
        print(f"CSV 欄位：{df.columns.tolist()}")
    except Exception as e:
        raise Exception(f"無法讀取 CSV 檔案：{str(e)}")

    total_rows = df.shape[0]
    block_size = 30
    cumulative_response = ""

    for i in range(0, total_rows, block_size):
        block = df.iloc[i:i+block_size]
        block_csv = block.to_csv(index=False)
        prompt = (
            f"以下是 CSV 資料第 {i+1} 到 {min(i+block_size, total_rows)} 筆：\n"
            f"{block_csv}\n\n"
            f"請根據以下規則進行分析並產出報表（以 Markdown 表格格式輸出）：\n"
            f"1. 針對每個知識名詞，檢查其定義、延伸建議、實際應用、外部資源和觀念題目是否完整。\n"
            f"2. 如果任何欄位缺失或不完整，提供補充內容（例如詳細的定義、具體的應用案例等）。\n"
            f"3. 確保輸出為 Markdown 表格，包含所有原始欄位，並在適當欄位中新增補充內容。\n"
            f"4. 補充內容應清晰、具體，並與現有資料一致。\n"
            f"{user_prompt}"
        )
        print(f"處理區塊 {i//block_size+1}")
        try:
            response = model.generate_content(prompt)
            block_response = response.text.strip()
            cumulative_response += f"區塊 {i//block_size+1}:\n{block_response}\n\n"
        except Exception as e:
            error_msg = f"生成內容失敗（區塊 {i//block_size+1}）：{str(e)}"
            print(error_msg)
            cumulative_response += f"區塊 {i//block_size+1} 錯誤：{error_msg}\n\n"

    df_result = parse_markdown_table(cumulative_response)
    pdf_path = generate_pdf(df=df_result) if df_result is not None else generate_pdf(text=cumulative_response)
    return cumulative_response, pdf_path

def post_to_reddit(pdf_path: str, post_title: str, subreddit: str = "test"):
    """在 Reddit 上發文，包含 PDF 分享連結"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("啟動瀏覽器，前往 Reddit...")
        page.goto("https://www.reddit.com/")
        page.wait_for_timeout(random.randint(2000, 4000))

        # 點擊登入按鈕
        login_button = page.locator("a[href*='/login']")
        login_button.wait_for(state="visible", timeout=10000)
        login_button.click()
        print("已點擊登入按鈕")
        page.wait_for_timeout(random.randint(2000, 4000))

        # 填入帳號與密碼
        page.fill("input[name='username']", REDDIT_USERNAME)
        page.wait_for_timeout(random.randint(1000, 3000))
        page.fill("input[name='password']", REDDIT_PASSWORD)
        page.press("input[name='password']", "Enter")
        print("提交登入資訊")
        page.wait_for_timeout(random.randint(3000, 5000))

        print("登入成功！")

        # 前往指定子板塊
        page.goto(f"https://www.reddit.com/r/{subreddit}/submit")
        page.wait_for_timeout(random.randint(2000, 4000))

        # 上傳 PDF 並獲取分享連結
        share_link = simulate_file_upload(pdf_path)

        # 填寫標題和內容
        post_content = f"分享我的知識學習報表！下載 PDF 查看詳細內容：{share_link}"
        page.fill("input[placeholder='Title']", post_title)
        page.fill("textarea[name='text']", post_content)
        page.wait_for_timeout(random.randint(1000, 2000))

        # 提交發文
        submit_button = page.locator("button[type='submit']")
        submit_button.wait_for(state="visible", timeout=10000)
        submit_button.click()
        print("已提交發文")
        page.wait_for_timeout(random.randint(3000, 5000))

        print("發文成功！")
        input("瀏覽器保持開啟，按 Enter 關閉...")
        browser.close()
        print("瀏覽器已關閉")

def main(csv_path: str, user_prompt: str, post_title: str, subreddit: str = "test"):
    """主函數：生成 PDF 並發文到 Reddit"""
    try:
        # 生成報表和 PDF
        response_text, pdf_path = process_csv_and_generate_report(csv_path, user_prompt)
        print(f"報表生成完成：{response_text[:100]}...")

        # 發文到 Reddit
        post_to_reddit(pdf_path, post_title, subreddit)
    except Exception as e:
        print(f"執行失敗：{str(e)}")

if __name__ == "__main__":
    # 示例參數
    sample_csv = "knowledge_learning_output.csv"  # 替換為實際 CSV 路徑
    sample_prompt = """請根據資料生成知識學習報表，提供清晰定義、延伸建議和實際應用。"""
    sample_title = "我的知識學習報表分享"
    sample_subreddit = "test"  # 測試用子板塊，實際使用時替換

    main(sample_csv, sample_prompt, sample_title, sample_subreddit)