from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, send_file
import os
import sqlite3
import re
import base64
import mimetypes
from html import escape
from io import BytesIO
from werkzeug.utils import secure_filename

# ======================
# IMAGE AI (BLIP)
# ======================
import torch
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration

# NLP (NLTK for phrase tagging)
import nltk
from nltk import pos_tag, RegexpParser
from nltk.stem import WordNetLemmatizer
# Download required data (first run only)
nltk.download('punkt')
nltk.download('averaged_perceptron_tagger_eng')
nltk.download('wordnet')

lemmatizer = WordNetLemmatizer()

# ======================
# CONFIG
# ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DATABASE_PATH = os.path.join(BASE_DIR, 'database.db')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'avif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = "dev_secret"

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ======================
# LOAD MODEL
# ======================
device = "cuda" if torch.cuda.is_available() else "cpu"

processor = BlipProcessor.from_pretrained(
    "Salesforce/blip-image-captioning-base"
)

model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip-image-captioning-base"
).to(device)

# ======================
# DATABASE
# ======================
def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            name TEXT,
            description TEXT,
            tags TEXT,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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


def clean_and_tokenize(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.split()


def extract_tags_from_caption(caption):
    words = clean_and_tokenize(caption)

    stop_words = {
        "a","an","the","is","are","was","were","be","been","being",
        "on","in","at","with","and","of","to","from","by","for","about",
        "over","under","between","into","through","during","before","after",
        "he","she","it","they","this","that","these","those",
        "his","her","their","its",
        "have","has","had","do","does","did",
        "there","here","which","who","what"
    }

    tagged = pos_tag(words)

# Phrase detection (keeps "santa claus", "living room", etc.)
    grammar = "NP: {<JJ>*<NN.*>+}"
    chunk_parser = RegexpParser(grammar)
    tree = chunk_parser.parse(tagged)

    tags = []

    for subtree in tree:
        if hasattr(subtree, 'label') and subtree.label() == 'NP':
            phrase = " ".join(word for word, pos in subtree)
            tags.append(phrase)
        else:
            word, pos = subtree
            if word not in stop_words and pos.startswith(("NN", "JJ")):
                tags.append(lemmatizer.lemmatize(word))

    # remove duplicates (preserve order)
    tags = list(dict.fromkeys(tags))

    return tags



def get_photo_by_id(id):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM photos WHERE id = ?", (id,))
    photo = c.fetchone()
    conn.close()
    return photo

def generate_tags(image_path):
    image = Image.open(image_path).convert("RGB")

    inputs = processor(image, return_tensors="pt").to(device)

    out = model.generate(**inputs)
    caption = processor.decode(out[0], skip_special_tokens=True)

    tags = extract_tags_from_caption(caption)

    return ", ".join(tags)


# ======================
# ROUTES
# ======================
@app.route('/')
def index():
    sort = request.args.get("sort", "date_desc")
    selected_tag = request.args.get("tag", "")

    if sort == "name_asc":
        order_by = "ORDER BY name COLLATE NOCASE ASC"
    elif sort == "name_desc":
        order_by = "ORDER BY name COLLATE NOCASE DESC"
    elif sort == "date_asc":
        order_by = "ORDER BY date_added ASC"
    else:
        order_by = "ORDER BY date_added DESC"

    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    if selected_tag:
        c.execute(
            f"SELECT * FROM photos WHERE tags LIKE ? {order_by}",
            (f"%{selected_tag}%",)
        )
    else:
        c.execute(f"SELECT * FROM photos {order_by}")

    photos = c.fetchall()

    c.execute("SELECT tags FROM photos")
    tag_rows = c.fetchall()

    conn.close()

    all_tags = []

    for row in tag_rows:
        if row[0]:
            tags = [tag.strip() for tag in row[0].split(",") if tag.strip()]
            all_tags.extend(tags)

    all_tags = sorted(set(all_tags), key=str.lower)

    return render_template(
        "index.html",
        photos=photos,
        sort=sort,
        all_tags=all_tags,
        selected_tag=selected_tag
    )


@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('files')
    names = request.form.getlist('names')
    descriptions = request.form.getlist('descriptions')
    user_tags_list = request.form.getlist('tags')

    if not files or files[0].filename == '':
        flash("No files selected")
        return redirect(url_for('index'))

    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    for i, file in enumerate(files):
        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            name_only, ext = os.path.splitext(original_filename)

            final_filename = original_filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], final_filename)

            counter = 1
            while os.path.exists(filepath):
                final_filename = f"{name_only}_{counter}{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], final_filename)
                counter += 1

            file.save(filepath)

            generated_tags = generate_tags(filepath)

            photo_name = names[i] if i < len(names) else name_only
            description = descriptions[i] if i < len(descriptions) else ''
            user_tags = user_tags_list[i].strip().lower() if i < len(user_tags_list) else ''

            if user_tags:
                user_tag_list = [tag.strip() for tag in user_tags.split(',') if tag.strip()]
                generated_tag_list = [tag.strip() for tag in generated_tags.split(',') if tag.strip()]

                combined_tags = user_tag_list + [
                    tag for tag in generated_tag_list if tag not in user_tag_list
                ]

                tags = ", ".join(combined_tags)
            else:
                tags = generated_tags

            c.execute(
                "INSERT INTO photos (filename, name, description, tags) VALUES (?, ?, ?, ?)",
                (final_filename, photo_name, description, tags)
            )

    conn.commit()
    conn.close()

    return redirect(url_for('index'))


