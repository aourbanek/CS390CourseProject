from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import os
import sqlite3
from werkzeug.utils import secure_filename

# ======================
# IMAGE AI (FREE BLIP MODEL)
# ======================
import torch
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration

# ======================
# CONFIG
# ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = "dev_secret"

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ======================
# LOAD MODEL (ONCE)
# ======================
processor = BlipProcessor.from_pretrained(
    "Salesforce/blip-image-captioning-base"
)
model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip-image-captioning-base"
)

# ======================
# DATABASE
# ======================
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('DROP TABLE IF EXISTS photos')

    c.execute('''
        CREATE TABLE photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            name TEXT,
            description TEXT,
            tags TEXT
        )
    ''')

    conn.commit()
    conn.close()

init_db()

# ======================
# HELPERS
# ======================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_tags(image_path):
    image = Image.open(image_path).convert("RGB")

    inputs = processor(image, return_tensors="pt")

    out = model.generate(**inputs)
    caption = processor.decode(out[0], skip_special_tokens=True)

    # convert caption → tags
    words = caption.lower().replace(".", "").split()

    stop_words = {"a", "an", "the", "is", "on", "in", "at", "with", "and", "of"}

    tags = [w for w in words if w not in stop_words]

    # remove duplicates while keeping order
    tags = list(dict.fromkeys(tags))

    return ", ".join(tags)

# ======================
# ROUTES
# ======================
@app.route('/')
def index():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM photos")
    photos = c.fetchall()
    conn.close()
    return render_template('index.html', photos=photos)


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        flash("No file uploaded")
        return redirect(url_for('index'))

    file = request.files['file']
    name = request.form.get('name', '')
    description = request.form.get('description', '')
    user_tags = request.form.get('tags', '').strip()

    if file.filename == '':
        flash("No file selected")
        return redirect(url_for('index'))

    # ONLY IMAGES
    if file and allowed_file(file.filename):

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # AUTO TAGGING
        generated_tags = generate_tags(filepath)

        if user_tags:
            user_tag_list = [tag.strip() for tag in user_tags.split(',') if tag.strip()]
            generated_tag_list = [tag.strip() for tag in generated_tags.split(',') if tag.strip()]
            combined_tags = user_tag_list + [tag for tag in generated_tag_list if tag not in user_tag_list]
            tags = ", ".join(combined_tags)
        else:
            tags = generated_tags

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute(
            "INSERT INTO photos (filename, name, description, tags) VALUES (?, ?, ?, ?)",
            (filename, name, description, tags)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('index'))

    else:
        flash("Only image files allowed")
        return redirect(url_for('index'))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/index.css')
def serve_css():
    return send_from_directory(BASE_DIR, 'index.css')


# ======================
# RUN APP
# ======================
if __name__ == '__main__':
    app.run(debug=True)