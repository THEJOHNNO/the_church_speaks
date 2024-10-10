from flask import Flask, send_from_directory, request, jsonify
import json
from whoosh.index import open_dir
from whoosh.qparser import QueryParser
from whoosh.query import Or, Term
import sqlite3
import os
from bs4 import BeautifulSoup
import requests
import re

import logging

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

# Paths and configurations
DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'commentaries.sqlite')
BIBLE_DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'bible_translations/ESV.db')
IX_PATH = "indexdir"
ix = open_dir(IX_PATH)

@app.route('/')
def home():
    return send_from_directory('templates', 'search.html')

# to ingore (for testing)
@app.route('/verify_db')
def verify_db():
    try:
        conn = sqlite3.connect(BIBLE_DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()
        return jsonify({"tables": tables})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# to ingore (for testing)
@app.route('/inspect_table')
def inspect_table():
    try:
        conn = sqlite3.connect(BIBLE_DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bible LIMIT 50000;")
        rows = cursor.fetchall()
        conn.close()
        return jsonify({"rows": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# main search functionality
@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        logging.debug(f"Received data: {data}")
        query_str = data.get('query', '')
        logging.debug(f"Query string: {query_str}")
        results = []

        if ':' in query_str:
            # Search in the SQLite database
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()

            # Exact match
            cursor.execute("""
                SELECT id, file_name, txt, father_name, source_title, source_url 
                FROM commentary 
                WHERE txt = ?
                LIMIT 20
            """, (query_str,))
            exact_rows = cursor.fetchall()

            # Non-exact match
            cursor.execute("""
                SELECT id, file_name, txt, father_name, source_title, source_url 
                FROM commentary 
                WHERE txt LIKE ?
                LIMIT 20
            """, ('%' + query_str + '%',))
            non_exact_rows = cursor.fetchall()

            # Process rows
            rows = exact_rows + non_exact_rows
            for row in rows:
                id, file_name, txt, father_name, source_title, source_url = row
                breadcrumb = f"{source_title}"
                results.append({
                    "id": id,  # Include ID in the result
                    "file_path": file_name,
                    "content_snippet": txt[:700] + "...",  # Show first 700 characters as snippet
                    "h1": father_name,
                    "breadcrumb": breadcrumb
                })

            conn.close()

        if ':' in query_str and any(version in query_str.lower() for version in ['esv', 'kjv', 'amp', 'bsb', 'gen', 'nasb']):
            query_str_lower = query_str.lower()
            chosen_bible = 'ESV'
            if 'esv' in query_str_lower:
                BIBLE_DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'bible_translations', 'ESV.db')
                chosen_bible = 'ESV'
            elif 'kjv' in query_str_lower:
                BIBLE_DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'bible_translations', 'KJV.db')
                chosen_bible = 'KJV'
            elif 'amp' in query_str_lower:
                BIBLE_DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'bible_translations', 'AMP.db')
                chosen_bible = 'AMP'
            elif 'bsb' in query_str_lower:
                BIBLE_DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'bible_translations', 'BSB.db')
                chosen_bible = 'BSB'
            elif 'gen' in query_str_lower:
                BIBLE_DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'bible_translations', 'GEN.db')
                chosen_bible = 'GEN'
            elif 'nasb' in query_str_lower:
                BIBLE_DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'bible_translations', 'NASB.db')
                chosen_bible = 'NASB'

            # Search in the Bible database
            conn = sqlite3.connect(BIBLE_DATABASE_PATH)
            cursor = conn.cursor()

            # Book name to ID mapping (case-insensitive)
            # Create a case-insensitive book mapping
            book_mapping = {
                "Genesis": 0,
                "Exodus": 1,
                "Leviticus": 2,
                "Numbers": 3,
                "Deuteronomy": 4,
                "Joshua": 5,
                "Judges": 6,
                "Ruth": 7,
                "1 Samuel": 8,
                "2 Samuel": 9,
                "1 Kings": 10,
                "2 Kings": 11,
                "1 Chronicles": 12,
                "2 Chronicles": 13,
                "Ezra": 14,
                "Nehemiah": 15,
                "Esther": 16,
                "Job": 17,
                "Psalms": 18,
                "Proverbs": 19,
                "Ecclesiastes": 20,
                "Song of Solomon": 21,
                "Isaiah": 22,
                "Jeremiah": 23,
                "Lamentations": 24,
                "Ezekiel": 25,
                "Daniel": 26,
                "Hosea": 27,
                "Joel": 28,
                "Amos": 29,
                "Obadiah": 30,
                "Jonah": 31,
                "Micah": 32,
                "Nahum": 33,
                "Habakkuk": 34,
                "Zephaniah": 35,
                "Haggai": 36,
                "Zechariah": 37,
                "Malachi": 38,
                "Matthew": 39,
                "Mark": 40,
                "Luke": 41,
                "John": 42,
                "Acts": 43,
                "Romans": 44,
                "1 Corinthians": 45,
                "2 Corinthians": 46,
                "Galatians": 47,
                "Ephesians": 48,
                "Philippians": 49,
                "Colossians": 50,
                "1 Thessalonians": 51,
                "2 Thessalonians": 52,
                "1 Timothy": 53,
                "2 Timothy": 54,
                "Titus": 55,
                "Philemon": 56,
                "Hebrews": 57,
                "James": 58,
                "1 Peter": 59,
                "2 Peter": 60,
                "1 John": 61,
                "2 John": 62,
                "3 John": 63,
                "Jude": 64,
                "Revelation": 65
            }


            def fetch_verses(book, chapter, start_verse, end_verse=None):
                book_number = book_mapping.get(book.capitalize())
                if book_number is None:
                    logging.error(f"Book not found: {book}")
                    return []  # Invalid book name
                logging.debug(f"Fetching verses for book: {book_number}, chapter: {chapter}, verses: {start_verse} to {end_verse}")
                if end_verse:
                    query = """
                        SELECT Book, Chapter, Versecount, verse 
                        FROM bible 
                        WHERE Book = ? AND Chapter = ? AND Versecount BETWEEN ? AND ?
                    """
                    params = (book_number, chapter, start_verse, end_verse)
                else:
                    query = """
                        SELECT Book, Chapter, Versecount, verse 
                        FROM bible 
                        WHERE Book = ? AND Chapter = ? AND Versecount = ?
                    """
                    params = (book_number, chapter, start_verse)
                
                logging.debug(f"Executing query: {query} with params: {params}")
                cursor.execute(query, params)
                fetched_verses = cursor.fetchall()
                logging.debug(f"Fetched verses: {fetched_verses}")
                return fetched_verses


            # Parse the query
            pattern = re.compile(r'(\d?\s*[A-Za-z]+(?:\s+[A-Za-z]+)*)\s(\d+):(\d+)(?:-(\d+))?')

            matches = pattern.findall(query_str.capitalize())
            logging.debug(f"Matches found: {matches}")

            for match in matches:
                book_name, chapter, start_verse, end_verse = match
                book_name = book_name.strip()  # Clean up any extra spaces and convert to lowercase
                end_verse = end_verse or start_verse  # Use start_verse if end_verse is not specified

                # Mapping book name to a database identifier
                book_id = book_mapping.get(book_name.capitalize())
                if book_id is None:
                    logging.error(f"Book not found: {book_name}")
                    continue  # Skip this match if the book is not found in the mapping
                
                # Fetching verses from the database
                query = """
                    SELECT Book, Chapter, Versecount, Verse
                    FROM bible
                    WHERE Book = ? AND Chapter = ? AND Versecount BETWEEN ? AND ?
                """
                params = (book_id, chapter, start_verse, end_verse)
                cursor.execute(query, params)
                fetched_verses = cursor.fetchall()

                for verse in fetched_verses:
                    results.append({
                        "Book": verse[0],
                        "Chapter": verse[1],
                        "Verse": verse[2],
                        "Text": verse[3]
                    })

            conn.close()
            return jsonify({"query": query_str, "results": results, "type": "bible", "book_data": book_mapping, "bible_version": chosen_bible})
        else:
            # search anything else except bible (newadvent)
            with ix.searcher() as searcher:
                # Split the query into terms, respecting quoted phrases
                exact_terms = []
                non_exact_terms = []

                for term in query_str.split():
                    if term.startswith('"') and term.endswith('"'):
                        exact_terms.append(term.strip('"'))
                    else:
                        non_exact_terms.append(term)

                # Create exact match queries
                exact_queries = [Term("content", term) for term in exact_terms]
                
                # Create a query parser for non-exact terms
                parser = QueryParser("content", ix.schema)
                combined_non_exact_query = parser.parse(" ".join(non_exact_terms))

                # Combine all queries
                combined_query = Or(exact_queries + [combined_non_exact_query])

                # Search for the combined query
                hits = searcher.search(combined_query, limit=20)
                for hit in hits:
                    relative_path = hit['file_path']
                    fixed_path = relative_path.replace('\\', '/')

                    # Extract h1 and breadcrumb from the file
                    with open(f'static/{fixed_path}', 'r', encoding='utf-8') as file:
                        content = file.read()
                        soup = BeautifulSoup(content, 'html.parser')
                        h1 = soup.find('h1').get_text(strip=True) if soup.find('h1') else 'No title'
                        breadcrumb = ' > '.join([crumb.get_text(strip=True) for crumb in soup.select('.breadcrumbs a')])

                    results.append({
                        "file_path": fixed_path,
                        "content_snippet": hit.highlights("content"),
                        "h1": h1,
                        "breadcrumb": breadcrumb
                    })

        return jsonify({"query": query_str, "results": results})
    except Exception as e:
        print(f"Error during search: {e}")
        return jsonify({"error": str(e)}), 500

