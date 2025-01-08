import nest_asyncio
from threading import Thread
from flask import Flask, request, jsonify, render_template
from tensorflow.keras.models import load_model
from PIL import Image
import numpy as np
import os

# Apply nest_asyncio to allow Flask to work in a Jupyter notebook environment
nest_asyncio.apply()

# Initialize the Flask application
app = Flask(__name__)

# Path to the trained model
MODEL_PATH = 'final_model.h5'

# Load the Keras model
model = load_model(MODEL_PATH)

# Define a folder for uploaded files
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Create the folder if it doesn't exist
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Function to preprocess the uploaded image
def preprocess_image(image):
    """
    Preprocess the image for the model.
    - Convert the image to grayscale
    - Resize the image
    - Normalize the pixel values
    """
    # Convert the image to grayscale (mode 'L')
    image = image.convert('L')  
    
    # Resize the image to the expected input size (224x224 for most CNN models)
    image = image.resize((224, 224))  
    
    # Convert the image to a NumPy array
    image = np.array(image)
    
    # Normalize the pixel values (scale from 0 to 1)
    image = image / 255.0  
    
    # Add an extra dimension for the channel (grayscale image has 1 channel)
    image = np.expand_dims(image, axis=-1)  
    
    # Add batch dimension for model input
    image = np.expand_dims(image, axis=0)  
    
    return image

# Route to serve the homepage
@app.route('/', methods=['GET'])
def home():
    """
    Renders a simple upload page for testing.
    """
    return render_template('index.html')

# Route to handle file uploads and predictions
@app.route('/classify', methods=['POST'])
def classify():
    """
    Endpoint to classify uploaded ECG images as normal, abnormal, history of MI, or MI.
    - Accepts a file upload.
    - Preprocesses the file.
    - Returns the classification result.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        # Save the file to the upload folder
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # Open and preprocess the image
        image = Image.open(file_path).convert('RGB')  # Ensure the image is in RGB format
        preprocessed_image = preprocess_image(image)

        # Predict using the model
        prediction = model.predict(preprocessed_image)
        
        # Debugging information: print the prediction array
        print(f"Model prediction raw output: {prediction}")

        # Map the prediction to the correct label
        class_labels = ['normal', 'abnormal', 'history of MI', 'MI']
        
        # Get the class with the highest probability
        predicted_class = class_labels[np.argmax(prediction)]  # Get the class with highest probability
        
        # Return the classification result
        return jsonify({'file': file.filename, 'prediction': predicted_class})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Main entry point for running the app in a separate thread (for Jupyter notebook compatibility)
def run_app():
    app.run(host='0.0.0.0', port=5004, debug=True, use_reloader=False)

if __name__ == '__main__':
    # Run Flask in a separate thread to avoid blocking the Jupyter notebook
    thread = Thread(target=run_app)
    thread.start()

