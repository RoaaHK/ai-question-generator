import os
import re
import logging
from datetime import datetime
import hashlib
import requests

from pymongo import MongoClient, UpdateOne
from tqdm import tqdm
from functools import lru_cache


class TextSplitter:
    def __init__(self, model_name="llama3", max_allowed_tokens=2048,
                 mongo_uri=None, db_name="GradProj", db_connection=None, max_cache_size=50000):

        # Try to load SpaCy model, fallback if not available
        try:
            import spacy
            self.nlp = spacy.load("en_core_web_sm")
            self.use_spacy = True
            logging.info("SpaCy model loaded successfully")
        except (OSError, ImportError) as e:
            logging.warning(f"SpaCy model not available: {e}")
            logging.warning("Using simple sentence splitting fallback")
            self.nlp = None
            self.use_spacy = False

        self.token_cache = {}
        self.MAX_TOKENS = max_allowed_tokens - 30
        self._token_cache = lru_cache(maxsize=max_cache_size)(self._count_tokens)
        self.streaming_threshold = 10 * 1024 * 1024

        self.ollama_api = "http://localhost:11434/api/generate"
        self.ollama_model = model_name
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

        self.mongo_client = None
        self.db = None

        if db_connection is not None:
            self.db = db_connection
            logging.info("Using existing MongoDB connection")
        elif mongo_uri:
            try:
                self.mongo_client = MongoClient(mongo_uri)
                self.db = self.mongo_client[db_name]
                logging.info(f"Created new MongoDB connection: {db_name}")
            except Exception as e:
                logging.error(f"Failed to connect to MongoDB: {e}")

    def set_ollama_api(self, api_url, model_name):
        self.ollama_api = api_url
        self.ollama_model = model_name

    def _count_tokens(self, text):
        if text not in self.token_cache:
            try:
                response = requests.post(
                    self.ollama_api.replace("/generate", "/tokenize"),
                    json={"model": self.ollama_model, "prompt": text},
                    timeout=5
                )
                if response.status_code == 200:
                    tokens = len(response.json().get("tokens", []))
                    self.token_cache[text] = tokens
                else:
                    # Fallback to a simple approximation
                    self.token_cache[text] = len(text.split())
            except:
                # Fallback to a simple approximation
                self.token_cache[text] = len(text.split())
        return self.token_cache[text]

    @staticmethod
    def detect_table(text):
        has_table_markers = bool(re.search(r"[-+|][-+|]+[-+|]", text))
        has_multiple_pipe_chars = text.count("|") > 3
        has_table_header = bool(re.search(r"[-+]+[-+]+[-+]", text))
        return has_table_markers or (has_multiple_pipe_chars and has_table_header)

    @staticmethod
    def detect_list_item(text):
        list_marker_patterns = [
            r"^\s*[•\-\*]\s+",
            r"^\s*\d+[\.\)]\s+",
            r"^\s*[a-zA-Z][\.\)]\s+",
            r"^\s*[•\-\*]\s+[A-Z][a-z]+\s+\(",
        ]
        for pattern in list_marker_patterns:
            if re.search(pattern, text, re.MULTILINE):
                return True
        return False

    @staticmethod
    def is_incomplete_list_item(text):
        if re.search(r"[-,]\s*$", text):
            return True
        if (re.search(r"^\s*[•\-*]\s+", text) and
                not re.search(r"[.!?]\s*$", text) and
                len(text.split()) < 15):
            return True
        if re.search(r"\([a-zA-Z\s]+\)\s*-\s*$", text):
            return True
        return False

    @staticmethod
    def split_by_headings(text):
        pattern = r"(?i)(chapter \d+|lesson \d+|section \d+|\b[a-z]+ \d+:)"
        parts = re.split(pattern, text)
        chunks = []
        current_heading = ""
        for part in parts:
            if re.match(pattern, part, flags=re.IGNORECASE):
                current_heading = part.strip()
            else:
                if part.strip():
                    chunk = f"{current_heading} {part.strip()}" if current_heading else part.strip()
                    chunks.append(chunk)
                    current_heading = ""
        return chunks

    def _split_table(self, table_text):
        rows = table_text.split("\n")
        header_rows = []
        separator_rows = []

        for i, row in enumerate(rows):
            if all(c in "+=- " for c in row.strip()):
                separator_rows.append(i)
                if "=" in row:
                    header_rows.append(i)

        header_indices = []
        if separator_rows:
            first_sep = separator_rows[0]
            header_indices.append(first_sep)
            for i in separator_rows:
                if i > first_sep:
                    header_indices.append(i)
                    break

        headers = []
        if header_indices and len(header_indices) >= 2:
            header_start = header_indices[0]
            header_end = header_indices[1] + 1
            headers = rows[header_start:header_end]
            data_rows = rows[header_end:]
        else:
            if separator_rows:
                headers = rows[:separator_rows[0] + 2]
                data_rows = rows[separator_rows[0] + 2:]
            else:
                headers = rows[:2] if len(rows) > 2 else []
                data_rows = rows[2:] if len(rows) > 2 else rows

        header_text = "\n".join(headers) if headers else ""
        header_tokens = self._count_tokens(header_text) if header_text else 0

        chunks = []
        current_chunk = headers.copy() if headers else []
        current_tokens = header_tokens

        row_sections = []
        current_section = []
        for row in data_rows:
            if all(c in "+=- " for c in row.strip()):
                if current_section:
                    row_sections.append(current_section)
                    current_section = []
            current_section.append(row)

        if current_section:
            row_sections.append(current_section)

        for section in row_sections:
            section_text = "\n".join(section)
            section_tokens = self._count_tokens(section_text)

            if current_tokens + section_tokens > self.MAX_TOKENS:
                if current_chunk and not current_chunk[-1].startswith("+"):
                    border_row = rows[separator_rows[-1]] if separator_rows else "+" + "-" * (
                            len(current_chunk[-1]) - 2) + "+"
                    current_chunk.append(border_row)

                if len(current_chunk) > len(headers):
                    chunks.append("\n".join(current_chunk))

                current_chunk = headers.copy() if headers else []
                current_tokens = header_tokens

            current_chunk.extend(section)
            current_tokens += section_tokens

        if len(current_chunk) > len(headers):
            if not current_chunk[-1].startswith("+"):
                border_row = rows[separator_rows[-1]] if separator_rows else "+" + "-" * (
                        len(current_chunk[-1]) - 2) + "+"
                current_chunk.append(border_row)
            chunks.append("\n".join(current_chunk))

        return chunks

    def _break_into_small_chunks(self, text):
        words = text.split()
        chunks = []
        current_chunk = []
        current_tokens = 0

        for word in words:
            word_tokens = self._count_tokens(word)

            if word_tokens > self.MAX_TOKENS:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                chunks.append(word[:len(word) // 2])
                chunks.append(word[len(word) // 2:])
                continue

            if current_tokens + word_tokens > self.MAX_TOKENS:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_tokens = word_tokens
            else:
                current_chunk.append(word)
                current_tokens += word_tokens

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def split_by_paragraphs(self, text, min_tokens=150):
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        current_chunk = []
        current_token_count = 0
        skip_next = False

        for i, para in enumerate(paragraphs):
            if skip_next:
                skip_next = False
                continue

            is_list_item = self.detect_list_item(para)
            is_incomplete = self.is_incomplete_list_item(para)
            next_para_exists = i < len(paragraphs) - 1

            if is_incomplete and next_para_exists:
                combined_para = para + "\n\n" + paragraphs[i + 1]
                para = combined_para
                skip_next = True

            if self.detect_table(para):
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_token_count = 0

                table_tokens = self._count_tokens(para)
                if table_tokens <= self.MAX_TOKENS:
                    chunks.append(para)
                else:
                    table_parts = self._split_table(para)
                    chunks.extend(table_parts)
                continue

            para_token_count = self._count_tokens(para)

            if para_token_count > self.MAX_TOKENS:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_token_count = 0
                sent_chunks = self.split_by_sentences(para)
                chunks.extend(sent_chunks)
                continue

            if current_token_count + para_token_count > self.MAX_TOKENS:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_token_count = para_token_count
            else:
                current_chunk.append(para)
                current_token_count += para_token_count

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        if min_tokens > 0:
            return self._merge_small_chunks(chunks, min_tokens)
        return chunks

    def split_by_sentences(self, text):
        # Proper fallback when SpaCy is not available
        if self.use_spacy and self.nlp:
            doc = self.nlp(text)
            sentences = [sent.text.strip() for sent in doc.sents]
        else:
            # Simple sentence splitting fallback
            import re
            # Split on sentence endings followed by whitespace and capital letter
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
            sentences = [sent.strip() for sent in sentences if sent.strip()]
        chunks = []
        current_chunk = []
        current_tokens = 0

        for i, sent in enumerate(sentences):
            sent_tokens = self._count_tokens(sent)
            is_incomplete = self.is_incomplete_list_item(sent)
            next_sent_exists = i < len(sentences) - 1

            if is_incomplete and next_sent_exists:
                sent = sent + " " + sentences[i + 1]
                sent_tokens = self._count_tokens(sent)
                i += 1

            if sent_tokens > self.MAX_TOKENS:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                for part in self._break_into_small_chunks(sent):
                    chunks.append(part)
                continue

            if current_tokens + sent_tokens > self.MAX_TOKENS:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [sent]
                current_tokens = sent_tokens
            else:
                current_chunk.append(sent)
                current_tokens += sent_tokens

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def split_by_bullet_points(self, text):
        list_marker_pattern = r"(\n\s*[\-•*] |\n\s*\d+\. )"
        parts = re.split(list_marker_pattern, text)
        chunks = []
        current_chunk = ""
        current_tokens = 0
        list_context = ""

        for i, part in enumerate(parts):
            if not part.strip():
                continue
            if re.match(list_marker_pattern, part):
                if i > 0 and not re.match(list_marker_pattern, parts[i - 1]):
                    list_context = parts[i - 1]
                break

        i = 0
        while i < len(parts):
            part = parts[i]
            if not part.strip():
                i += 1
                continue

            is_list_marker = re.match(list_marker_pattern, part)
            if is_list_marker and i + 1 < len(parts):
                combined_part = part + parts[i + 1]
                is_incomplete = self.is_incomplete_list_item(combined_part)
                if is_incomplete and i + 2 < len(parts):
                    combined_part += parts[i + 2]
                    i += 3
                else:
                    i += 2
                part = combined_part
            else:
                i += 1

            part_tokens = self._count_tokens(part)

            if part_tokens > self.MAX_TOKENS:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                    current_tokens = 0
                sub_chunks = self.split_by_sentences(part)
                chunks.extend(sub_chunks)
                continue

            if current_tokens + part_tokens > self.MAX_TOKENS:
                if current_chunk:
                    chunks.append(current_chunk)
                if re.match(list_marker_pattern, part) and list_context and self._count_tokens(
                        list_context + part) <= self.MAX_TOKENS:
                    current_chunk = list_context + part
                    current_tokens = self._count_tokens(current_chunk)
                else:
                    current_chunk = part
                    current_tokens = part_tokens
            else:
                current_chunk += part
                current_tokens += part_tokens

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def split_text(self, text, min_tokens=150, strategy="hierarchical"):
        if self._count_tokens(text) <= self.MAX_TOKENS:
            return [text]

        if strategy == "hierarchical":
            heading_chunks = self.split_by_headings(text)
            processed_chunks = []

            for chunk in heading_chunks:
                chunk_tokens = self._count_tokens(chunk)
                if chunk_tokens <= self.MAX_TOKENS:
                    processed_chunks.append(chunk)
                else:
                    if self.detect_table(chunk):
                        table_chunks = self._split_table(chunk)
                        processed_chunks.extend(table_chunks)
                    else:
                        para_chunks = self.split_by_paragraphs(chunk, min_tokens=min_tokens)
                        processed_chunks.extend(para_chunks)

            verified_chunks = []
            for chunk in processed_chunks:
                chunk_tokens = self._count_tokens(chunk)
                if chunk_tokens <= self.MAX_TOKENS:
                    verified_chunks.append(chunk)
                else:
                    fallback_chunks = self.split_by_sentences(chunk)
                    verified_chunks.extend(fallback_chunks)

            return verified_chunks

        elif strategy == "paragraphs":
            return self.split_by_paragraphs(text, min_tokens=min_tokens)
        elif strategy == "sentences":
            return self.split_by_sentences(text)
        elif strategy == "bullet_points":
            return self.split_by_bullet_points(text)
        else:
            raise ValueError(f"Unknown splitting strategy: {strategy}")

    def _merge_small_chunks(self, chunks, min_tokens):
        if not chunks:
            return []

        result = []
        current_chunk = chunks[0]
        current_tokens = self._count_tokens(current_chunk)

        for i in range(1, len(chunks)):
            next_chunk = chunks[i]
            next_tokens = self._count_tokens(next_chunk)
            is_incomplete = self.is_incomplete_list_item(current_chunk)

            if (current_tokens < min_tokens or is_incomplete) and current_tokens + next_tokens <= self.MAX_TOKENS:
                current_chunk = current_chunk + "\n\n" + next_chunk
                current_tokens += next_tokens
            else:
                result.append(current_chunk)
                current_chunk = next_chunk
                current_tokens = next_tokens

        if current_chunk:
            result.append(current_chunk)

        return result

    @staticmethod
    def preprocess_text(text):
        pattern = r"([\•\-\*]\s+[A-Z0-9]+\s+\([^)]+\)\s*[\-,])"
        matches = re.finditer(pattern, text)

        for match in matches:
            start_pos = match.start()
            end_pos = match.end()
            line_end = text.find("\n", end_pos)

            if line_end == -1:
                line_end = len(text)

            complete_item = text[start_pos:line_end].strip()
            if len(complete_item.split()) > 3 and not complete_item.endswith("-"):
                continue

            next_para_start = line_end + 1
            while next_para_start < len(text) and text[next_para_start].isspace():
                next_para_start += 1

            if next_para_start < len(text):
                next_para_end = text.find("\n\n", next_para_start)
                if next_para_end == -1:
                    next_para_end = len(text)
                item_with_explanation = complete_item + " " + text[next_para_start:next_para_end].strip()
                to_replace = text[start_pos:line_end] + text[line_end:next_para_end]
                text = text.replace(to_replace, item_with_explanation)

        return text

    @staticmethod
    def _create_chunk_hash(chunk_data):
        hash_string = f"{chunk_data['file_name']}-{chunk_data['chunk_id']}-{chunk_data['content']}"
        return hashlib.md5(hash_string.encode()).hexdigest()

    def process_file(self, file_path, min_tokens, strategy):
        result_chunks = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
                text = self.preprocess_text(text)

                global_position = 0
                current_hierarchy = []

                file_stats = os.stat(file_path)
                doc_metadata = {
                    "title": os.path.splitext(os.path.basename(file_path))[0],
                    "file_size": file_stats.st_size,
                    "created": file_stats.st_ctime,
                    "modified": file_stats.st_mtime
                }

                text_chunks = self.split_text(text, min_tokens=min_tokens, strategy=strategy)

                for idx, chunk in enumerate(text_chunks, start=1):
                    start_pos = global_position
                    end_pos = start_pos + len(chunk.encode('utf-8'))
                    global_position = end_pos + 2  # Account for separators

                    chunk_type, hierarchy_update = self._analyze_chunk_structure(
                        chunk, current_hierarchy)

                    if hierarchy_update:
                        current_hierarchy = hierarchy_update

                    chunk_data = {
                        "file_name": os.path.basename(file_path),
                        "chunk_id": str(idx),
                        "content": chunk,
                        "tokens": self._count_tokens(chunk),
                        "chunk_type": chunk_type,
                        "position": {
                            "start": start_pos,
                            "end": end_pos,
                            "line": text.count('\n', 0, start_pos) + 1
                        },
                        "hierarchy": current_hierarchy.copy(),
                        **doc_metadata
                    }

                    # content hash for tracking changes
                    chunk_data["content_hash"] = self._create_chunk_hash(chunk_data)

                    result_chunks.append(chunk_data)

                return result_chunks

        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")
            return []

    def _analyze_chunk_structure(self, chunk, current_hierarchy):
        chunk_type = "paragraph"
        new_hierarchy = None

        if self.detect_table(chunk):
            chunk_type = "table"
        elif self.detect_list_item(chunk):
            chunk_type = "list"
        else:
            heading_match = re.match(
                r'^(?:HEADING_START\n)?(chapter|section|part)\s+([\w\d]+)',
                chunk,
                re.IGNORECASE
            )
            if heading_match:
                chunk_type = "heading"
                level = {"chapter": 1, "part": 1, "section": 2}.get(
                    heading_match.group(1).lower(), 2)

                new_hierarchy = current_hierarchy.copy()
                while new_hierarchy and new_hierarchy[-1]["level"] >= level:
                    new_hierarchy.pop()

                new_hierarchy.append({
                    "title": heading_match.group(0),
                    "level": level,
                    "ref": f"{heading_match.group(1)}-{heading_match.group(2)}"
                })

        return chunk_type, new_hierarchy

    def _sync_to_mongodb(self, chunks, collection_name="chunks"):
        if self.db is None:
            return False

        try:
            collection = self.db[collection_name]

            operations = []
            for chunk in chunks:
                operations.append(
                    UpdateOne(
                        {"file_name": chunk["file_name"], "chunk_id": chunk["chunk_id"]},
                        {"$set": chunk},
                        upsert=True
                    )
                )

            if operations:
                result = collection.bulk_write(operations)
                logging.info(f"MongoDB sync: {result.upserted_count} inserted, "
                             f"{result.modified_count} updated")
                return True
            return False
        except Exception as e:
            logging.error(f"Error syncing to MongoDB: {e}")
            return False

    def process_text_direct(self, text, file_name, file_hash=None, min_tokens=150, strategy="hierarchical"):
        try:
            text = self.preprocess_text(text)
            text_chunks = self.split_text(text, min_tokens=min_tokens, strategy=strategy)

            if not text_chunks:
                logging.warning(f"No chunks created from text for {file_name}")
                return []

            result_chunks = []
            global_position = 0
            current_hierarchy = []
            current_time = datetime.now()

            for idx, chunk in enumerate(text_chunks, start=1):
                start_pos = global_position
                end_pos = start_pos + len(chunk.encode('utf-8'))
                global_position = end_pos + 2

                chunk_type, hierarchy_update = self._analyze_chunk_structure(chunk, current_hierarchy)

                if hierarchy_update:
                    current_hierarchy = hierarchy_update

                chunk_data = {
                    "file_name": file_name,
                    "chunk_id": str(idx),
                    "content": chunk,
                    "tokens": self._count_tokens(chunk),
                    "hierarchy": current_hierarchy.copy(),
                    "file_hash": file_hash,  # page_range_hash from db_manager
                    "created_at": current_time,
                    "chunk_type": chunk_type,
                    "position": {
                        "start": start_pos,
                        "end": end_pos,
                        "line": text.count('\n', 0, start_pos) + 1
                    }
                }

                chunk_data["content_hash"] = self._create_chunk_hash(chunk_data)
                result_chunks.append(chunk_data)

            logging.info(f"Created {len(result_chunks)} chunks from text for {file_name}")
            return result_chunks

        except Exception as e:
            logging.error(f"Error processing text directly: {e}")
            return []

    def find_chunks(self, query=None, collection_name="chunks"):
        if self.db is None:
            logging.error("MongoDB connection not available")
            return []

        try:
            collection = self.db[collection_name]
            if query is None:
                query = {}
            return list(collection.find(query))
        except Exception as e:
            logging.error(f"Error querying MongoDB: {e}")
            return []

    def update_chunk(self, file_name, chunk_id, updates, collection_name="chunks"):
        if self.db is None:
            logging.error("MongoDB connection not available")
            return False

        try:
            collection = self.db[collection_name]

            current_chunk = collection.find_one({"file_name": file_name, "chunk_id": chunk_id})
            if not current_chunk:
                logging.error(f"Chunk not found: {file_name}, {chunk_id}")
                return False

            updates["version"] = current_chunk.get("version", 1) + 1

            if "content" in updates:
                chunk_data = current_chunk.copy()
                chunk_data.update(updates)
                updates["content_hash"] = self._create_chunk_hash(chunk_data)

            result = collection.update_one(
                {"file_name": file_name, "chunk_id": chunk_id},
                {"$set": updates}
            )

            if result.modified_count == 0:
                logging.warning(f"No changes made to chunk: {file_name}, {chunk_id}")
                return False

            logging.info(f"Updated chunk in MongoDB: {file_name}, {chunk_id}")
            return True
        except Exception as e:
            logging.error(f"Error updating chunk: {e}")
            return False

    def process_folder(self, input_folder_path, min_tokens=150, strategy="hierarchical",
                       collection_name="chunks"):
        all_chunks = []

        for root, dirs, files in os.walk(input_folder_path):
            input_files = [f for f in files if f.endswith(".txt")]

            if not input_files:
                continue

            rel_path = os.path.relpath(root, input_folder_path)

            for file_name in tqdm(input_files, desc=f"Processing files in {rel_path}"):
                full_path = os.path.join(root, file_name)
                file_chunks = self.process_file(full_path, min_tokens, strategy)

                if not file_chunks:
                    logging.warning(f"No chunks created for file: {full_path}")
                    continue

                logging.info(f"Processed {len(file_chunks)} chunks from {file_name}")
                all_chunks.extend(file_chunks)

                # Sync chunks to MongoDB in smaller batches for better performance
                if len(all_chunks) >= 100:
                    self._sync_to_mongodb(all_chunks, collection_name)
                    all_chunks = []

        # Sync any remaining chunks
        if all_chunks:
            self._sync_to_mongodb(all_chunks, collection_name)
            logging.info(f"Synced {len(all_chunks)} chunks to MongoDB collection: {collection_name}")

        return True


if __name__ == "__main__":
    # MONGO_ATLAS_URI = "mongodb+srv://Rtest:<1209348756>@cluster0.vln72pz.mongodb.net/"
    LOCAL_MONGO_URI = "mongodb://localhost:27017/"

    splitter = TextSplitter(
        model_name="llama3",
        max_allowed_tokens=2048,
        mongo_uri=LOCAL_MONGO_URI,
        db_name="GradProj"
    )

    input_folder = r"C:\Users\user\Downloads\books"

    success = splitter.process_folder(
        input_folder,
        min_tokens=150,
        strategy="hierarchical",
        collection_name="chunks"
    )

    if success:
        print("Successfully processed all files and saved chunks to GradProj database!")
    else:
        print("Failed to process files. Check logs for more details.")