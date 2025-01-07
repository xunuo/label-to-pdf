from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# In-memory storage for simplicity, use a database in production
articles = []

@app.route('/data', methods=['GET'])
def get_articles():
    return jsonify(articles)

@app.route('/data', methods=['POST'])
def add_article():
    article = request.json
    if not any(a['Title'] == article['Title'] for a in articles):
        articles.append(article)
        return jsonify(article), 201
    return jsonify({"message": "Article already exists"}), 409


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
