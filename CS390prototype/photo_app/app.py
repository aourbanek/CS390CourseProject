from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
import sqlite3
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Creates upload folder photo_app\uploads\ if not already present
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # "Clears" db from previous tests
    c.execute('''DROP TABLE IF EXISTS photos''')
    # In this prototype, tags is just a TEXT value. In theory, tags would create
    # a relation between the file and one or multiple tags in a "tags" table
    # that SQL queries could be ran on to filter files by their tags.
    c.execute('''
        CREATE TABLE IF NOT EXISTS photos (
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

# provides photo data for HTML to display at bottom of page
@app.route('/')
def index():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM photos")
    photos = c.fetchall()
    conn.close()
    return render_template('index.html', photos=photos)

# saves uploaded file & data to folder and records that in database
@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    name = request.form['name']
    description = request.form['description']
    tags = request.form['tags']

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute(
            "INSERT INTO photos (filename, name, description, tags) VALUES (?, ?, ?, ?)",
            (filename, name, description, tags)
        )
        conn.commit()
        conn.close()

    return redirect(url_for('index'))

#edit
@app.route('/edit/<int:id>')
def edit(id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("SELECT * FROM photos WHERE id = ?", (id,))
    photo = c.fetchone()

    conn.close()
    return render_template('edit.html', photo=photo)

@app.route('/delete/<int:id>')
def delete(id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    #get filename
    c.execute("SELECT filename FROM photos WHERE id = ?", (id,))
    photo = c.fetchone()

    if photo:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], photo[0])

        # Delete file from uploads
        if os.path.exists(filepath):
            os.remove(filepath)

        # Delete from database
        c.execute("DELETE FROM photos WHERE id = ?", (id,))
        conn.commit()

    conn.close()
    return redirect(url_for('index'))

#debug
print("DELETE ROUTE HIT:", id)

#save changes
@app.route('/update/<int:id>', methods=['POST'])
def update(id):
    name = request.form['name']
    description = request.form['description']
    tags = request.form['tags']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("""
        UPDATE photos
        SET name = ?, description = ?, tags = ?
        WHERE id = ?
    """, (name, description, tags, id))

    conn.commit()
    conn.close()

    return redirect(url_for('index'))


# Supports "Open Image in new tab" browser action
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/index.css')
def serve_css():
    return send_from_directory(BASE_DIR, 'index.css')

if __name__ == '__main__':
    app.run(debug=True)
