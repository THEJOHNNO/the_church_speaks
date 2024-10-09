import json
import os
from whoosh.index import create_in
from whoosh.fields import Schema, TEXT, ID

# Define the schema for the index
schema = Schema(file_path=ID(stored=True, unique=True), content=TEXT(stored=True))

# Create the index directory if it doesn't exist
if not os.path.exists("indexdir"):
    os.mkdir("indexdir")

# Create the index
ix = create_in("indexdir", schema)

# Open the index writer
writer = ix.writer()

# Load the index.json file
with open("index.json", "r", encoding="utf-8") as f:
    data = json.load(f)
    for i, (file_path, content) in enumerate(data.items()):
        writer.add_document(file_path=file_path, content=content)
        if i % 100 == 0:
            print(f"Indexed {i}/{len(data)} documents...")

# Commit the changes
writer.commit()
print("Indexing completed.")
