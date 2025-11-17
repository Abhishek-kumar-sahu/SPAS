import os, joblib, pandas as pd

from flask import current_app
from backend.models import Student, Performance, db
from backend.analytics import aggregate_student_features, predict_for_aggregated

MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'rf_model.pkl')

def load_model():
    if os.path.exists(MODEL_PATH):
        try:
            return joblib.load(MODEL_PATH)
        except Exception as e:
            current_app.logger.warning('Model load failed: %s', e)
    return None

def student_agg_df_from_db():
    perfs = Performance.query.all()
    rows = []
    for p in perfs:
        rows.append({'student_id': p.student.student_id, 'subject': p.subject, 'marks': p.marks, 'attendance': p.attendance, 'assignments_completed':0, 'assignments_total':1})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    agg = aggregate_student_features(df)
    return agg

def generate_alerts(threshold=50.0):
    agg = student_agg_df_from_db()
    alerts = []
    if agg.empty:
        return alerts
    pred_df = predict_for_aggregated(agg) if os.path.exists(MODEL_PATH) else agg
    for _, row in pred_df.iterrows():
        val = row.get('predicted_marks', row.get('avg_marks',0))
        if float(val) < threshold:
            alerts.append({'student_id': row['student_id'], 'predicted_marks': float(val)})
    return alerts

def personalized_recommendation(student_id):
    perfs = Performance.query.join(Student).filter(Student.student_id==student_id).all()
    if not perfs:
        return {'msg':'No data'}
    avg_marks = sum([p.marks for p in perfs])/len(perfs)
    avg_att = sum([p.attendance for p in perfs])/len(perfs)
    recs = []
    if avg_att < 75:
        recs.append('Improve attendance to at least 75%')
    if avg_marks < 50:
        recs.append('Attend remedial classes and practice basics')
    elif avg_marks < 70:
        recs.append('Regular practice and revision recommended')
    else:
        recs.append('Keep up the good work; try advanced problems')
    # weak subjects
    subj = {}
    for p in perfs:
        subj.setdefault(p.subject,[]).append(p.marks)
    weak = [s for s,v in subj.items() if sum(v)/len(v) < 60]
    if weak:
        recs.append('Weak subjects: ' + ', '.join(weak))
    return {'avg_marks':avg_marks,'avg_attendance':avg_att,'recommendations':recs}
