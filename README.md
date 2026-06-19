# WO IST MEIN GELD - Receipt Recognition System

Đây là hệ thống quản lý chi tiêu (mobile-first) tập trung vào chức năng nhận diện hóa đơn (OCR) và tự động trích xuất thông tin thông minh thông qua XGBoost & Gemini SLM.

Hệ thống bao gồm 2 phần: **Backend** (Python/FastAPI) thực hiện OCR & AI, và **Frontend** (React/Vite) cung cấp giao diện người dùng trên thiết bị di động.

## 1. Yêu cầu hệ thống (Prerequisites)
- **Node.js** (Phiên bản >= 18.x) và `npm` để chạy Frontend.
- **Python** (Phiên bản >= 3.10) để chạy Backend.
- **Google Gemini API Key** để sử dụng tính năng "Ask AI" (fallback).

---

## 2. Cài đặt và Chạy Backend (AI & API Server)

Backend chịu trách nhiệm xử lý hình ảnh, gọi module PaddleOCR, phân loại bằng XGBoost và fallback sang Gemini API.

### Bước 2.1: Cài đặt môi trường Python
Mở Terminal/PowerShell tại thư mục gốc của dự án (`DSAI---OCR-Project-Receipt-recognition-Team`):

```bash
# (Tùy chọn) Tạo môi trường ảo
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

# Cài đặt thư viện cần thiết
pip install -r requirements.txt
```

### Bước 2.2: Cấu hình API Key (Environment Variables)
Tạo một file có tên `.env` bên trong thư mục `Candidate_classification/` và thêm key của Gemini vào:

File: `Candidate_classification/.env`
```env
GOOGLE_API_KEY=điền_api_key_của_bạn_vào_đây
```

### Bước 2.3: Khởi động Server
Vẫn ở thư mục gốc của dự án, chạy lệnh:
```bash
python api.py
```
> Server FastAPI sẽ khởi động tại địa chỉ: `http://localhost:8000`

---

## 3. Cài đặt và Chạy Frontend (React/Vite)

Frontend là một giao diện Web SPA được thiết kế tối ưu cho trải nghiệm trên màn hình dọc (điện thoại di động).

### Bước 3.1: Cài đặt thư viện
Mở một tab Terminal mới, di chuyển vào thư mục `temp/`:
```bash
cd temp
npm install
```

### Bước 3.2: Khởi động Frontend
Chạy server phát triển của Vite:
```bash
npm run dev
```
> Trình duyệt sẽ tự động mở hoặc bạn có thể truy cập bằng đường dẫn: `http://localhost:5173`

---

## 4. Luồng hoạt động cơ bản
1. Mở Frontend trên trình duyệt (F12 chọn chế độ xem Mobile để có trải nghiệm tốt nhất).
2. Tải lên một ảnh hóa đơn.
3. Frontend gửi ảnh đến `http://localhost:8000/api/upload`.
4. Backend nhận ảnh, áp dụng filter kiểu CamScanner (`outputs/CAMSCANNER_RESULT.jpg`), chạy PaddleOCR, và đánh giá bằng thuật toán XGBoost.
5. Nếu XGBoost không tự tin hoặc bạn thấy dữ liệu sai, bấm nút **"Ask AI (Gemini)"**. Lúc này, Frontend sẽ gửi trực tiếp cục chữ (OCR text) lên `/api/llm-parse` để bóc tách lại chuẩn xác theo định dạng ngày tháng Châu Á bằng Gemini 2.5 Flash.
6. Xác nhận (`Confirm`) để lưu vào Database.