@app.route('/edit/<int:id>')
def edit(id):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM photos WHERE id = ?", (id,))
    photo = c.fetchone()
    conn.close()
    return render_template('edit.html', photo=photo)


@app.route('/delete/<int:id>')
def delete(id):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    c.execute("SELECT filename FROM photos WHERE id = ?", (id,))
    photo = c.fetchone()

    if photo:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], photo[0])

        if os.path.exists(filepath):
            os.remove(filepath)

        c.execute("DELETE FROM photos WHERE id = ?", (id,))
        conn.commit()

    conn.close()
    return redirect(url_for('index'))


@app.route('/update/<int:id>', methods=['POST'])
def update(id):
    name = request.form['name']
    description = request.form['description']
    tags = request.form['tags'].lower()

    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    c.execute("""
        UPDATE photos
        SET name = ?, description = ?, tags = ?
        WHERE id = ?
    """, (name, description, tags, id))

    conn.commit()
    conn.close()

    return redirect(url_for('index'))


@app.route('/export/<int:id>')
def export_share_file(id):
    photo = get_photo_by_id(id)

    if not photo:
        return "Photo not found", 404

    filename = photo[1]
    photo_name = photo[2] or "Shared Photo"
    description = photo[3] or ""
    tags = photo[4] or ""
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(image_path):
        return "Image file not found", 404

    mime_type = mimetypes.guess_type(filename)[0] or "image/jpeg"

    with open(image_path, "rb") as image_file:
        image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

    safe_title = escape(photo_name)
    safe_description = escape(description)
    safe_tags = escape(tags)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_title}</title>
    <style>
        body {{
            margin: 0;
            min-height: 100vh;
            padding: 40px;
            box-sizing: border-box;
            font-family: Arial, sans-serif;
            background: linear-gradient(to bottom, #dcefff 0%, #cfe7ff 45%, #bddcff 100%);
            color: #1f2937;
        }}

        .shared-wrapper {{
            max-width: 1400px;
            margin: auto;
            text-align: center;
        }}

        .shared-image {{
            width: 100%;
            max-height: 82vh;
            object-fit: contain;
            border-radius: 16px;
            border: 3px solid #5da9ff;
            background: white;
            box-shadow: 0 10px 30px rgba(0,0,0,0.12);
            margin-bottom: 25px;
        }}

        .shared-info {{
            background: white;
            border: 2px solid #5da9ff;
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.08);
        }}

        .shared-title {{
            font-size: 2rem;
            font-weight: bold;
            margin-bottom: 12px;
        }}

        .shared-description {{
            margin-bottom: 16px;
            line-height: 1.5;
        }}

        .shared-tags {{
            color: #4b5563;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="shared-wrapper">
        <img class="shared-image" src="data:{mime_type};base64,{image_base64}" alt="{safe_title}">

        <div class="shared-info">
            <div class="shared-title">{safe_title}</div>
            <div class="shared-description">{safe_description}</div>
            <div class="shared-tags">Tags: {safe_tags}</div>
        </div>
    </div>
</body>
</html>"""

    download_name = secure_filename(photo_name) or "shared_photo"
    file_data = BytesIO(html_content.encode("utf-8"))

    return send_file(
        file_data,
        mimetype="text/html",
        as_attachment=True,
        download_name=f"{download_name}_share.html"
    )


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
