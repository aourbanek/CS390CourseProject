# CS390CourseProject
This is where the code will live for my group's course project in Bradley University's CS 390 Intro to SE course.

Our product, in theory, would be an online photo management app, similar in interface to Google Drive/etc, but with organizational systems better suited for a photographer's portfolio or similar use cases. Primarily, use of a tagging system, which has advantages over a traditional file directory structure.

However, given the limited time available in the course, actual design and prototyping for any live product features will be [tentatively] limited to the file uploading process, including interacting with a device's native file management system and adding to the uploaded item: tags, a name, description, and any other metadata we find applicable.

### Installation / Running
- Download fullCS390prototype "root" folder
- Open VS Code (developed in version 1.112.0) with the Python extension installed https://marketplace.visualstudio.com/items?itemName=ms-python.python
- Within a powershell terminal from the "root" folder:
  - Run `python -m venv .venv` to create a Python virtual environment
  - Activate the virtual environment using `.\.venv\Scripts\Activate` (Powershell's Execution Policy may need to be changed to allow the script)
  - Install Flask using `pip install flask`
  - Install required libraries for AI tagging using `pip install torch transformers pillow`
  - Install NLTK using `pip install nltk` (improves auto-tagging)
- Run app.py

### Structure
```
CS390prototype/
├── photo_app/                     # Parent folder for actual source code
│   ├── static/                    # Style resources for HTML to reference
│   │   ├── css/
│   │   │   └── index.css
│   │   └── fonts/
│   │       ├── APompadour.ttf
│   │       └── APompadourBold.ttf
│   ├── templates/
│   │   └── index.html/            # Main UI display
│   ├── uploads/                   # Uploaded files stored here (excluding additional user-added data included/stored in database.db; empty by default)
│   ├── app.py                     # Main app driver
│   └── database.db                # Data about uploaded items stored here
└── requirements.txt               # Packages auto-installed by `npm install`
README.md                          # Project documentation
```
