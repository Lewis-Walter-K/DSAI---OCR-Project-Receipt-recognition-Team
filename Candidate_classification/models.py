import sys
import re
import numpy as np
from ultralytics import YOLO
from sentence_transformers import SentenceTransformer
from transformers import pipeline
import xgboost as xgb
from sklearn.metrics.pairwise import cosine_similarity

from config import SEG_MODELS, XGB_MODEL_PATH

print("🚀 Đang khởi tạo các mô hình AI... Vui lòng đợi.")

# Load segmentation model
model_segment = YOLO(str(SEG_MODELS / "best-seg.pt"))

# Embedding & NLI
embedding_model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

nli_classifier = pipeline(
    "zero-shot-classification",
    model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
)

# prompts helper
def _flatten(prompts):
    return [x.strip() for p in prompts for x in p.split(',') if x.strip()]

_pos_prompts = _flatten([
    "order total, grand total, total amount to pay, amount due, balance due, net total, total-eft",
    "tổng cộng, tổng tiền, thành tiền, thanh toán, số tiền thanh toán, tổng tier, thành tier, Tổng tiền hàng",
    "tong cong, tong tien, thanh tien, thanh toan, so tien thanh toan, tong tier, thanh tier, Tong tien hang",
    "消费合计, 合计, 总计, 实付金额, 应付金额, 收款金额, 结账金额",
    "合計, お会計, 請求金額, 支払合計, お支払い金額",
    "합계, 총액, 결제금액, 청구금액, 지불합계",
])

_neg_prompts = _flatten([
    "transaction ID, reference code, authorization code, barcode, serial number, phone number",
    "mã giao dịch, mã tham chiếu, mã vạch, số điện thoại, mã hóa đơn, tiền thừa, tiền nhận",
    "ma giao dich, ma tham chieu, ma vach, so dien thoai, ma hoa don, tien thua, tien nhan, thira",
    "交易号, 参考号, 条形码, 电话, 授权码, 流水号",
    "取引ID, 参照番号, バーコード, 電話番号, シリアル番号",
])

_qty_prompts = _flatten([
    "number of items, quantity, item count, total pieces, total units",
    "số lượng, số món, số cái, tổng số lượng",
    "so luong, so mon, so cai, tong so luong",
    "数量, 点数, 個数, 件数",
    "수량, 개수, 총수량",
])

_tax_prompts = _flatten([
    "tax amount, VAT, consumption tax, sales tax, service tax, tax included",
    "tiền thuế, thuế VAT, thuế tiêu thụ đặc biệt, phí dịch vụ",
    "tien thue, thue vat, thue tieu thu dac biet, phi dich vu",
    "税额, 增值税, 消费税, 税, 含税",
    "消費税, 内消費税, 税込, 税額, 内税",
    "세금, 부가세, 소비세",
])

_time_prompts = _flatten([
    "time, hour, check-in time, check-out time, opening time, timestamp, date and time",
    "giờ vào, giờ ra, thời gian, ngày giờ, giờ mở cửa, thời điểm",
    "gio vao, gio ra, thoi gian, ngay gio, gio mo cua, thoi diem, gio",
    "时间, 日期, 入店时间, 离店时间, 营业时间",
    "時間, 日時, チェックイン, チェックアウト",
    "시간, 날짜, 체크인, 체크아웃",
])

POSITIVE_VECTORS  = embedding_model.encode(_pos_prompts)
NEGATIVE_VECTORS  = embedding_model.encode(_neg_prompts)
QUANTITY_VECTORS  = embedding_model.encode(_qty_prompts)
TAX_VECTORS       = embedding_model.encode(_tax_prompts)
TIME_VECTORS      = embedding_model.encode(_time_prompts)

CURRENCY_PATTERN = re.compile(
    r'[\$€£¥₩₹₽₺₴₦฿₫₱¢]|USD|EUR|EURO|VND|JPY|GBP|AUD|CAD|SGD|CHF',
    re.IGNORECASE
)

NUMBER_PATTERN = re.compile(r'\b\d+(?:[\.,:]\d+)*\b')

xgb_model = xgb.XGBClassifier()
if XGB_MODEL_PATH.exists():
    xgb_model.load_model(str(XGB_MODEL_PATH))
else:
    print(f"❌ Lỗi: Không tìm thấy model {XGB_MODEL_PATH}")
    sys.exit(1)
