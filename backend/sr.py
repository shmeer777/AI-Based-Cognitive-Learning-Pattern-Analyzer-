from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector
import pandas as pd
import numpy as np
from scipy.cluster.vq import kmeans2, whiten
import os
from datetime import datetime, timedelta

web = Flask(__name__)
CORS(web)

DB_AVAILABLE = False

def get_connection():
    global DB_AVAILABLE
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="YOUR_PASSWORD",
            database="cognitive_learning",
            auth_plugin='mysql_native_password'
        )
        DB_AVAILABLE = True
        return conn
    except:
        DB_AVAILABLE = False
        return None

# try to ensure history table exists
try:
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("""
CREATE TABLE IF NOT EXISTS student_behavior_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(50),
    avg_response_time FLOAT,
    avg_attempts FLOAT,
    accuracy FLOAT,
    cluster INT,
    recommendation VARCHAR(255),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
        conn.commit()
        cur.close()
        conn.close()
except:
    pass

def fetch_data():
    if not DB_AVAILABLE:
        # Return mock data when database is unavailable
        return pd.DataFrame({
            "student_id": ["24KQ1A5444", "24KQ1A5445", "24KQ1A5446", "24KQ1A5447"],
            "response_time": [15.2, 18.5, 12.3, 20.1],
            "attempts": [1.8, 2.1, 1.5, 2.5],
            "correct": [0.85, 0.78, 0.92, 0.70],
            "marks": [85, 78, 92, 70]
        })
    try:
        conn = get_connection()
        if not conn:
            return pd.DataFrame()
        query = "SELECT * FROM student_logs"
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

def analyze_behavior(df):
    grouped = df.groupby("student_id").agg({
        "response_time": "mean",
        "attempts": "mean",
        "correct": "mean"
    }).reset_index()

    grouped.rename(columns={
        "response_time": "avg_response_time",
        "attempts": "avg_attempts",
        "correct": "accuracy"
    }, inplace=True)

    return grouped

def classify_students(data):
    features = data[["avg_response_time", "avg_attempts", "accuracy"]].values
    normalized_features = whiten(features)
    centroids, labels = kmeans2(normalized_features, 3, minit='points')
    data["cluster"] = labels
    return data

def generate_recommendation(row):
    if row["accuracy"] < 0.5:
        return "Review fundamentals with guided videos"
    elif row["avg_response_time"] > 20:
        return "Practice timed quizzes"
    elif row["avg_attempts"] > 2:
        return "Use step-by-step hints"
    else:
        return "Advanced challenge questions recommended"

@web.route('/')
def home():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
    return send_from_directory(root, 'arise.html')

@web.route('/<path:filename>')
def static_files(filename):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
    return send_from_directory(root, filename)


@web.route("/analyze")
def analyze():
    df = fetch_data()

    if df.empty:
        return jsonify([
            {"student_id": "24KQ1A5444", "accuracy": 0.85, "avg_response_time": 15.2, "cluster": 0, "recommendation": "Advanced challenge questions recommended"},
            {"student_id": "24KQ1A5445", "accuracy": 0.78, "avg_response_time": 18.5, "cluster": 1, "recommendation": "Practice timed quizzes"}
        ])

    behavior = analyze_behavior(df)
    classified = classify_students(behavior)
    classified["recommendation"] = classified.apply(generate_recommendation, axis=1)

    # store snapshot to history table if DB available
    if DB_AVAILABLE:
        try:
            conn = get_connection()
            if conn:
                cur = conn.cursor()
                for _, row in classified.iterrows():
                    cur.execute(
                        "INSERT INTO student_behavior_history (student_id, avg_response_time, avg_attempts, accuracy, cluster, recommendation) VALUES (%s,%s,%s,%s,%s,%s)",
                        (row.student_id, row.avg_response_time, row.avg_attempts, row.accuracy, int(row.cluster), row.recommendation)
                    )
                conn.commit()
                cur.close()
                conn.close()
        except:
            pass

    return jsonify(classified.to_dict(orient="records"))

from ai_config import ask_ai_question
import heapq

def a_star(graph, start, goal, h=lambda n:0):
    open_set=[]
    heapq.heappush(open_set,(0,start))
    came_from={}
    g_score={start:0}
    f_score={start:h(start)}
    while open_set:
        _, current = heapq.heappop(open_set)
        if current==goal:
            path=[current]
            while current in came_from:
                current=came_from[current]
                path.append(current)
            return list(reversed(path))
        for neighbor,cost in graph.get(current,[]):
            tentative=g_score[current]+cost
            if tentative < g_score.get(neighbor,float('inf')):
                came_from[neighbor]=current
                g_score[neighbor]=tentative
                f_score[neighbor]=tentative+h(neighbor)
                heapq.heappush(open_set,(f_score[neighbor],neighbor))
    return None


@web.route("/history/<student_id>")
def history(student_id):
    if not DB_AVAILABLE:
        # Return mock historical data
        now = datetime.now()
        return jsonify([
            {"recorded_at": (now - timedelta(days=5)).isoformat(), "accuracy": 0.75, "avg_response_time": 18},
            {"recorded_at": (now - timedelta(days=4)).isoformat(), "accuracy": 0.80, "avg_response_time": 16},
            {"recorded_at": (now - timedelta(days=3)).isoformat(), "accuracy": 0.82, "avg_response_time": 15},
            {"recorded_at": (now - timedelta(days=2)).isoformat(), "accuracy": 0.85, "avg_response_time": 14},
            {"recorded_at": (now - timedelta(days=1)).isoformat(), "accuracy": 0.85, "avg_response_time": 15}
        ])
    
    try:
        conn = get_connection()
        if not conn:
            return jsonify([])
        
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT student_id, avg_response_time, avg_attempts, accuracy, cluster, recommendation, recorded_at FROM student_behavior_history WHERE student_id=%s ORDER BY recorded_at", (student_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(rows)
    except:
        return jsonify([])

@web.route("/add-edge", methods=["POST"])
def add_edge():
    from flask import request
    data = request.json
    frm = data.get('from')
    to = data.get('to')
    cost = data.get('cost')
    if not frm or not to or cost is None:
        return jsonify({'status':'error','message':'from,to,cost required'}),400
    
    if not DB_AVAILABLE:
        return jsonify({'status':'ok','message':'Demo mode: edge noted'})
    
    try:
        conn = get_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO astar_edges (node_from,node_to,cost) VALUES (%s,%s,%s)", (frm,to,cost))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'status':'ok'})
    except:
        pass
    
    return jsonify({'status':'ok'})

@web.route("/all-data")
def all_data():
    if not DB_AVAILABLE:
        # Return mock data when database is unavailable
        now = datetime.now()
        behavior_history = [
            {
                "student_id": "24KQ1A5444",
                "avg_response_time": 15.2,
                "avg_attempts": 1.8,
                "accuracy": 0.85,
                "cluster": 0,
                "recommendation": "Advanced challenge questions recommended",
                "recorded_at": (now - timedelta(days=5)).isoformat()
            },
            {
                "student_id": "24KQ1A5445",
                "avg_response_time": 18.5,
                "avg_attempts": 2.1,
                "accuracy": 0.78,
                "cluster": 1,
                "recommendation": "Practice timed quizzes",
                "recorded_at": (now - timedelta(days=3)).isoformat()
            }
        ]
        logs = [
            {"student_id": "24KQ1A5444", "response_time": 14.5, "marks": 85, "logged_at": (now - timedelta(days=1)).isoformat()},
            {"student_id": "24KQ1A5445", "response_time": 19.2, "marks": 78, "logged_at": (now - timedelta(days=2)).isoformat()}
        ]
        marks = [85, 78, 92, 88, 76, 82, 90, 79]
        return jsonify({"behavior_history": behavior_history, "logs": logs, "marks": marks})
    
    try:
        conn = get_connection()
        if not conn:
            return jsonify({"behavior_history": [], "logs": [], "marks": []})
        
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM student_behavior_history ORDER BY student_id, recorded_at")
        history = cur.fetchall()
        cur.execute("SELECT * FROM student_logs ORDER BY student_id LIMIT 100")
        logs = cur.fetchall()
        cur.execute("SELECT marks FROM student_logs ORDER BY marks DESC")
        marks = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"behavior_history": history, "logs": logs, "marks": marks})
    except:
        return jsonify({"behavior_history": [], "logs": [], "marks": []})

@web.route("/marks")
def marks():
    if not DB_AVAILABLE:
        return jsonify([85, 78, 92, 88, 76, 82, 90, 79, 81, 86, 75, 89, 84, 77, 91])
    
    try:
        conn = get_connection()
        if not conn:
            return jsonify([85, 78, 92, 88, 76, 82, 90, 79])
        
        cur = conn.cursor()
        cur.execute("SELECT marks FROM student_logs")
        rows = cur.fetchall()
        values = [r[0] for r in rows if r[0] is not None]
        cur.close()
        conn.close()
        return jsonify(values)
    except:
        return jsonify([85, 78, 92, 88, 76, 82, 90, 79])

@web.route("/ask-ai", methods=["POST"])
def ask_ai():
    from flask import request

    try:
        conversation = request.json.get("conversation") or []
        print("/ask-ai received conversation", conversation)
        # special handling: A* commands
        if conversation and conversation[-1]["role"]=="user":
            msg = conversation[-1]["content"].strip()
            if msg.startswith("astar "):
                parts = msg.split()
                # keep backward compatibility
                if len(parts) >= 4 and parts[2] == 'edges:':
                    start = parts[1]
                    goal = parts[3]
                    edge_list = parts[4:] if len(parts) > 4 else []
                    graph={}
                    for e in edge_list:
                        try:
                            nodes,cost = e.split(":")
                            a,b = nodes.split("-")
                            cost=float(cost)
                            graph.setdefault(a,[]).append((b,cost))
                            graph.setdefault(b,[]).append((a,cost))
                        except:
                            continue
                    path = a_star(graph, start, goal)
                    reply = f"A* path from {start} to {goal}: {path}"
                    print("/ask-ai sending astar reply", reply)
                    return jsonify({"reply": reply})
            elif msg.startswith("astar-user "):
                parts = msg.split(maxsplit=1)
                if len(parts) >= 2:
                    student_id = parts[1]
                    history = []
                    marks = []
                    
                    if DB_AVAILABLE:
                        try:
                            conn = get_connection()
                            if conn:
                                cur = conn.cursor(dictionary=True)
                                cur.execute("SELECT * FROM student_behavior_history WHERE student_id=%s ORDER BY recorded_at DESC LIMIT 5", (student_id,))
                                history = cur.fetchall()
                                cur.execute("SELECT marks FROM student_logs WHERE student_id=%s ORDER BY marks DESC", (student_id,))
                                marks = cur.fetchall()
                                cur.close()
                                conn.close()
                        except:
                            pass
                    else:
                        # Demo data
                        history = [{
                            "student_id": student_id,
                            "accuracy": 0.85,
                            "avg_response_time": 15.2,
                            "cluster": 0,
                            "recommendation": "Advanced challenge questions recommended"
                        }]
                        marks = [{"marks": 85}]
                    
                    if history or marks:
                        reply = f"User {student_id} data:\n"
                        if history:
                            reply += f"Recent behavior ({len(history)} records):\n"
                            for h in history:
                                reply += f"  Accuracy: {h.get('accuracy',0)*100:.1f}%, Response: {h.get('avg_response_time',0):.1f}s\n"
                        if marks:
                            reply += f"Marks ({len(marks)} found): "
                            mark_vals = [str(m.get('marks',0)) for m in marks]
                            reply += ", ".join(mark_vals[:10]) + "\n"
                    else:
                        reply = f"No data found for user {student_id}"
                    print("/ask-ai sending astar-user reply", reply)
                    return jsonify({"reply": reply})

            elif msg.startswith("astar-user"):
                parts = msg.split()
                if len(parts) >= 2:
                    student_id = parts[1]
                    history = []
                    logs = []
                    
                    if DB_AVAILABLE:
                        try:
                            conn = get_connection()
                            if conn:
                                cur = conn.cursor(dictionary=True)
                                cur.execute("SELECT * FROM student_behavior_history WHERE student_id=%s", (student_id,))
                                history = cur.fetchall()
                                cur.execute("SELECT * FROM student_logs WHERE student_id=%s LIMIT 10", (student_id,))
                                logs = cur.fetchall()
                                cur.close()
                                conn.close()
                        except:
                            pass
                    else:
                        history = [{"accuracy": 0.85, "avg_response_time": 15.2}]
                        logs = []
                    
                    reply = f"Found {len(history)} history records and {len(logs)} log records for student {student_id}"
                    if history:
                        reply += f". Latest: accuracy={history[-1].get('accuracy', 'N/A')}, response_time={history[-1].get('avg_response_time', 'N/A')}"
                    return jsonify({"reply": reply})
        reply = ask_ai_question(conversation)
        print("/ask-ai sending reply", reply)
        return jsonify({"reply": reply})
    except Exception as e:
        print("/ask-ai error", e)
        return jsonify({"reply": "[Server error: {}]".format(str(e))}), 500

if __name__ == "__main__":
    web.run(debug=True)