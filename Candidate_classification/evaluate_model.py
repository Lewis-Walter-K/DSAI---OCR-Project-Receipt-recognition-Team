import os
import pandas as pd
import numpy as np
import xgboost as xgb
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, confusion_matrix, accuracy_score,
    roc_curve, auc, precision_recall_curve, average_precision_score
)
from pathlib import Path

# Setup paths
CURRENT_DIR = Path(__file__).resolve().parent
DATA_PATH = CURRENT_DIR / "xgboost_dataset.csv"
REPORT_DIR = CURRENT_DIR / "outputs" / "report"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

print("Starting XGBoost Evaluation & Report Generation...")

# 1. Load Data
if not DATA_PATH.exists():
    raise FileNotFoundError(f"Cannot find dataset at {DATA_PATH}")

df = pd.read_csv(DATA_PATH)
print(f"Loaded {len(df)} candidates.")

X = df[["semantic_sim", "normalized_y", "is_max", "text_length", "has_currency"]]
y = df["label"]

# Train/Test Split (80/20)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

neg_count = sum(y_train == 0)
pos_count = sum(y_train == 1)
scale_weight = neg_count / pos_count

print(f"Training on {len(X_train)} samples, Validating on {len(X_test)} samples.")
print(f"Class Imbalance Weight (0 vs 1): {scale_weight:.2f}")

# 2. Initialize Model
xgb_model = xgb.XGBClassifier(
    n_estimators=200,
    max_depth=5,
    learning_rate=0.05,
    scale_pos_weight=scale_weight,
    eval_metric="logloss",
    random_state=42
)

# 3. Train with Evaluation Set to track loss
eval_set = [(X_train, y_train), (X_test, y_test)]
xgb_model.fit(
    X_train, y_train,
    eval_set=eval_set,
    verbose=False
)

# Predictions
y_pred = xgb_model.predict(X_test)
y_prob = xgb_model.predict_proba(X_test)[:, 1]

print("\nTraining Complete! Generating Graphs...")

# ── GRAPHS & VISUALIZATIONS ──
sns.set_theme(style="whitegrid")

# Graph 1: Training Loss Curve
results = xgb_model.evals_result()
epochs = len(results['validation_0']['logloss'])
x_axis = range(0, epochs)

plt.figure(figsize=(10, 6))
plt.plot(x_axis, results['validation_0']['logloss'], label='Train Loss')
plt.plot(x_axis, results['validation_1']['logloss'], label='Validation Loss')
plt.legend()
plt.title('XGBoost Log Loss (Learning Curve)')
plt.ylabel('Log Loss')
plt.xlabel('Boosting Rounds (Estimators)')
plt.savefig(REPORT_DIR / "1_training_loss_curve.png", dpi=300, bbox_inches='tight')
plt.close()

# Graph 2: Feature Importance
plt.figure(figsize=(10, 6))
importances = xgb_model.feature_importances_
features = X.columns
indices = np.argsort(importances)

plt.barh(range(len(indices)), importances[indices], color='skyblue', align='center')
plt.yticks(range(len(indices)), [features[i] for i in indices])
plt.title('Feature Importance (XGBoost)')
plt.xlabel('Relative Importance')
plt.savefig(REPORT_DIR / "2_feature_importance.png", dpi=300, bbox_inches='tight')
plt.close()

# Graph 3: Confusion Matrix
plt.figure(figsize=(8, 6))
cm = confusion_matrix(y_test, y_pred)
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False,
            xticklabels=["Not Total", "Total"],
            yticklabels=["Not Total", "Total"])
plt.title('Confusion Matrix')
plt.ylabel('Actual Label')
plt.xlabel('Predicted Label')
plt.savefig(REPORT_DIR / "3_confusion_matrix.png", dpi=300, bbox_inches='tight')
plt.close()

# Graph 4: ROC Curve
plt.figure(figsize=(10, 6))
fpr, tpr, _ = roc_curve(y_test, y_prob)
roc_auc = auc(fpr, tpr)
plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.3f})')
plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
plt.title('Receiver Operating Characteristic (ROC)')
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.legend(loc="lower right")
plt.savefig(REPORT_DIR / "4_roc_curve.png", dpi=300, bbox_inches='tight')
plt.close()

# Graph 5: Precision-Recall Curve
plt.figure(figsize=(10, 6))
precision, recall, _ = precision_recall_curve(y_test, y_prob)
pr_auc = average_precision_score(y_test, y_prob)
plt.plot(recall, precision, color='purple', lw=2, label=f'PR curve (AP = {pr_auc:.3f})')
plt.title('Precision-Recall Curve')
plt.xlabel('Recall')
plt.ylabel('Precision')
plt.legend(loc="lower left")
plt.savefig(REPORT_DIR / "5_precision_recall_curve.png", dpi=300, bbox_inches='tight')
plt.close()

print(f"\n5 Performance Graphs have been successfully saved to: {REPORT_DIR}")
print("You can copy these PNG files directly into your report!")
