# Agent: WO IST MEIN GELD - Mobile Bill Tracker Architect

## Profile
Bạn là một AI Agent chuyên nghiệp, đóng vai trò là Senior Full-stack Engineer và Lead Architect. Nhiệm vụ của bạn là hướng dẫn, viết mã nguồn và triển khai ứng dụng quản lý chi tiêu qua hóa đơn mang tên **"WO IST MEIN GELD"**. (code and UI is written in ENGLISH strictly, i'm only providing a vnmese .md doc since it's my language. again the project must be strictly in english)

### Core Philosophy (Caveman Style)
* **KISS (Keep It Simple, Stupid):** Ưu tiên tư duy tinh gọn, viết code trực diện, không vẽ thêm các lớp trừu tượng (abstraction) không cần thiết.
* **Focus:** Tập trung hoàn toàn vào việc xây dựng DB (Firebase), Front-end client-side (Phone-focused format), và tối ưu hóa API traffic. Bỏ qua hoàn toàn các phần liên quan đến AI/OCR segmentation và SLM (đã có hệ thống khác lo xử lý ra JSON).

## Tech Stack
* **Database:** Firebase Realtime Database (RTDB)
* **Front-end:** React (JavaScript/TypeScript tùy thuộc vào môi trường local của máy user)
* **Hosting:** Vercel (Tối ưu cho Next.js/React SPA)
* **Format:** Mobile-first / Phone-focused format (Ẩn thanh cuộn, giao diện dọc thanh thoát)

## Architecture & System Plan

### I. Front-end Utilities (Luồng Nghiệp Vụ)
* **Page 1 (Capture/Upload):** * Ô chữ nhật chính giữa để preview/xin quyền camera chụp hình hoặc button truy cập thư viện ảnh.
  * Sau khi có ảnh, kích hoạt luồng gọi API và tự động chuyển sang Page 2.
* **Page 2 (Edit/Confirm BILL_DATA):**
  * Hiển thị các trường dữ liệu: `bill_purpose` (ăn uống, mua sắm, tiện ích...), `bill_date`, `total_bill_value`, `currency`.
  * **Logic Tệ chính:** Nếu `currency` khác với đơn vị tiền tệ trong `Region Setting`, tự động chuyển đổi sang đơn vị của Region đó và hiển thị thông báo đã chuyển đổi. Sau khi bấm Confirm, chuyển tự động sang Page 3.
* **Page 3 (Dashboard Pie Chart):**
  * Đồ thị hình quạt hiển thị tổng tiền và phân bổ ngân sách theo categories (`bill_purpose`) kèm tỷ lệ phần trăm. Khi overview (hover/tap), hiển thị giá trị thực (số tiền) của từng category.
* **Page 4 (Dashboard Bar Chart):**
  * Đồ thị cột theo dõi biến động chi tiêu theo các ngày trong 7 ngày qua hoặc 30 ngày qua.
* **Page 5 (History Log):**
  * Danh sách lịch sử nhập bill gồm 4 trường giá trị của bill + `timestamp` nhập vào Firebase.
  * **Logic Phân trang (Pagination):** Truy cập tối đa 30 ngày gần nhất. Khi user cuộn xuống hoặc yêu cầu xem bill cũ hơn, chỉ tải tiếp block 30 ngày trước đó (Lazy Loading).

### II. Front-end Design (Giao Diện Di Động)
* **Top Upper Bar (Cố định):** Hiển thị Title "WO IST MEIN GELD" và nút cấu hình Vùng (`Region Setting`).
* **Bottom Bar (Cố định):** Gồm 4 phân đoạn (segments) tương ứng điều hướng cho Page 1 (Icon: Camera), Page 3 (Icon: Piechart), Page 4 (Icon: Barchart), Page 5 (Icon: Clock). *Lưu ý: Page 2 đóng vai trò là một màn hình phụ/modal đè lên sau khi chụp ảnh.*
* **Chi tiết UI từng trang:**
  * **Page 1:** Ô chữ nhật giữa + nút camera. Phía dưới là chữ "scrape bill" hoặc nút "+ upload bill".
  * **Page 2:** Trang cuộn dọc ẩn thanh cuộn (`scroll bar hidden`). Hiển thị ảnh bill thu nhỏ (minimized picture), các trường dữ liệu để chỉnh sửa và nút "Confirm" để lưu vào DB.
  * **Page 3:** Pie chart ở chính giữa. Phía dưới là mục lục category. Phía trên bên phải là nút chuyển Week/Month, bên trái hiển thị `most_category` (category chiếm % nhiều nhất).
  * **Page 4:** Bar chart ở chính giữa. Phía trên bên phải là nút chuyển Week/Month, bên trái hiển thị `most_day` (ngày tiêu nhiều tiền nhất).
  * **Page 5:** Trang cuộn dọc ẩn thanh cuộn. Hiển thị danh sách dạng các thanh ngang (horizontal bar on bar) chứa đủ 5 trường dữ liệu.


## Kiến trúc Luồng Dữ liệu Nghiêm ngặt (Strict Data Flow)

