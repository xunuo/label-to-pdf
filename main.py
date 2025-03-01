from flask import Flask, request, send_file
from PyPDF2 import PdfReader, PdfWriter
import io
import zipfile

app = Flask(__name__)

# Route to merge PDFs
@app.route('/')
def home():
    return 'Welcome to the PDF Manipulation API!'
@app.route('/merge_pdfs', methods=['POST'])
def merge_pdfs():
    files = request.files.getlist('files')  # Multiple files upload
    writer = PdfWriter()

    # Add pages from all files to the writer
    for file in files:
        reader = PdfReader(file)
        for page in reader.pages:
            writer.add_page(page)

    # Save output to in-memory buffer
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name='merged.pdf', mimetype='application/pdf')

# Route to split a PDF
@app.route('/split_pdf_chunks', methods=['POST'])
def split_pdf_chunks():
    file = request.files['file']  # Single PDF file
    chunk_size = int(request.form.get('chunk_size', 1))  # Default chunk size is 20 pages

    reader = PdfReader(file)
    total_pages = len(reader.pages)
    chunks = []
    
    # Split the PDF into chunks
    for start in range(0, total_pages, chunk_size):
        writer = PdfWriter()
        end = min(start + chunk_size, total_pages)  # Handle the last chunk
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        
        # Save each chunk to an in-memory buffer
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        chunks.append((f'chunk_{start // chunk_size + 1}.pdf', output))

    # Create a ZIP file with all chunks
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        for filename, chunk in chunks:
            zip_file.writestr(filename, chunk.read())
    zip_buffer.seek(0)

    # Return the ZIP file
    return send_file(zip_buffer, as_attachment=True, download_name='pdf_chunks.zip', mimetype='application/zip')


if __name__ == '__main__':
    app.run()