import re  # Ensure the re module is imported

@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.get_json()
        prompt = data.get('prompt')

        # Extract chapter and verse from the prompt using regex
        match = re.search(r'(\b\w+\s\d+:\d+\b)', prompt)
        if match:
            scripture_reference = match.group(1)
            chapter, verse = scripture_reference.split(':')

            # Search the SQLite database for the chapter and verse
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT father_name, txt 
                FROM commentary 
                WHERE txt LIKE ?
            """, ('%' + scripture_reference + '%',))
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return jsonify({"error": "No commentaries found for this scripture reference"}), 404

            contexts = []
            for row in rows:
                father_name, txt = row
                # Find the scripture reference in the text
                index = txt.lower().find(scripture_reference.lower())
                if index != -1:
                    start = max(0, index - 600)
                    end = min(len(txt), index + 600)
                    context = txt[start:end]
                    contexts.append(f"{father_name}: {context}")

            # Combine all contexts
            combined_context = "\n\n".join(contexts)

            # Check if the prompt contains a question
            if '?' in prompt or re.search(r'\bhow\b|\bwhat\b|\bwhy\b|\bwhen\b|\bwho\b|\bdoes\b|\bdo\b', prompt.lower()):
                ai_prompt = f"Context: {combined_context}\n\nQuestion: {prompt}\n\nPlease include quotes from the context\n\nYour response should be in markdown format\n\nAnswer:"
            else:
                ai_prompt = f"Provide a consensus of the church fathers on {scripture_reference} based on the following commentaries:\n\n{combined_context}\n\nPLease include quotes from the context\n\nYour response should be in markdown format\n\nAnswer:"
        else:
            # New logic for when no valid scripture reference is found
            ai_prompt = f"{prompt}\n\nYour response should be in markdown format\n\n"  # Use the prompt directly without additional context

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3:8b",
                "prompt": ai_prompt,
                "stream": False
            }
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "An error occurred with the AI model"}), response.status_code

    except Exception as e:
        print(f"Error during AI generation: {e}")
        return jsonify({"error": str(e)}), 500



@app.route('/context', methods=['POST'])
def context():
    try:
        data = request.get_json()
        query = data.get('query').lower()
        file_path = data.get('file_path')
        id = data.get('id', None)

        if id:
            # Fetch from SQLite database using id
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT txt, father_name, source_title 
                FROM commentary 
                WHERE id = ?
            """, (id,))
            row = cursor.fetchone()
            if row:
                txt, father_name, source_title = row
                contexts = [txt]
                breadcrumb_text = source_title
                h1_text = father_name
            else:
                return jsonify({"error": "No data found for this id"}), 404
            conn.close()
        else:
            # Fetch from static file system using file_path
            with open(f'static/{file_path}', 'r', encoding='utf-8') as file:
                content = file.read()

            soup = BeautifulSoup(content, 'html.parser')
            text_content = soup.get_text()
            lower_content = text_content.lower()
            contexts = []
            query_length = len(query)

            index = lower_content.find(query)
            if index == -1:
                # If exact match not found, get first 1120 characters
                context = text_content[:1120]
                contexts.append(context)
            else:
                while index != -1:
                    start = max(0, index - 560)
                    end = min(len(text_content), index + 560 + query_length)
                    context = text_content[start:end]
                    contexts.append(context)
                    index = lower_content.find(query, end)

            breadcrumb_text = soup.select_one('.breadcrumbs').get_text(strip=True) if soup.select_one('.breadcrumbs') else "No breadcrumb found"
            h1_text = soup.select_one('h1').get_text(strip=True) if soup.select_one('h1') else "No title found"

        return jsonify({"contexts": contexts, "breadcrumb_text": breadcrumb_text, "h1_text": h1_text})
    except Exception as e:
        print(f"Error during context extraction: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/ask_ai', methods=['POST'])
def ask_ai():
    try:
        data = request.get_json()
        file_path = data.get('file_path')
        question = data.get('question')

        with open(f'static/{file_path}', 'r', encoding='utf-8') as file:
            content = file.read()

        # Send the full content and the question to the AI
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3:8b",
                "prompt": f"Context:\n{content}\n\nQuestion: {question}\n\nYour response should be in markdown format",
                "stream": False
            }
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "An error occurred"}), response.status_code
    except Exception as e:
        print(f"Error during AI generation: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=34892)
