import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import joblib, os
import json
from datetime import datetime

# -------------------------------
# Load CSV
# -------------------------------
def load_csv(path):
    return pd.read_csv(path)

# -------------------------------
# Preprocess Data
# -------------------------------
def preprocess(df):
    df = df.copy()
    
    # Fill missing values safely
    if 'attendance' in df.columns:
        df['attendance'] = df['attendance'].fillna(df['attendance'].mean())
    else:
        df['attendance'] = 0
    
    if 'marks' in df.columns:
        df['marks'] = df['marks'].fillna(df['marks'].mean())
    else:
        df['marks'] = 0
    
    # Assignments ratio
    if 'assignments_completed' in df.columns and 'assignments_total' in df.columns:
        df['assign_ratio'] = df['assignments_completed'] / df['assignments_total'].replace(0, 1)
    else:
        df['assign_ratio'] = 0.0
    
    # Normalize subject column and create dummies
    if 'subject' in df.columns:
        df['subject'] = df['subject'].astype(str).str.strip().str.lower()
        subjects = pd.get_dummies(df['subject'], prefix='sub')
        df = pd.concat([df, subjects], axis=1)
    
    # Ensure a unified student ID column
    if 'student_id' not in df.columns:
        if 'enrollment_no' in df.columns:
            df = df.rename(columns={'enrollment_no': 'student_id'})
        elif 'enrollment' in df.columns:
            df = df.rename(columns={'enrollment': 'student_id'})
        else:
            raise ValueError("Data must have 'student_id', 'enrollment_no', or 'enrollment' column")
    
    return df

# -------------------------------
# Merge / Update Duplicate Students
# -------------------------------
def merge_or_update_students(existing_df, new_df):
    new_df = preprocess(new_df)
    
    merged_df = pd.merge(
        existing_df, new_df,
        on='student_id',
        how='outer',
        suffixes=('_old', '_new')
    )
    
    # Update numeric columns
    for col in ['marks', 'attendance', 'assign_ratio']:
        if col+'_old' in merged_df.columns and col+'_new' in merged_df.columns:
            merged_df[col] = merged_df[col+'_new'].combine_first(merged_df[col+'_old'])
            merged_df.drop([col+'_old', col+'_new'], axis=1, inplace=True)
    
    # Update subject dummies
    sub_cols = [c for c in merged_df.columns if c.startswith('sub_')]
    for sub in sub_cols:
        if sub+'_old' in merged_df.columns and sub+'_new' in merged_df.columns:
            merged_df[sub] = merged_df[sub+'_new'].combine_first(merged_df[sub+'_old'])
            merged_df.drop([sub+'_old', sub+'_new'], axis=1, inplace=True)
    
    return merged_df

# -------------------------------
# Aggregate Features Per Student
# -------------------------------
def aggregate_student_features(df):
    df = preprocess(df)
    agg = df.groupby('student_id').agg({
        'marks':'mean',
        'attendance':'mean',
        'assign_ratio':'mean'
    }).reset_index().rename(columns={
        'marks':'avg_marks',
        'attendance':'avg_attendance',
        'assign_ratio':'avg_assign_ratio'
    })
    
    # Aggregate subject dummies
    sub_cols = [c for c in df.columns if c.startswith('sub_')]
    if sub_cols:
        subs = df.groupby('student_id')[sub_cols].mean().reset_index()
        agg = agg.merge(subs, on='student_id', how='left')
    
    # Rename to match your models
    agg = agg.rename(columns={'student_id':'enrollment_no'})
    return agg

# -------------------------------
# Train Random Forest Model
# -------------------------------
def train_model(df, model_path='../models/rf_model.pkl'):
    agg = aggregate_student_features(df)
    
    if len(agg) < 2:
        return None, None  # Not enough data to train
    
    X = agg.drop(columns=['enrollment_no','avg_marks']).fillna(0)
    y = agg['avg_marks']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    preds = model.predict(X_test)
    mse = mean_squared_error(y_test, preds)
    
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(model, model_path)
    
    return model, mse

# -------------------------------
# Predict for Aggregated Data
# -------------------------------
def predict_for_aggregated(df, model_path='../models/rf_model.pkl'):
    df = preprocess(df)
    
    # Always add predicted_marks column
    df['predicted_marks'] = np.nan
    
    # Ensure enrollment_no exists
    if 'student_id' in df.columns:
        df = df.rename(columns={'student_id':'enrollment_no'})
    
    if not os.path.exists(model_path):
        return df
    
    model = joblib.load(model_path)
    if model is None or not hasattr(model, 'feature_names_in_'):
        return df
    
    X = df.drop(columns=['enrollment_no'], errors='ignore').fillna(0)
    
    # Align columns with model
    model_cols = model.feature_names_in_
    for col in model_cols:
        if col not in X.columns:
            X[col] = 0
    X = X[model_cols]
    
    preds = model.predict(X)
    df['predicted_marks'] = preds
    
    return df

