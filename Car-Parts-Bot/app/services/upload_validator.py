# app/services/upload_validator.py

from flask import current_app


def validate_reference_file(file) -> None:
    """
    Raises ValueError if file is invalid.
    Does NOT save file.
    """

    if not file:
        raise ValueError("No file uploaded")

    if not file.filename:
        raise ValueError("Empty filename")

    filename = file.filename
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext not in current_app.config["ALLOWED_REFERENCE_EXTENSIONS"]:
        raise ValueError(
            f"Unsupported file type .{ext}. "
            f"Allowed: {', '.join(current_app.config['ALLOWED_REFERENCE_EXTENSIONS'])}"
        )

    # File size check (without reading whole file)
    file.seek(0, 2)  # move to end
    size = file.tell()
    file.seek(0)     # rewind

    if size > current_app.config["MAX_REFERENCE_FILE_SIZE"]:
        raise ValueError("File too large. Max size is 5MB")
