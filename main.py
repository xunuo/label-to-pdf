from flask import Flask,jsonify
import psycopg2
import json
from datetime import datetime
import model
from flask_apscheduler import APScheduler
from chinatech_data import Chinamain
from Globaltech_data import Globalmain
app = Flask(__name__)
DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "9740377549",
    "host": "localhost",
    "port": 5432
}
Indices = {"GlobalTech":0,"ChinaTech":0}
PageCount = {"GlobalTech":15,"ChinaTech":15}
BaseUrls = {"GlobalTech":"https://techcrunch.com/latest/","ChinaTech":"https://www.chinadaily.com.cn/business/tech"}

@app.route('/get-data/<tech_type>',methods=['GET'])
def get_data(tech_type):
  try:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print(tech_type)
    valid_tables = {"GlobalTech", "ChinaTech"}
    if tech_type not in valid_tables:
      raise ValueError("Invalid table name.")
    cur.execute(f"SELECT count(*) FROM {tech_type};")
    row_count = cur.fetchone()[0]
    current_idx = Indices.get(tech_type,0)
    
    cur.execute(f"SELECT metadata, content FROM {tech_type} OFFSET {current_idx} LIMIT 1;")
    res = cur.fetchone()
    Indices[tech_type] = (current_idx + 1)%row_count
    cur.close()
    conn.close()
    metadata,content = res
    summary = model.summarize_text(content)
    title = model.generate_title(summary)
    description = model.generate_description(summary)
    title = title
    description = description
    data ={
       'author' : metadata.get('author','Unknown'),
       'updated-time' : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
       'url': metadata.get('url'),
       'title' : title,
       'description' : (",").join(description.split('\n')),
       'summary' : summary,
    }
    print(description)
    return jsonify(data)
  except Exception as e:
    return jsonify({"error":str(e)}),500
# job function
def scheduleUpdate():
  Chinaurl = f"{BaseUrls['ChinaTech']}/page_{PageCount['ChinaTech']}.html"
  Globalurl = f"{BaseUrls['GlobalTech']}page/{PageCount['GlobalTech']}/"
  Globalmain(url=Globalurl)
  Chinamain(url=Chinaurl)
  PageCount["GlobalTech"] += 1
  PageCount["ChinaTech"] += 1

scheduler = APScheduler()
scheduler.add_job(id='UpdateDBs',func=scheduleUpdate,trigger = 'interval',hours = 1)
scheduler.init_app(app)
scheduler.start()
if __name__ == '__main__':
    app.run(debug=True, port=9000)
