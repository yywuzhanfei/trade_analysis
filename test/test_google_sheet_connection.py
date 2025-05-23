import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === 配置 ===
GOOGLE_CREDENTIALS_FILE = 'ib-goog-sheet-credentials.json'  # 替换为你的 JSON 文件名
SHEET_NAME = 'IB order history'  # 替换为你的 Google Sheet 名称

# === 建立连接 ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)

# === 打开 Sheet ===
try:
    sheet = client.open(SHEET_NAME).sheet1
except gspread.SpreadsheetNotFound:
    print(f"❌ 找不到名为 '{SHEET_NAME}' 的 Google Sheet，请确认名称拼写正确")
    exit()

# === 写入测试行 ===
test_data = ['✅ 连接成功', '测试行', '时间戳', '来自脚本']
sheet.append_row(test_data)

print("✅ 成功写入测试数据到 Google Sheet")
