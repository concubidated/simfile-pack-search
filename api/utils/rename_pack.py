"""
This module provides functionality to rename a pack
"""
import os
import zipfile
import shutil
import tempfile

def rename_pack_file(zip_path, old_name, new_name):
    """Renames a folder inside a zip file and creates a new zip file."""
    temp_dir = tempfile.mkdtemp()

    # Unzip
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    # Rename folder inside temp_dir
    old_folder_path = os.path.join(temp_dir, old_name)
    new_folder_path = os.path.join(temp_dir, new_name)
    if os.path.exists(old_folder_path):
        os.rename(old_folder_path, new_folder_path)

    # Where to save the new zip
    base_dir = os.path.dirname(zip_path)
    new_zip_filename = f"{new_name}.zip"
    new_zip_path = os.path.join(base_dir, new_zip_filename)

    # check if file already exists before writing over it
    if os.path.exists(new_zip_path):
        raise FileExistsError(f"Destination file already exists: {new_zip_filename}")

    # Create new zip
    with zipfile.ZipFile(new_zip_path, 'w') as zipf:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, temp_dir)
                zipf.write(abs_path, rel_path)

    # Clean up
    shutil.rmtree(temp_dir)
    if os.path.exists(zip_path) and zip_path != new_zip_path:
        os.remove(zip_path)

    return new_zip_path