# -------------------------------
# Chart.js Analytics Functions
# -------------------------------

def generate_performance_trend_data(student_performances):
    """Generate data for student performance trend chart"""
    if not student_performances:
        return None
    
    labels = []
    actual_marks = []
    predicted_marks = []
    
    for i, performance in enumerate(student_performances):
        labels.append(f"Test {i+1}")
        actual_marks.append(performance.marks)
        predicted_marks.append(getattr(performance, 'predicted_marks', performance.marks))
    
    return {
        "labels": labels,
        "actual_marks": actual_marks,
        "predicted_marks": predicted_marks
    }

def generate_department_comparison_chart(students_data):
    """Generate data for department-wise average marks comparison"""
    if not students_data:
        return None
    
    try:
        df = pd.DataFrame(students_data)
        
        # Check if required columns exist
        if 'department' not in df.columns or 'avg_marks' not in df.columns:
            return None
        
        # Group by department and calculate averages
        dept_stats = df.groupby('department').agg({
            'avg_marks': 'mean',
            'avg_attendance': 'mean',
            'enrollment': 'count'
        }).reset_index()
        
        return {
            "labels": dept_stats['department'].tolist(),
            "avg_marks": dept_stats['avg_marks'].round(2).tolist(),
            "avg_attendance": dept_stats['avg_attendance'].round(2).tolist(),
            "student_count": dept_stats['enrollment'].tolist()
        }
    except Exception as e:
        print(f"Error in department comparison chart: {e}")
        return None

def generate_college_performance_chart(students_data):
    """Generate data for college-wise performance comparison"""
    if not students_data:
        return None
    
    try:
        df = pd.DataFrame(students_data)
        
        if 'college' not in df.columns or 'avg_marks' not in df.columns:
            return None
        
        college_stats = df.groupby('college').agg({
            'avg_marks': 'mean',
            'avg_attendance': 'mean',
            'enrollment': 'count'
        }).reset_index()
        
        return {
            "labels": college_stats['college'].tolist(),
            "avg_marks": college_stats['avg_marks'].round(2).tolist(),
            "avg_attendance": college_stats['avg_attendance'].round(2).tolist(),
            "student_count": college_stats['enrollment'].tolist()
        }
    except Exception as e:
        print(f"Error in college performance chart: {e}")
        return None

def generate_marks_distribution_chart(students_data):
    """Generate data for marks distribution histogram"""
    if not students_data:
        return None
    
    try:
        df = pd.DataFrame(students_data)
        
        if 'avg_marks' not in df.columns:
            return None
            
        marks = df['avg_marks'].dropna()
        
        if len(marks) == 0:
            return None
            
        # Create bins for histogram
        bins = [0, 40, 50, 60, 70, 80, 90, 100]
        hist, bin_edges = np.histogram(marks, bins=bins)
        
        # Create labels for bins
        bin_labels = [f"{int(bin_edges[i])}-{int(bin_edges[i+1])}" for i in range(len(bin_edges)-1)]
        
        return {
            "labels": bin_labels,
            "counts": hist.tolist(),
            "total_students": len(marks)
        }
    except Exception as e:
        print(f"Error in marks distribution chart: {e}")
        return None

def generate_attendance_correlation_chart(students_data):
    """Generate data for attendance vs marks correlation scatter plot"""
    if not students_data:
        return None
    
    try:
        df = pd.DataFrame(students_data)
        
        if 'avg_attendance' not in df.columns or 'avg_marks' not in df.columns:
            return None
            
        return {
            "attendance": df['avg_attendance'].fillna(0).tolist(),
            "marks": df['avg_marks'].fillna(0).tolist(),
            "students": df.get('name', ['Unknown'] * len(df)).tolist()
        }
    except Exception as e:
        print(f"Error in attendance correlation chart: {e}")
        return None

def generate_performance_prediction_chart(students_data):
    """Generate data for actual vs predicted marks comparison"""
    if not students_data:
        return None
    
    try:
        df = pd.DataFrame(students_data)
        
        if 'avg_marks' not in df.columns:
            return None
            
        # If predicted marks are available
        if 'predicted_marks' in df.columns:
            return {
                "students": df.get('name', ['Unknown'] * len(df)).tolist(),
                "actual_marks": df['avg_marks'].tolist(),
                "predicted_marks": df['predicted_marks'].tolist()
            }
        else:
            return {
                "students": df.get('name', ['Unknown'] * len(df)).tolist(),
                "actual_marks": df['avg_marks'].tolist(),
                "predicted_marks": df['avg_marks'].tolist()  # Use actual as fallback
            }
    except Exception as e:
        print(f"Error in performance prediction chart: {e}")
        return None

