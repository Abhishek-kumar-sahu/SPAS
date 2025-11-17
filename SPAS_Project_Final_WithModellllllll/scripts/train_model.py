# backend/analytics.py
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import joblib
import os

def train_model(df: pd.DataFrame, model_path: str = None):
    """
    Train a RandomForestRegressor on student performance data.

    Args:
        df (pd.DataFrame): DataFrame with student features.
        model_path (str): Path to save the trained model (optional).

    Returns:
        model: Trained RandomForestRegressor
        mse: Mean Squared Error on test set
    """
    # --- Step 1: Clean data ---
    df = df.copy()
    
    # Drop rows where target is missing
    if 'exam_marks' not in df.columns:
        raise ValueError("DataFrame must contain 'exam_marks' column as target")
    
    df = df.dropna(subset=['exam_marks'])
    
    # Fill numeric columns with median, convert non-numeric columns if possible
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        df[col] = df[col].fillna(df[col].median())

    # Convert categorical/string columns to numeric (simple encoding)
    cat_cols = df.select_dtypes(include=['object']).columns.tolist()
    for col in cat_cols:
        df[col] = df[col].astype('category').cat.codes

    # Features and target
    X = df.drop(columns=['exam_marks'])
    y = df['exam_marks']

    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)

    # Save model
    if model_path:
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)

    return model, mse
