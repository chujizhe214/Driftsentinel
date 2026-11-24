"""DriftSentinel 本地表格二分类适配器（joblib / scikit-learn 示例）。"""
from pathlib import Path
from joblib import load

# 修改模型文件名；建议加载包含训练时预处理的完整 Pipeline。
# 模型文件与本适配器放在同一文件夹，路径同时适用于 Docker 和本地运行。
model = load(Path(__file__).parent / "delivery_model.joblib")

def predict(X):
    # X 是平台传入的 pandas DataFrame，不包含已选择的真实标签列。
    # 字段、类型、顺序和预处理须与训练时一致；返回长度为 len(X) 的类别数组。
    return model.predict(X)

def predict_proba(X):
    # 模型必须支持 predict_proba；无此接口请选择“仅类别预测”模板。
    # 两列概率的第二列必须对应平台登记的正类，请检查 model.classes_ 顺序。
    # 也可改为返回一维正类概率，范围为 0–1，长度为 len(X)。
    return model.predict_proba(X)
