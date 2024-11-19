from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image, ImageFilter
import io

app = Flask(__name__)
CORS(app)  # Enable CORS for communication with React frontend

@app.route('/apply-filter', methods=['POST'])
def apply_filter():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    
    image_file = request.files['image']
    image = Image.open(image_file)
    
    # Apply a sample filter (e.g., BLUR)
    filtered_image = image.filter(ImageFilter.BLUR)
    
    # Save the filtered image to a BytesIO object
    output = io.BytesIO()
    filtered_image.save(output, format='JPEG')
    output.seek(0)
    
    # Send the processed image back as a response
    return jsonify({"message": "Filter applied successfully!"})

if __name__ == '__main__':
    app.run(debug=True)
