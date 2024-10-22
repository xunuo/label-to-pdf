import torch
import torch.nn as nn
import torch.nn.functional as F
from flask import Flask, request, render_template, jsonify
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
from scipy.signal import butter, filtfilt
import matplotlib
matplotlib.use('Agg')  # Use 'Agg' backend for matplotlib to avoid GUI issues

app = Flask(__name__)

# Define the model
class Anomaly_Classifier(nn.Module):
    def __init__(self, input_size, num_classes):
        super(Anomaly_Classifier, self).__init__()
        self.conv = nn.Conv1d(in_channels=input_size, out_channels=32, kernel_size=5, stride=1)
        self.conv_pad = nn.Conv1d(in_channels=32, out_channels=32, kernel_size=5, stride=1, padding=2)
        self.maxpool = nn.MaxPool1d(kernel_size=5, stride=2)
        
        self.flattened_size = None
        
        self.dense1 = nn.Linear(32 * 8, 32)
        self.dense2 = nn.Linear(32, 32)
        self.dense_final = nn.Linear(32, num_classes)
        self.softmax = nn.LogSoftmax(dim=1)

    def forward(self, x):
        residual = self.conv(x)
        x = F.relu(self.conv_pad(residual))
        x = self.conv_pad(x)
        x += residual
        x = F.relu(x)
        residual = self.maxpool(x)
        
        x = F.relu(self.conv_pad(residual))
        x = self.conv_pad(x)
        x += residual
        x = F.relu(x)
        residual = self.maxpool(x)
        
        x = F.relu(self.conv_pad(residual))
        x = self.conv_pad(x)
        x += residual
        x = F.relu(x)
        residual = self.maxpool(x)
        
        x = F.relu(self.conv_pad(residual))
        x = self.conv_pad(x)
        x += residual
        x = F.relu(x)
        x = self.maxpool(x)
        
        if self.flattened_size is None:
            self.flattened_size = x.view(x.size(0), -1).size(1)
            self.dense1 = nn.Linear(self.flattened_size, 32)
        
        x = x.view(x.size(0), -1)
        x = F.relu(self.dense1(x))
        x = F.relu(self.dense2(x))
        x = self.softmax(self.dense_final(x))
        return x

# Load the model
anom_classifier = Anomaly_Classifier(input_size=1, num_classes=5)
anom_classifier.load_state_dict(torch.load('Dev Process\\model\\anom_classifier.pth', map_location=torch.device('cpu'), weights_only=True))
anom_classifier.eval()

# Bandpass filter (for noise reduction)
def butter_bandpass(lowcut, highcut, fs, order=5):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return b, a

def bandpass_filter(signal, lowcut=0.5, highcut=40.0, fs=256, order=4):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = filtfilt(b, a, signal)
    return y

def preprocess_ecg_signal(ecg_signal, target_length=256):
    # Ensure the input is a valid 1D array
    ecg_signal = np.asarray(ecg_signal, dtype=np.float32)
    
    # Step 1: Apply bandpass filtering to reduce noise
    fs = target_length  # Assuming the target length is the sampling frequency
    ecg_signal = bandpass_filter(ecg_signal, lowcut=0.5, highcut=40.0, fs=fs)
    
    # Step 2: Adjust signal length to the target length
    if len(ecg_signal) > target_length:
        ecg_signal = ecg_signal[:target_length]
    elif len(ecg_signal) < target_length:
        padding = target_length - len(ecg_signal)
        ecg_signal = np.pad(ecg_signal, (0, padding), 'constant')
    
    # Step 3: Normalize the signal (mean-centered, unit variance)
    ecg_signal -= np.mean(ecg_signal)  # Zero-center the signal
    ecg_signal /= np.std(ecg_signal)   # Scale to unit variance
    
    # Convert to tensor of shape (1, 1, target_length)
    ecg_tensor = torch.tensor(ecg_signal, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
    
    return ecg_tensor

# Improved post-processing function
def post_process_prediction(prediction, probability, class_labels, threshold):
    predicted_label = class_labels.get(prediction, "Unknown Beat")

    # If below the threshold, assign as unknown beat
    if probability < threshold:
        return "Unknown Beat"
    
    # Adjust rules based on observed prediction behavior
    if predicted_label == "Premature Ventricular Beat" and probability < 0.6:
        return "Unknown Beat"
    
    if predicted_label == "Fusion Beat" and probability < 0.7:
        return "Unknown Beat"
    
    if predicted_label == "Supra Ventricular Premature Beat" and probability < 0.5:
        return "Unknown Beat"
    
    return predicted_label

def plot_ecg_signal(ecg_signal, row_index, prediction_label, probability):
    plt.figure(figsize=(10, 4))
    plt.plot(ecg_signal)
    plt.title(f'ECG Signal - Row {row_index}: {prediction_label} ({probability:.2f}%)')
    plt.xlabel('Time')
    plt.ylabel('Amplitude')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()

    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return f"data:image/png;base64,{image_base64}"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/prediction')
def prediction():
    return render_template('prediction.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/predict', methods=['POST'])
def predict():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        df = pd.read_csv(file)
        results = []

        # Set a more lenient confidence threshold
        threshold = 0.5

        class_labels = {
            0: 'Normal Heartbeat',
            1: 'Supra Ventricular Premature Beat',
            2: 'Premature Ventricular Beat',
            3: 'Fusion Beat',
            4: 'Unknown Beat'
        }

        for index, row in df.iterrows():
            # Ensure valid ECG signal format and shape
            ecg_signal = np.array(row, dtype=np.float32)
            
            if ecg_signal.size == 0:
                continue  # Skip empty rows

            ecg_tensor = preprocess_ecg_signal(ecg_signal, target_length=256)

            with torch.no_grad():
                prediction = anom_classifier(ecg_tensor)

            predicted_class = prediction.argmax().item()
            predicted_probability = torch.exp(prediction[0][predicted_class]).item()

            # Apply post-processing rule with enhanced logic
            prediction_label = post_process_prediction(predicted_class, predicted_probability, class_labels, threshold)

            probability = predicted_probability * 100

            ecg_plot_url = plot_ecg_signal(ecg_signal, index, prediction_label, probability)

            results.append({
                'index': index,
                'prediction': prediction_label,
                'probability': round(probability, 2),
                'ecg_plot_url': ecg_plot_url
            })

        return jsonify(results)

    except pd.errors.EmptyDataError:
        return jsonify({'error': 'Empty CSV file'}), 400
    except Exception as e:
        print("Error:", str(e))
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
