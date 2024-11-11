from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3

app = Flask(__name__)

# Kết nối SQLite
def get_db_connection():
    conn = sqlite3.connect('db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

# Tạo bảng người chơi nếu chưa có
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            score INTEGER NOT NULL DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Trang chính
@app.route('/')
def index():
    return render_template('index.html')

# Chế độ đấu 2 người
@app.route('/player-vs-player')
def player_vs_player():
    return render_template('player_vs_player.html')

# Chế độ đấu với máy
@app.route('/player-vs-ai', methods=['GET', 'POST'])
def player_vs_ai():
    if request.method == 'POST':
        name = request.form.get('name')
        if not name:
            return redirect(url_for('player_vs_ai'))
        
        conn = get_db_connection()
        player = conn.execute('SELECT * FROM players WHERE name = ?', (name,)).fetchone()
        
        if player:
            return render_template('player_vs_ai.html', name=player['name'], score=player['score'])
        else:
            conn.execute('INSERT INTO players (name, score) VALUES (?, ?)', (name, 0))
            conn.commit()
            return render_template('player_vs_ai.html', name=name, score=0)
    return render_template('enter_name.html')

# Cập nhật điểm người chơi sau khi thắng
@app.route('/update_score', methods=['POST'])
def update_score():
    name = request.json.get('name')
    conn = get_db_connection()
    conn.execute('UPDATE players SET score = score + 1 WHERE name = ?', (name,))
    conn.commit()
    conn.close()
    return jsonify(success=True)

# Bảng xếp hạng
@app.route('/leaderboard')
def leaderboard():
    conn = get_db_connection()
    players = conn.execute('SELECT * FROM players ORDER BY score DESC LIMIT 10').fetchall()
    conn.close()
    return render_template('leaderboard.html', players=players)
    
if __name__ == '__main__':
    app.run(debug=True)
