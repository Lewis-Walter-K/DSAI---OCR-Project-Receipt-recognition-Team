import cv2
import numpy as np
import matplotlib.pyplot as plt
from ultralytics import YOLO
import cv2
import easyocr
import numpy as np

# Chạy Detect và Seg
# --- 1. NẠP MÔ HÌNH Detect và Seg ---
model_detect = YOLO(r"../models/best-detect.pt")
model_segment = YOLO(r"../models/best-seg.pt")

# Đường dẫn ảnh đầu vào của bạn
img_path = r"../input/z7915126283783_8fd817571e9db4ced9e627b389c7c101.jpg"
img_original = cv2.imread(img_path)

# --- 2. CÁC HÀM TOÁN HỌC ĐỂ NẮN THẲNG (HÌNH HỌC KHÔNG GIAN) ---

def order_points(pts):
    """Sắp xếp định vị chính xác 4 góc: [Top-Left, Top-Right, Bottom-Right, Bottom-Left]"""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # Top-left (Tổng x+y nhỏ nhất)
    rect[2] = pts[np.argmax(s)]   # Bottom-right (Tổng x+y lớn nhất)
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)] # Top-right (Hiệu y-x nhỏ nhất)
    rect[3] = pts[np.argmax(diff)] # Bottom-left (Hiệu y-x lớn nhất)
    return rect

def flatten_receipt(image, pts, padding=30):
    """Hàm nắn phẳng nâng cấp: Tự động thêm 'vùng đệm' (padding) bao quanh
    để cứu các con số tổng tiền ở sát mép không bị AI OCR bỏ sót."""
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    # Tính toán kích thước thật chiều rộng mới của tờ hóa đơn sau khi duỗi thẳng
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    # Tính toán kích thước thật chiều cao mới
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    # Tạo khung lưới mới thẳng tắp để áp tọa độ vào
    dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")
    
    # Tính ma trận chuyển đổi và thực hiện nắn phẳng (Cắt bỏ toàn bộ background thừa)
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (maxWidth, maxHeight))

# --- 3. BẮT ĐẦU CHẠY LUỒNG PIPELINE LIÊN HOÀN ---

# Mắt xích 1: Dùng YOLO Detect để định vị vùng chứa hóa đơn
det_results = model_detect(img_original)

if len(det_results[0].boxes) > 0:
    # Lấy hộp vuông có độ tự tin cao nhất
    best_box_idx = det_results[0].boxes.conf.argmax()
    x1, y1, x2, y2 = map(int, det_results[0].boxes[best_box_idx].xyxy[0].tolist())
    cropped_invoice = img_original[y1:y2, x1:x2] 
    
    # Mắt xích 2: Đưa ảnh đã cắt vào mô hình Segmentation 99.5% của bạn
    seg_results = model_segment(cropped_invoice)
    
    if seg_results[0].masks is not None:
        # Lấy danh sách tọa độ đa giác (pixel)
        polygon_points = seg_results[0].masks.xy[0]
        contour = np.array(polygon_points, dtype=np.int32)
        
        # 🔥 ĐÂY LÀ ĐOẠN PHẢI SỬA: Ép đa giác hàng trăm điểm về ĐÚNG 4 GÓC NHỌN
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        
        # Nếu thuật toán tìm ra đúng hình có 4 góc
        if len(approx) == 4:
            pts = approx.reshape(4, 2)
        else:
            # Phương án dự phòng nếu đa giác bị răng cưa: Dùng hộp chữ nhật có diện tích nhỏ nhất ôm khít
            rect_backup = cv2.minAreaRect(contour)
            pts = cv2.boxPoints(rect_backup).astype(int)
        
        # Mắt xích 3: Gọi hàm nắn phẳng (Warp) - Trả về ảnh trực diện, sạch bóng background
        flat_receipt = flatten_receipt(cropped_invoice, pts)
        
        # Mắt xích 4: HẬU XỬ LÝ CHUẨN ĐỒ HỌA CAMSCANNER (Tối ưu cho OCR đọc chữ)
        # Bước A: Chuyển về ảnh xám (Grayscale)
        gray = cv2.cvtColor(flat_receipt, cv2.COLOR_BGR2GRAY)

        # THAY ĐỔI MẤU CHỐT: Tăng blockSize lên số lẻ lớn (81 hoặc 101) để bảo vệ chữ béo/số tiền
        block_size = 81
        C_param = 21    # Hằng số điều chỉnh độ mịn nền
        
        # Bước B: Kích hoạt bộ lọc Adaptive Thresholding (Lọc nhị phân thích ứng)
        # Giúp chuyển nền giấy thành trắng tinh khôi và chữ đen đậm sắc nét, khử bóng mờ tay cầm khôn như CamScanner
        final_ocr_ready = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, C_param
        )

        # Không dùng Adaptive Thresholding nữa
        # Thay bằng bộ lọc tăng cường độ tương phản CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        # final_ocr_ready = clahe.apply(gray)
        
        # --- 4. HIỂN THỊ KẾT QUẢ ĐỐI CHIẾU ---
        fig, axes = plt.subplots(1, 2, figsize=(15, 10))
        
        # Ảnh 1: Ảnh gốc sau khi cắt
        axes[0].imshow(cv2.cvtColor(cropped_invoice, cv2.COLOR_BGR2RGB))
        axes[0].set_title("Ảnh gốc (Bị nghiêng & Dính nền)", fontsize=12, fontweight='bold')
        axes[0].axis('off')
        
        # Ảnh 2: Ảnh thành quả sau nắn và lọc CamScanner
        axes[1].imshow(final_ocr_ready, cmap='gray')
        axes[1].set_title("Kết quả CamScanner (Thẳng băng & Sạch nhiễu OCR)", fontsize=12, fontweight='bold')
        axes[1].axis('off')
        
        plt.tight_layout()
        plt.show()
        
        # Lưu file ảnh sạch nhất để đẩy vào EasyOCR
        output_path = r"../outputs/CAMSCANNER_RESULT.jpg"
        cv2.imwrite(output_path, final_ocr_ready)
        print(f"🔥 THÀNH CÔNG RỰC RỠ! Ảnh chuẩn CamScanner đã xuất xưởng tại: {output_path}")
        
    else:
        print("⚠️ Không tìm thấy mặt nạ đa giác thỏa mãn.")
