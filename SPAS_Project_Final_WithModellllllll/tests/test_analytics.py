import pandas as pd
from backend.analytics import aggregate_student_features
df = pd.read_csv('data/sample_students.csv')
agg = aggregate_student_features(df)
print(agg.head())
