from flask import Flask, render_template, request, send_file
import os
import re
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from PyPDF2 import PdfReader

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

# Preprocess image for better OCR accuracy
def preprocess_image(file_path):
    img = Image.open(file_path)
    img = img.convert('L')  # Convert to grayscale
    img = img.filter(ImageFilter.MedianFilter())  # Reduce noise
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2)  # Increase contrast
    return img

# Extract text using Tesseract with custom configs
def extract_text_from_image(file_path):
    img = preprocess_image(file_path)
    custom_config = r'--oem 3 --psm 6'  # OCR Engine mode + page segmentation mode
    text = pytesseract.image_to_string(img, config=custom_config)
    return text.strip()

# Extract text from PDF
def extract_text_from_pdf(file_path):
    text = ""
    pdf_reader = PdfReader(file_path)
    for page in pdf_reader.pages:
        extracted_text = page.extract_text()
        if extracted_text:
            text += extracted_text + "\n"
    return text.strip()

# Improved email extraction regex
def extract_emails(text):
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
    return email_pattern.findall(text)

# Extract dates
def extract_dates(text):
    return re.findall(r'\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}\b|\b\d{4}\b', text)

# Extract amounts
def extract_amounts(text):
    return re.findall(r'\b\d+(?:[.,]\d+)?\b', text)

# Categorize amounts into groups
def categorize_amounts(amounts):
    structured_data = {"phone_numbers": [], "cgpas": [], "years": [], "other": []}
    for amount in amounts:
        if re.match(r'^\d{10}$', amount):  # phone numbers
            structured_data['phone_numbers'].append(amount)
        elif re.match(r'^\d{1,2}\.\d{1,2}$', amount):  # CGPA
            structured_data['cgpas'].append(amount)
        elif re.match(r'^(19|20)\d{2}$', amount):  # Years
            structured_data['years'].append(amount)
        else:
            structured_data['other'].append(amount)
    return structured_data

@app.route('/extract_text', methods=['POST'])
def extract_text():
    if 'file' not in request.files:
        return "No file part"
    file = request.files['file']
    if file.filename == '':
        return "No selected file"
    
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    
    # Extract text
    if file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        text = extract_text_from_image(file_path)
    elif file.filename.lower().endswith('.pdf'):
        text = extract_text_from_pdf(file_path)
    else:
        return "Unsupported file type"

    # Extract structured data
    emails = extract_emails(text)
    dates = extract_dates(text)
    amounts = extract_amounts(text)
    categorized_amounts = categorize_amounts(amounts)

    # Save results
    result_file = os.path.join(RESULT_FOLDER, 'extracted_text.txt')
    with open(result_file, 'w', encoding='utf-8') as f:
        f.write('Extracted Text:\n')
        f.write(text + '\n\n')
        f.write('Emails:\n' + '\n'.join(emails) + '\n\n')
        f.write('Dates:\n' + '\n'.join(dates) + '\n\n')
        f.write('Phone Numbers:\n' + '\n'.join(categorized_amounts['phone_numbers']) + '\n\n')
        f.write('CGPAs:\n' + '\n'.join(categorized_amounts['cgpas']) + '\n\n')
        f.write('Years:\n' + '\n'.join(categorized_amounts['years']) + '\n\n')
        f.write('Other Amounts:\n' + '\n'.join(categorized_amounts['other']) + '\n\n')

    return render_template('result.html', text=text, emails=emails, dates=dates, categorized_amounts=categorized_amounts, filename='extracted_text.txt')

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(RESULT_FOLDER, filename), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
