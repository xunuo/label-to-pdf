from flask import Flask, request, jsonify
import tensorflow as tf
import pickle
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

# Load model dan tokenizer
model = tf.keras.models.load_model('multilabel_model.h5')
with open('tokenizer.pkl', 'rb') as f:
    tokenizer = pickle.load(f)

# Load data wisata (pastikan file Jawa.xlsx sudah ada)
df = pd.read_excel('Jawa.xlsx')

max_len = 50
all_labels = ['alam', 'buatan', 'budaya', 'religi', 'edukasi']

def predict_labels(text):
    seq = tokenizer.texts_to_sequences([text])
    padded = tf.keras.preprocessing.sequence.pad_sequences(seq, maxlen=max_len)
    preds = model.predict(padded)[0]
    labels_bin = {label: int(preds[i] >= 0.5) for i, label in enumerate(all_labels)}
    labels_prob = {label: float(preds[i]) for i, label in enumerate(all_labels)}
    return labels_bin, labels_prob

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def recommend_places(user_province, user_labels, user_description, df, top_n=10):
    filtered_df = df[df['province'].str.lower() == user_province.lower()]
    if filtered_df.empty:
        return {"error": "Maaf, tidak ada tempat di provinsi tersebut."}

    selected_labels = [label for label, val in user_labels.items() if val == 1]
    if not selected_labels:
        return {"error": "Mohon pilih minimal satu tipe wisata."}

    mask = filtered_df[selected_labels].sum(axis=1) > 0
    filtered_df = filtered_df[mask]
    if filtered_df.empty:
        return {"error": "Maaf, tidak ada tempat dengan tipe wisata tersebut di provinsi itu."}

    # Gabungkan place_name dan deskripsi jadi satu string untuk setiap baris
    combined_text = (filtered_df['place_name'] + ' ' + filtered_df['deskripsi']).tolist()

    # Tambahkan user_description sebagai query terakhir
    corpus_with_query = combined_text + [user_description]

    # TF-IDF vectorization dan cosine similarity
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(corpus_with_query)

    cosine_sim = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()
    top_indices = cosine_sim.argsort()[::-1][:top_n]

    recommendations = []
    for idx in top_indices:
        place = filtered_df.iloc[idx]
        recommendations.append({
            'place_name': place['place_name'],
            'province': place['province'],
            'deskripsi': place['deskripsi'],
            'similarity_score': float(cosine_sim[idx])
        })

    return recommendations


@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json
    user_province = data.get('province', '').strip()
    user_description = data.get('description', '').strip()
    user_selected_labels = data.get('selected_labels', [])  # list of label strings

    # Validasi minimal input
    if not user_province or not user_description:
        return jsonify({"error": "Province and description must be provided."}), 400

    # Buat dict label binary dari input client
    selected_labels = {label: 1 if label in user_selected_labels else 0 for label in all_labels}

    # Prediksi label dari deskripsi user (optional)
    predicted_labels_bin, predicted_labels_prob = predict_labels(user_description)

    # Gunakan label dari input client untuk rekomendasi
    result = recommend_places(user_province, selected_labels, user_description, df)

    # Jika ada error dari recommend_places
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 404

    return jsonify({
        "input_labels": selected_labels,
        "predicted_labels_prob": predicted_labels_prob,
        "recommendations": result
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
