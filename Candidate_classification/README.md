# 🧾 Invoice Total Amount Extraction (Candidate Classification)

Đây là module cốt lõi của hệ thống **Invoice Reader**, chịu trách nhiệm đọc chữ trên hóa đơn (OCR) và sử dụng Trí tuệ nhân tạo (XGBoost + NLP) để thông minh tìm ra con số **Tổng tiền (Total Amount)** cuối cùng.

## 🌟 Luồng hoạt động (Pipeline)
1. **Tiền xử lý & Cắt ảnh (`main.py`)**: Nhận ảnh chụp, dùng YOLO v8 để tìm ra tờ hóa đơn, nắn phẳng lại (chuẩn CamScanner). Dùng Tesseract để phát hiện và xoay ảnh cho thẳng đứng.
2. **OCR Ngầm (`ocr_worker.py`)**: Dùng PaddleOCR quét toàn bộ chữ và số trên ảnh đã nắn thẳng. Chạy bằng luồng subprocess độc lập để tránh xung đột RAM/VRAM với các mô hình khác.
3. **Phân loại & Chốt số (`extract_text.ipynb`)**: Áp dụng luật (Rules) và mô hình XGBoost để trích xuất các đặc trưng (Semantic, Tọa độ, v.v.), từ đó lọc bỏ Mã vạch (Barcode/ID) và chốt chính xác con số Tổng Tiền.

---

## ⚙️ Hướng dẫn Cài đặt Môi trường (Cho Team dùng VS Code)

Để chạy được toàn bộ luồng pipeline này trên máy cá nhân (Local Machine), các bạn cần cài đặt 2 phần:

### 1. Cài đặt lõi Tesseract OCR (BẮT BUỘC để xoay ảnh)
Phần mềm này giúp AI nhận diện xem người dùng cầm điện thoại ngang hay dọc để xoay ảnh hóa đơn cho đúng.

**🖥️ Dành cho Windows:**
1. Tải bản cài đặt (64-bit) tại: [Tesseract OCR Windows Installer](https://github.com/UB-Mannheim/tesseract/wiki)
2. Mở file `.exe` vừa tải và tiến hành cài đặt.
3. ⚠️ **QUAN TRỌNG:** Hãy bấm *Next* liên tục và **GIỮ NGUYÊN ĐƯỜNG DẪN MẶC ĐỊNH**. Phải đảm bảo nó được cài vào:
   `C:\Program Files\Tesseract-OCR\`
   *(Code đã được cấu hình đường dẫn này).*

**🍎 Dành cho macOS (Macbook):**
Mở Terminal và chạy lệnh:
```bash
brew install tesseract
```
*Lưu ý: Nếu dùng Mac, bạn cần vào file `Seg_OCR_Tri/src/main.py` và comment (`#`) dòng gán `pytesseract.pytesseract.tesseract_cmd = ...` lại nhé.*

**🐧 Dành cho Linux / Ubuntu / Google Colab:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr -y
```

### 2. Cài đặt thư viện Python
Mở Terminal trong VS Code và chạy lệnh sau để tải toàn bộ thư viện AI cần thiết:
```bash
pip install opencv-python numpy pandas matplotlib
pip install ultralytics
pip install paddlepaddle paddleocr
pip install sentence-transformers
pip install xgboost scikit-learn
pip install pytesseract
```

---

## 🚀 Hướng dẫn Chạy hệ thống

Cách đơn giản nhất để test luồng:
1. Mở file `extract_text.ipynb` bằng Jupyter Notebook hoặc VS Code.
2. Đổi đường dẫn biến `image_input` trỏ tới bức ảnh hóa đơn bạn muốn test.
3. Bấm **Run All** (Chạy tất cả các ô).
4. Kéo xuống phần cuối cùng của Notebook để xem bảng xếp hạng Top 5 ứng viên (Candidates) và **Kết quả Tổng tiền chốt hạ**.
