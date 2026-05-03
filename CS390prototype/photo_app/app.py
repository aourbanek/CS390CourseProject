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
DATABASE_PATH = os.path.join(BASE_DIR, 'database.db')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'avif'}

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


def generate_tags(image_path):
    image = Image.open(image_path).convert("RGB")

    inputs = processor(image, return_tensors="pt")

    out = model.generate(**inputs)
    caption = processor.decode(out[0], skip_special_tokens=True)

    words = caption.lower().replace(".", "").split()

    stop_words = {"a", "an", "the", "is", "on", "in", "at", "with", "and", "of"}

    tags = [w for w in words if w not in stop_words]

    tags = list(dict.fromkeys(tags))

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
            user_tags = user_tags_list[i].strip() if i < len(user_tags_list) else ''

            if user_tags:
                user_tag_list = [
                    tag.strip() for tag in user_tags.split(',')
                    if tag.strip()
                ]

                generated_tag_list = [
                    tag.strip() for tag in generated_tags.split(',')
                    if tag.strip()
                ]

                combined_tags = user_tag_list + [
                    tag for tag in generated_tag_list
                    if tag not in user_tag_list
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
    tags = request.form['tags']

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