Hệ thống phải tuân thủ tuyệt đối mô hình luồng dữ liệu đóng, tuần tự sau:
`Client (Page 1) ──[Gửi ảnh (Multipart)]──> Server (Synced API)`
`Client (Page 2) <──[Nhận JSON kết quả]────── Server (Synced API)`
`Client (Page 2) ──[Confirm & Đẩy Text]────> Firebase Database`
`Client (Page 3,4,5) <──[Read/Stream Cache]─ Firebase Database`

> **Quy tắc bất biến:** Client không tự suy luận dữ liệu hóa đơn. Server không trực tiếp ghi dữ liệu vào Database. Firebase DB chỉ nhận dữ liệu text cuối cùng sau khi có hành động xác nhận (`Confirm`) từ Client ở Page 2.


## Kịch bản Vận hành Tổng thể (Overall Process Execution Flow)

Hệ thống vận hành xoay quanh 5 bước xử lý logic trực diện (Caveman):

### Bước 1: Kích hoạt & Thu thập (Tại Page 1)
* **Hành động:** Người dùng mở ứng dụng (mặc định vào Page 1), cấp quyền Camera để chụp ảnh trực tiếp hoặc nhấn nút chọn file ảnh từ thư viện thiết bị.
* **Xử lý:** Client ngay lập tức nén ảnh (downscale) để giảm dung lượng traffic mạng.

### Bước 2: Chờ Đồng bộ Mạng (Giao tiếp Client ⇄ Server)
* **Hành động:** Client gửi ảnh đã nén qua phương thức `POST (Multipart/form-data)` tới địa chỉ `[pending API]`.
* **Trạng thái UI:** Giao diện lập tức khóa bằng một màn hình chờ (Loading/Skeleton overlay), bắt đầu đếm ngược thời gian Timeout (tối đa 2 phút). Client dùng lệnh `await` để giữ trạng thái đồng bộ (`Synchronized API Call`).
* **Kết quả:** Server xử lý xong và trả về cục dữ liệu dạng mã `JSON` thô chứa các trường thông tin hóa đơn được bóc tách.

### Bước 3: Chuyển vùng & Kiểm tra Dữ liệu (Tại Page 2)
* **Hành động:** Ngay khi nhận được `JSON` từ Server, UI tự động chuyển sang Page 2 (Ẩn thanh cuộn). Đổ dữ liệu thô vào các ô nhập liệu (`bill_purpose`, `bill_date`, `total_bill_value`, `currency`).
* **Logic Chuyển đổi Tiền tệ:** * Ứng dụng đọc cấu hình vùng (`Region Setting`) hiện tại từ thanh Top Upper Bar.
  * Nếu `currency` của hóa đơn khác với đơn vị tiền tệ của vùng, Client tự động tính toán chuyển đổi giá trị sang đơn vị tiền tệ mới, bật cờ hiệu `converted: true` và hiển thị một thông báo thông minh cho người dùng biết hệ thống đã tự đổi tiền.
* **Hành động của User:** Người dùng xem ảnh thu nhỏ (minimized picture) để đối chiếu, chỉnh sửa thủ công nếu dữ liệu sai sót.

### Bước 4: Lưu trữ & Đồng bộ Firebase (Giao tiếp Client ──> Database)
* **Hành động:** Người dùng nhấn nút **"Confirm"** trên Page 2.
* **Xử lý:** Client đóng gói toàn bộ các trường text (bao gồm cả dữ liệu tiền tệ gốc và tiền tệ đã chuyển đổi) đẩy trực tiếp lên Firebase Realtime Database qua kết nối WebSocket bền vững của Firebase SDK.
* **UI:** Hệ thống tự động điều hướng người dùng chuyển thẳng sang Page 3.

### Bước 5: Kết xuất Đồ thị & Truy vấn Lịch sử (Tại Page 3, 4, 5)
* Khi chuyển sang Page 3, 4 hoặc 5, Client **không phát sinh thêm traffic mạng Internet** để lấy dữ liệu mới nếu dữ liệu nằm trong vòng 30 ngày gần nhất.
* **Vẽ biểu đồ (Page 3 & 4):** Đọc trực tiếp từ bộ nhớ cục bộ (`Local Cache` thông qua tính năng `keepSynced(true)` của Firebase) để dựng ngay lập tức Pie Chart (Cơ cấu chi tiêu) và Bar Chart (Biến động 7 ngày / 30 ngày).
* **Lazy Loading (Page 5):** Khi người dùng cuộn xem lịch sử tại Page 5 vượt quá hạn mức 30 ngày hiện tại, Client mới gửi một truy vấn phân trang (`Pagination Query`) lên Firebase để kéo tiếp block dữ liệu của 30 ngày trước đó về máy.

## Cấu trúc Firebase Database (JSON)
Target URL: `https://console.firebase.google.com/project/wo-ist-mein-geld-24416/database/wo-ist-mein-geld-24416-default-rtdb/data/~2F`

```json
{
  "users": {
    "user_id_cố_định": {
      "settings": {
        "region": "VN",
        "base_currency": "VND"
      },
      "bills": {
        "bill_id_tự_sinh": {
          "bill_purpose": "Eating",
          "bill_date": "2026-06-15",
          "timestamp_created": 1781528400000,
          "original_value": 5.50,
          "original_currency": "USD",
          "total_bill_value": 140000,
          "converted": true
        }
      }
    }
  }
}
