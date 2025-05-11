from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from pdf2docx import Converter
from docx2pdf import convert
import tempfile
import uuid
from win32com.client import Dispatch  
import pythoncom
from fpdf import FPDF
from PIL import Image, ImageOps
import fitz  # PyMuPDF
import zipfile
 
# Flask app configuration
app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = './uploads'
CONVERTED_FOLDER = './converted'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)

# Logging Configuration
logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Allowed file types
def allowed_file(filename, file_type):
    if file_type == 'pdf':
        return filename.lower().endswith('.pdf')
    if file_type == 'word':
        return filename.lower().endswith('.docx')
    return False


# ============================
# 🚀 Image to PDF Conversion (Updated for multiple images, rotation, pdf name)
# ============================
@app.route('/convert/img2pdf', methods=['POST'])
def convert_images_to_pdf():
    files = request.files.getlist('images')
    # Remove pdf_name logic, always generate a random name
    # Get rotations as a list of ints, default to 0 if not provided
    rotations = []
    i = 0
    while True:
        rot = request.form.get(f'rotations[{i}]')
        if rot is None:
            break
        try:
            rotations.append(int(rot))
        except Exception:
            rotations.append(0)
        i += 1

    if not files or len(files) == 0:
        logging.error("No images provided in the request")
        return jsonify({'error': 'No images provided'}), 400

    allowed_extensions = {'png', 'jpg', 'jpeg', 'bmp', 'gif'}
    image_paths = []
    images = []
    try:
        # Save images temporarily and open them with PIL
        for idx, file in enumerate(files):
            if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
                logging.error(f"Invalid file type for file: {file.filename}")
                return jsonify({'error': 'Only image files are allowed'}), 400
            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            image_path = os.path.abspath(os.path.join(UPLOAD_FOLDER, filename))
            file.save(image_path)
            image_paths.append(image_path)
            img = Image.open(image_path)
            # Fix orientation using EXIF if present (for camera images)
            img = ImageOps.exif_transpose(img)
            # Apply rotation if specified
            if idx < len(rotations):
                img = img.rotate(-rotations[idx], expand=True)
            # Convert all images to RGB for PDF
            if img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)

        # Save all images as a single PDF with a random name
        pdf_filename = f"{uuid.uuid4().hex}.pdf"
        # Ensure the converted folder path is absolute and matches other endpoints
        converted_folder_abs = os.path.abspath(CONVERTED_FOLDER)
        os.makedirs(converted_folder_abs, exist_ok=True)
        pdf_path = os.path.join(converted_folder_abs, pdf_filename)
        if images:
            images[0].save(pdf_path, save_all=True, append_images=images[1:])
        else:
            return jsonify({'error': 'No valid images to convert'}), 400

        logging.info(f"Images successfully converted to PDF: {pdf_path}")
        return send_file(pdf_path, as_attachment=True, download_name=pdf_filename, mimetype='application/pdf')

    except Exception as e:
        logging.error(f"Error during image to PDF conversion: {str(e)}")
        return jsonify({'error': f'Error during conversion: {str(e)}'}), 500

    finally:
        # Clean up temp images
        for image_path in image_paths:
            if os.path.exists(image_path):
                os.remove(image_path)


# ============================
# 🚀 PDF to Word Conversion
# ============================
@app.route('/pdf-to-word', methods=['POST'])
def pdf_to_word():
    if 'file' not in request.files:
        logging.error("No file part in the request")
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        logging.error("No file selected")
        return jsonify({'error': 'No selected file'}), 400

    if not allowed_file(file.filename, 'pdf'):
        logging.error("Invalid file type")
        return jsonify({'error': 'Only PDF files are allowed'}), 400

    # Save PDF to temp location
    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)
    logging.info(f"PDF uploaded: {pdf_path}")

    try:
        # Convert PDF to Word
        word_filename = os.path.splitext(filename)[0] + '.docx'
        word_path = os.path.join(CONVERTED_FOLDER, word_filename)

        logging.info(f"Converting {pdf_path} to {word_path}")
        cv = Converter(pdf_path)
        cv.convert(word_path, start=0, end=None)
        cv.close()
        logging.info(f"Conversion successful: {word_path}")

        return jsonify({'message': 'Conversion successful', 'file': word_filename}), 200

    except Exception as e:
        logging.error(f"Conversion failed: {str(e)}")
        return jsonify({'error': 'Conversion failed'}), 500


# ============================
# 🚀 Word to PDF Conversion
# ============================
@app.route('/word-to-pdf', methods=['POST'])
def word_to_pdf():
    if 'file' not in request.files:
        logging.error("No file provided in the request")
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        logging.error("No file selected")
        return jsonify({'error': 'No selected file'}), 400

    if not file.filename.lower().endswith('.docx'):
        logging.error(f"Invalid file type for file: {file.filename}")
        return jsonify({'error': 'Only DOCX files are allowed'}), 400

    filename = secure_filename(file.filename)
    word_path = os.path.join(UPLOAD_FOLDER, filename)

    try:
        file.save(word_path)
        logging.info(f"Word document uploaded: {word_path}")

        word_path = os.path.abspath(word_path)
        word_path = word_path.replace("/", "\\")

        pdf_filename = os.path.splitext(filename)[0] + '.pdf'
        pdf_path = os.path.join(CONVERTED_FOLDER, pdf_filename)
        pdf_path = os.path.abspath(pdf_path)
        pdf_path = pdf_path.replace("/", "\\")

        if not os.path.exists(word_path):
            logging.error(f"File not found: {word_path}")
            return jsonify({'error': f"File not found: {word_path}"}), 500

        pythoncom.CoInitialize()
        logging.info("COM interface initialized successfully.")

        word = Dispatch("Word.Application")
        word.Visible = False

        logging.info(f"Opening document: {word_path}")
        doc = word.Documents.Open(word_path)

        logging.info(f"Saving as PDF: {pdf_path}")
        doc.SaveAs(pdf_path, FileFormat=17)
        doc.Close()
        word.Quit()
        logging.info("Word document successfully converted to PDF.")

        if os.path.exists(pdf_path):
            # Return the PDF file directly as a download
            return send_file(pdf_path, as_attachment=True, download_name=pdf_filename, mimetype='application/pdf')
        else:
            logging.error("PDF conversion failed, file not found.")
            return jsonify({'error': 'Conversion failed'}), 500

    except Exception as e:
        logging.error(f"Error during conversion: {str(e)}")
        return jsonify({'error': f'Error during conversion: {str(e)}'}), 500

    finally:
        pythoncom.CoUninitialize()
        logging.info("COM interface uninitialized.")
        if os.path.exists(word_path):
            os.remove(word_path)

