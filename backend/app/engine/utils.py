import math
import pandas as pd


def ts(x):
    if x is None or (isinstance(x, float) and math.isnan(x)) or x is pd.NaT:
        return None
    try:
        return pd.Timestamp(x).to_pydatetime()
    except Exception:
        return None


def clv(margin, cost, churn, horizon=10, rate=0.06):
    churn = min(max(churn, 0.0), 0.99)
    return sum((margin - cost) * (1 - churn) ** (t - 1) / (1 + rate) ** t for t in range(1, horizon + 1))
