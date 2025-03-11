import asyncio
import requests
from bs4 import BeautifulSoup
import schedule
import time
from telegram import Bot
from datetime import datetime, timedelta
import os


# Cấu hình
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CH_ID"]
EVN_URL = 'https://www.cskh.evnspc.vn/TraCuu/GetThongTinLichNgungGiamMaKhachHang'
FILTER_KEYWORD = 'phú kiết'  # Từ khóa cần lọc, không phân biệt hoa thường

# Khởi tạo bot
bot = Bot(token=TELEGRAM_TOKEN)


def get_evn_data():
    # Lấy ngày hiện tại và ngày sau 7 ngày
    current_date = datetime.now()

    params = {
        'madvi': 'PB0808',
        'tuNgay': current_date.strftime('%d-%m-%Y'),
        'denNgay': (current_date + timedelta(days=7)).strftime('%d-%m-%Y'),
        'ChucNang': 'MaDonVi'
    }

    try:
        response = requests.get(EVN_URL, params=params)
        if response.status_code == 200:
            return response.text
        else:
            return f"Lỗi khi truy cập: {response.status_code}"
    except Exception as e:
        return f"Lỗi: {str(e)}"


def parse_html_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    # Tìm bảng dữ liệu
    table = soup.find('table')
    if not table:
        return "Không tìm thấy dữ liệu lịch cắt điện"

    # Lấy tất cả các hàng dữ liệu (bỏ qua hàng tiêu đề)
    rows = table.find_all('tr')[1:]

    # Khởi tạo danh sách để lưu dữ liệu
    power_outages = []

    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 4:
            location = cells[2].text.strip()
            # Chỉ thêm vào danh sách nếu vị trí chứa từ khóa cần lọc (không phân biệt hoa thường)
            if FILTER_KEYWORD.lower() in location.lower():
                outage = {
                    'start_time': cells[0].text.strip(),
                    'end_time': cells[1].text.strip(),
                    'location': location,
                    'reason': cells[3].text.strip()
                }
                power_outages.append(outage)

    return power_outages


def format_message(power_outages):
    if not power_outages or isinstance(power_outages, str):
        return "Không có lịch cắt điện nào ảnh hưởng đến khu vực Phú Kiết" if not power_outages else power_outages

    # Sắp xếp lịch cắt điện theo thời gian bắt đầu
    try:
        power_outages.sort(key=lambda x: datetime.strptime(x['start_time'], "%d/%m/%Y %H:%M:%S"))
    except:
        # Nếu không thể sắp xếp, bỏ qua
        pass

    message = "📢 THÔNG BÁO LỊCH NGỪNG/GIẢM CUNG CẤP ĐIỆN\n\n"

    for i, outage in enumerate(power_outages, 1):
        message += f"{i}. Thời gian:\n"
        message += f"   • Bắt đầu: {outage['start_time']}\n"
        message += f"   • Kết thúc: {outage['end_time']}\n\n"
        message += f"Khu vực bị ảnh hưởng:\n{outage['location']}\n\n"
        message += f"Lý do: {outage['reason']}\n"
        message += "----------------------------\n\n"

    message += "Nguồn: EVN SPC"
    return message


async def send_telegram_message(chat_id, text):
    # Chia nhỏ tin nhắn nếu quá dài (giới hạn Telegram là 4096 ký tự)
    if len(text) <= 4000:
        await bot.send_message(chat_id=chat_id, text=text)
    else:
        # Chia thành nhiều phần
        parts = [text[i:i + 4000] for i in range(0, len(text), 4000)]
        for i, part in enumerate(parts):
            header = f"Phần {i + 1}/{len(parts)}\n\n" if i > 0 else ""
            await bot.send_message(chat_id=chat_id, text=header + part)


def send_update():
    html_content = get_evn_data()
    if html_content:
        power_outages = parse_html_data(html_content)
        message = format_message(power_outages)
        # Chỉ gửi tin nhắn nếu có lịch cắt điện ảnh hưởng đến khu vực cần lọc
        if "Không có lịch cắt điện nào ảnh hưởng" not in message:
            # Sử dụng asyncio.run để chạy coroutine
            asyncio.run(send_telegram_message(CHANNEL_ID, message))
            print(f"Đã gửi cập nhật về lịch cắt điện ảnh hưởng đến khu vực {FILTER_KEYWORD}")
        else:
            print(f"Không có lịch cắt điện nào ảnh hưởng đến khu vực {FILTER_KEYWORD}")


# Lên lịch gửi cập nhật hàng ngày
schedule.every().day.at("08:00").do(send_update)

# Gửi cập nhật ngay khi khởi động
if __name__ == "__main__":
    print(f"Bot đã khởi động. Đang kiểm tra lịch cắt điện cho khu vực {FILTER_KEYWORD}...")
    send_update()

    print("Đang chạy lịch trình...")
    while True:
        schedule.run_pending()
        time.sleep(60)
