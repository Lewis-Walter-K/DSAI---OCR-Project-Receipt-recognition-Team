import cv2
import numpy as np
from models import model_segment
from config import OUTPUT_DIR


def _order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _flatten_receipt(image, pts):
    rect = _order_points(pts)
    tl, tr, br, bl = rect

    width = max(int(np.linalg.norm(br - bl)), int(np.linalg.norm(tr - tl)))
    height = max(int(np.linalg.norm(tr - br)), int(np.linalg.norm(tl - bl)))

    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (width, height))


def img_scanner(img_path: str) -> str | None:
    img_original = cv2.imread(img_path)
    if img_original is None:
        raise ValueError(f"Không thể đọc ảnh: {img_path}")

    seg_results = model_segment(img_original)

    if not seg_results[0].boxes or seg_results[0].masks is None:
        print("❌ Không tìm thấy hóa đơn hoặc mặt nạ đa giác.")
        return None

    best_idx = int(seg_results[0].boxes.conf.argmax())
    polygon = seg_results[0].masks.xy[best_idx]
    contour = np.array(polygon, dtype=np.int32)

    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

    pts = approx.reshape(4, 2) if len(approx) == 4 else cv2.boxPoints(cv2.minAreaRect(contour)).astype(int)

    flat = _flatten_receipt(img_original, pts)

    gray = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)
    cleaned = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 81, 21)

    output_path = OUTPUT_DIR / "CAMSCANNER_RESULT.jpg"
    cv2.imwrite(str(output_path), cleaned)
    print(f"✅ Ảnh đã xuất tại: {output_path}")
    return str(output_path)