def generate_subject_performance_chart(performance_data):
    """Generate data for subject-wise performance analysis"""
    if not performance_data:
        return None
    
    try:
        # If performance_data is a list of dictionaries
        if isinstance(performance_data, list) and performance_data:
            df = pd.DataFrame(performance_data)
        else:
            df = pd.DataFrame([performance_data])
        
        if 'subject' not in df.columns or 'marks' not in df.columns:
            return None
            
        subject_stats = df.groupby('subject').agg({
            'marks': 'mean',
            'attendance': 'mean'
        }).reset_index()
        
        return {
            "subjects": subject_stats['subject'].tolist(),
            "avg_marks": subject_stats['marks'].round(2).tolist(),
            "avg_attendance": subject_stats['attendance'].round(2).tolist()
        }
    except Exception as e:
        print(f"Error in subject performance chart: {e}")
        return None

def generate_monthly_trend_chart(performance_data):
    """Generate data for monthly performance trend"""
    if not performance_data:
        return None
    
    try:
        # If performance_data is a list of dictionaries
        if isinstance(performance_data, list) and performance_data:
            df = pd.DataFrame(performance_data)
        else:
            df = pd.DataFrame([performance_data])
        
        # Check if we have date information
        date_column = None
        for col in ['date', 'test_date', 'created_at']:
            if col in df.columns:
                date_column = col
                break
        
        if not date_column:
            return None
        
        # Extract month from date
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        df = df.dropna(subset=[date_column])
        
        if len(df) == 0:
            return None
            
        df['month'] = df[date_column].dt.to_period('M')
        
        monthly_stats = df.groupby('month').agg({
            'marks': 'mean',
            'attendance': 'mean'
        }).reset_index()
        
        monthly_stats['month'] = monthly_stats['month'].astype(str)
        
        return {
            "months": monthly_stats['month'].tolist(),
            "avg_marks": monthly_stats['marks'].round(2).tolist(),
            "avg_attendance": monthly_stats['attendance'].round(2).tolist()
        }
    except Exception as e:
        print(f"Error in monthly trend chart: {e}")
        return None

# -------------------------------
# Main Analytics Data Generator
# -------------------------------

def generate_all_chart_data(students_data=None, student_performances=None, performance_data=None):
    """Generate all chart data for the dashboard"""
    
    chart_data = {}
    
    # Only generate charts if we have students_data
    if students_data:
        chart_data.update({
            "department_comparison": generate_department_comparison_chart(students_data),
            "college_performance": generate_college_performance_chart(students_data),
            "marks_distribution": generate_marks_distribution_chart(students_data),
            "attendance_correlation": generate_attendance_correlation_chart(students_data),
            "performance_prediction": generate_performance_prediction_chart(students_data),
        })
    
    # Add student-specific charts if performance data is available
    if student_performances:
        chart_data["student_trend"] = generate_performance_trend_data(student_performances)
    
    if performance_data:
        chart_data["subject_performance"] = generate_subject_performance_chart(performance_data)
        chart_data["monthly_trend"] = generate_monthly_trend_chart(performance_data)
    
    # Remove None values
    chart_data = {k: v for k, v in chart_data.items() if v is not None}
    
    return chart_data

# -------------------------------
# Utility Functions for Chart.js
# -------------------------------

def get_chart_config(chart_type, chart_data):
    """Generate Chart.js configuration for different chart types"""
    
    base_configs = {
        'bar': {
            'type': 'bar',
            'data': {
                'labels': [],
                'datasets': []
            },
            'options': {
                'responsive': True,
                'plugins': {
                    'legend': {
                        'position': 'top',
                    },
                    'title': {
                        'display': True,
                        'text': 'Chart'
                    }
                }
            }
        },
        'line': {
            'type': 'line', 
            'data': {
                'labels': [],
                'datasets': []
            },
            'options': {
                'responsive': True,
                'plugins': {
                    'legend': {
                        'position': 'top',
                    }
                }
            }
        },
        'doughnut': {
            'type': 'doughnut',
            'data': {
                'labels': [],
                'datasets': [{
                    'data': [],
                    'backgroundColor': []
                }]
            },
            'options': {
                'responsive': True,
                'plugins': {
                    'legend': {
                        'position': 'top',
                    }
                }
            }
        }
    }
    
    return base_configs.get(chart_type, base_configs['bar'])