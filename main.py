from flask import Flask, request, jsonify
from transformers import pipeline

# Load the Hugging Face model
classifier = pipeline(
    "sentiment-analysis",
    model="lk1307/love_model",
    token="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",
    framework="pt"  # Force PyTorch
)

# Initialize the Flask app
app = Flask(__name__)

# Define a route for sentiment analysis
@app.route("/predict", methods=["POST"])
def predict():
    # Get the input text from the JSON request
    data = request.get_json()
    user_input = data.get("text")

    if not user_input:
        return jsonify({"error": "Text is required"}), 400
    
    # Get sentiment analysis result
    result = classifier(user_input)
    
    # Return the result as JSON
    return jsonify(result)

# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