# ============================
# 🚀 PDF to Images Conversion
# ============================
@app.route('/pdf-to-images', methods=['POST'])
def pdf_to_images_route():
    if 'file' not in request.files:
        logging.error("No file part in the request")
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        logging.error("No file selected")
        return jsonify({'error': 'No selected file'}), 400

    if not allowed_file(file.filename, 'pdf'):
        logging.error("Invalid file type")
        return jsonify({'error': 'Only PDF files are allowed'}), 400

    # Save PDF to temp location
    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)
    logging.info(f"PDF uploaded: {pdf_path}")

    try:
        # Use absolute path for converted folder (like other endpoints)
        converted_folder_abs = os.path.abspath(CONVERTED_FOLDER)
        os.makedirs(converted_folder_abs, exist_ok=True)

        # Create output folder for images inside converted folder
        base_name = os.path.splitext(filename)[0]
        output_folder = os.path.join(converted_folder_abs, f"{base_name}_images")
        os.makedirs(output_folder, exist_ok=True)
        
        # Convert PDF to images
        doc = fitz.open(pdf_path)
        image_paths = []
        
        zoom = request.form.get('zoom', default=3, type=int)
        
        for i, page in enumerate(doc):
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            image_path = os.path.join(output_folder, f"page_{i+1}.png")
            pix.save(image_path)
            image_paths.append(image_path)
            logging.info(f"Saved image: {image_path}")
        
        # Create a zip file of all images in the converted folder
        zip_filename = f"{base_name}_images.zip"
        zip_path = os.path.join(converted_folder_abs, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for image_path in image_paths:
                zipf.write(image_path, os.path.basename(image_path))
        
        logging.info(f"Created zip file: {zip_path}")
        
        # Return the zip file
        return send_file(
            zip_path,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        logging.error(f"Conversion failed: {str(e)}")
        return jsonify({'error': f'Conversion failed: {str(e)}'}), 500
        
    # finally:
    #     # Clean up the PDF file
    #     if os.path.exists(pdf_path):
    #         os.remove(pdf_path)

# ============================
# 🚀 Download Route
# ============================
@app.route('/download-pdf/<filename>', methods=['GET'])
def download_pdf(filename):
    try:
        file_path = os.path.join(CONVERTED_FOLDER, filename)
        return send_file(file_path, as_attachment=True, download_name=filename, mimetype='application/pdf')
    except Exception as e:
        return jsonify({'error': f'Failed to send file: {str(e)}'}), 500


@app.route('/open-zip/<filename>', methods=['GET'])
def open_zip(filename):
    try:
        zip_path = os.path.join(CONVERTED_FOLDER, filename)
        if not os.path.exists(zip_path) or not zip_path.lower().endswith('.zip'):
            return jsonify({'error': 'ZIP file not found'}), 404

        # List contents of the zip file
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            file_list = zipf.namelist()
        return jsonify({'files': file_list, 'zip': filename}), 200
    except Exception as e:
        return jsonify({'error': f'Failed to open zip: {str(e)}'}), 500


@app.route('/download-from-zip', methods=['GET'])
def download_from_zip():
    zip_name = request.args.get('zip')
    file_name = request.args.get('file')
    if not zip_name or not file_name:
        return jsonify({'error': 'Missing zip or file parameter'}), 400
    zip_path = os.path.join(CONVERTED_FOLDER, zip_name)
    if not os.path.exists(zip_path) or not zip_path.lower().endswith('.zip'):
        return jsonify({'error': 'ZIP file not found'}), 404
    try:
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            if file_name not in zipf.namelist():
                return jsonify({'error': 'File not found in ZIP'}), 404
            # Extract file to temp dir and send
            temp_dir = tempfile.mkdtemp()
            zipf.extract(file_name, temp_dir)
            file_path = os.path.join(temp_dir, file_name)
            return send_file(file_path, as_attachment=True, download_name=file_name)
    except Exception as e:
        return jsonify({'error': f'Failed to extract file: {str(e)}'}), 500

@app.route('/download-zip/<zip_name>', methods=['GET'])
def download_zip(zip_name):
    zip_path = os.path.join(CONVERTED_FOLDER, zip_name)
    if not os.path.exists(zip_path) or not zip_path.lower().endswith('.zip'):
        return jsonify({'error': 'ZIP file not found'}), 404
    try:
        return send_file(zip_path, as_attachment=True, download_name=zip_name, mimetype='application/zip')
    except Exception as e:
        return jsonify({'error': f'Failed to send zip: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