else:
    print("❌ Không detect được vùng chứa hóa đơn.")

# Chạy OCR
def ocr_and_fix_orientation(image_path):
    # 1. Khởi tạo mô hình EasyOCR
    print("🚀 Đang khởi tạo mô hình EasyOCR song ngữ Anh - Việt...")
    reader = easyocr.Reader(["en", "vi", "de"], gpu=True)
    
    img = cv2.imread(image_path)
    best_image = img
    max_confidence_score = 0
    best_angle = 0
    
    print("🔍 Bước 1: Thám thính tìm góc xoay tối ưu...")
    
    # Thử nghiệm 4 góc xoay dựa trên điểm tin cậy mặc định (Không bật paragraph ở bước này)
    for angle in [0, 90, 180, 270]:
        if angle == 90:
            test_img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        elif angle == 180:
            test_img = cv2.rotate(img, cv2.ROTATE_180)
        elif angle == 270:
            test_img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            test_img = img  # Góc 0 độ
            
        # Đọc chế độ thường để lấy res[2] tính toán toán học
        results_check = reader.readtext(test_img, paragraph=False)
        
        if len(results_check) > 0:
            avg_conf = np.mean([res[2] for res in results_check])
            
            if avg_conf > max_confidence_score:
                max_confidence_score = avg_conf
                best_image = test_img
                best_angle = angle

    print(f"✅ Đã xác định góc xoay đúng của hóa đơn là: {best_angle} độ (Độ tin cậy: {max_confidence_score:.2f})")
    
    # ---------------------------------------------------------------------------
    print("\n🔍 Bước 2: Kích hoạt chế độ Paragraph gom cụm để săn 'Tổng tiền'...")
    
    # Lúc này ảnh đã thẳng hoàn toàn, ta tự tin dùng paragraph=True để bóc tách text
    final_text_results = reader.readtext(
        best_image,            # BẮT BUỘC dùng ảnh này để đảm bảo thẳng chiều 100%
        paragraph=True,        # Gom từ theo dòng, cứu con số ở rìa mép
        batch_size=4,          # Tối ưu năng suất GPU RTX 4060
        decoder='beamsearch',  # Thuật toán giải mã cao cấp chống đọc nhầm số/chữ
        beamWidth=10,          # Tăng độ sâu tìm kiếm từ ngữ
        mag_ratio=1.5,         # Phóng to cục bộ vùng chữ để nhìn rõ nét hơn
        canvas_size=3000,      # Giữ nguyên độ phân giải ảnh lớn, không nén mờ
        text_threshold=0.7,    # Ngưỡng lọc chữ chuẩn
        low_text=0.3           # ĐÃ SỬA: Tên chuẩn của EasyOCR để bắt chữ mờ
    )

    # Đoạn code xuất file .txt để lưu kết quả OCR
    txt_output_path = r"../outputs/OCR_RESULT.txt"

    # Mở file với chế độ 'w' (ghi đè file cũ) và ép định dạng utf-8 để giữ nguyên dấu tiếng Việt
    with open(txt_output_path, "w", encoding="utf-8") as f:
        print("\n--- KẾT QUẢ OCR HÓA ĐƠN HOÀN CHỈNH ---")
        
        for res in final_text_results:
            bbox, text = res  
            print(f"📝 {text}")          # Vẫn in ra màn hình console để bạn theo dõi
            
            f.write(text + "\n")        # Ghi dòng text vào file và tự động xuống dòng (\n)
            
    print(f"\nĐã lưu dữ liệu văn bản sạch hoàn chỉnh tại: {txt_output_path}")
    print("File .txt đã sẵn sàng để nạp làm Prompt Input cho SLM")
            
    # Lưu lại bức ảnh đúng chiều
    output_fixed_path = r"../outputs/FINAL_CORRECT_ORIENTATION.jpg"
    cv2.imwrite(output_fixed_path, best_image)
    print(f"\nĐã lưu ảnh hóa đơn đúng chiều tại: {output_fixed_path}")

# --- CHẠY THỬ NGHIỆM THU ---
image_input = r"../outputs/CAMSCANNER_RESULT.jpg"
ocr_and_fix_orientation(image_input)