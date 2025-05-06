import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
import google.generativeai as genai
import pdfkit
from jinja2 import Template
from flask import Flask, request, render_template, send_file, Response
from werkzeug.utils import secure_filename

# 設定 wkhtmltopdf 路徑
WKHTMLTOPDF_PATH = "C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe"
config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

# 載入環境變數並設定 API 金鑰
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")
genai.configure(api_key=api_key)

# HTML 模板
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

# Flask 應用程式
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制上傳檔案大小為16MB

# 確保上傳資料夾存在
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def parse_markdown_table(markdown_text: str) -> pd.DataFrame:
    """
    從 Markdown 格式的表格文字提取資料，返回一個 pandas DataFrame。
    """
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
    """
    使用 jinja2 模板生成 HTML 內容。
    """
    template = Template(HTML_TEMPLATE)
    return template.render(table=df, text=text)

def generate_pdf(text: str = None, df: pd.DataFrame = None) -> str:
    """
    生成 PDF 檔案，使用 pdfkit 從 HTML 內容轉換。
    """
    print("開始生成 PDF")
    html_content = generate_html(text, df)
    pdf_filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    try:
        pdfkit.from_string(html_content, pdf_filename, configuration=config)
        print(f"PDF 生成完成，檔案：{pdf_filename}")
    except Exception as e:
        error_msg = f"PDF 生成失敗：{str(e)}"
        print(error_msg)
        return error_msg
    return pdf_filename

def process_input(csv_file, user_prompt):
    """
    處理輸入，生成分析結果和 PDF。
    """
    print("進入 process_input")
    model_name = "gemini-1.5-flash"
    try:
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        error_msg = f"無法初始化模型 {model_name}：{str(e)}"
        print(error_msg)
        return error_msg, None

    if csv_file is not None:
        print("讀取 CSV 檔案")
        try:
            df = pd.read_csv(csv_file)
            print(f"CSV 欄位：{df.columns.tolist()}")
        except Exception as e:
            error_msg = f"無法讀取 CSV 檔案：{str(e)}"
            print(error_msg)
            return error_msg, None

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
        
        # 嘗試解析 Markdown 表格
        df_result = parse_markdown_table(cumulative_response)
        if df_result is not None:
            print("成功解析 Markdown 表格")
            pdf_path = generate_pdf(df=df_result)
            return cumulative_response, pdf_path
        else:
            print("無法解析 Markdown 表格，生成純文字 PDF")
            pdf_path = generate_pdf(text=cumulative_response)
            return cumulative_response, pdf_path
    else:
        print("未上傳 CSV，處理純文字輸入")
        try:
            response = model.generate_content(user_prompt)
            response_text = response.text.strip()
        except Exception as e:
            error_msg = f"生成內容失敗：{str(e)}"
            print(error_msg)
            return error_msg, None
        
        # 嘗試解析 Markdown 表格
        df_result = parse_markdown_table(response_text)
        if df_result is not None:
            print("成功解析 Markdown 表格")
            pdf_path = generate_pdf(df=df_result)
        else:
            print("無法解析 Markdown 表格，生成純文字 PDF")
            pdf_path = generate_pdf(text=response_text)
        return response_text, pdf_path

default_prompt = """請根據以下資料進行分析，並提供完整的知識學習建議。請特別注意：
  1. 對該知識名詞提供清晰的定義與解釋；
  2. 延伸建議：根據該知識名詞，推薦可以進一步學習的相關知識或領域；
  3. 實際應用：說明該知識如何應用在現實生活中，並提供具體範例；
  4. 請搜尋外部網站，找出與該知識名詞相關的最新資訊或學習資源，並將搜尋結果整合進回覆中；
  5. 最後請生成 3-5 個簡單的基本觀念題目（選擇題或問答題），以確認使用者是否理解該知識。
請提供一份完整、易懂且具學習價值的回覆。"""

# Flask 路由
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user_prompt = request.form.get('user_prompt', default_prompt)
        csv_file = request.files.get('csv_file')
        
        if csv_file and csv_file.filename:
            filename = secure_filename(csv_file.filename)
            csv_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            csv_file.save(csv_path)
            response_text, pdf_path = process_input(csv_path, user_prompt)
            os.remove(csv_path)  # 清理上傳的檔案
        else:
            response_text, pdf_path = process_input(None, user_prompt)
        
        if pdf_path and os.path.exists(pdf_path):
            return render_template('result.html', response_text=response_text, pdf_path=pdf_path)
        else:
            return render_template('result.html', response_text=response_text, error=pdf_path)
    
    return render_template('index.html', default_prompt=default_prompt)

@app.route('/download/<path:filename>')
def download_file(filename):
    try:
        return send_file(filename, as_attachment=True)
    except Exception as e:
        return Response(f"檔案下載失敗：{str(e)}", status=500)

if __name__ == '__main__':
    app.run(debug=True)