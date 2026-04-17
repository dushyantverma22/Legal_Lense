"""
Project Folder + Package Initializer
===================================

Creates:
1. Folder structure
2. __init__.py files for Python packages

Usage:
    python template.py
"""

from pathlib import Path


# ==============================
# 📁 Folder Structure
# ==============================
FOLDERS = [
    "notebooks",

    "src/ingestion",
    "src/retrieval",
    "src/generation",
    "src/evaluation",
    "src/api",

    "tests/unit",
    "tests/integration",

    "config",

    "data/raw",
    "data/processed",
    "data/eval",

    "logs",
]


# ==============================
# 📦 Python Package Files
# ==============================
INIT_FILES = [
    "src/__init__.py",
    "src/ingestion/__init__.py",
    "src/retrieval/__init__.py",
    "src/generation/__init__.py",
    "src/evaluation/__init__.py",
    "src/api/__init__.py",
]


# ==============================
# 📂 Create Folders
# ==============================
def create_folders(base_path: str = ".") -> None:
    for folder in FOLDERS:
        path = Path(base_path) / folder
        path.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created folder: {path}")


# ==============================
# 📄 Create __init__.py Files
# ==============================
def create_init_files(base_path: str = ".") -> None:
    for file in INIT_FILES:
        file_path = Path(base_path) / file

        # Ensure parent folder exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file if not exists
        file_path.touch(exist_ok=True)
        print(f"📄 Created file: {file_path}")


# ==============================
# 🚀 Entry Point
# ==============================
if __name__ == "__main__":
    print("🚀 Setting up project structure...\n")

    create_folders()
    create_init_files()

    print("\n🎉 Project setup completed successfully!")