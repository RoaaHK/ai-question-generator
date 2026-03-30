import logging
import json
from pymongo import MongoClient, UpdateOne
from typing import List, Dict, Optional, Union
from datetime import datetime


class DBManager:
    def __init__(self, mongo_uri: str = None, db_name: str = "question_bank"):

        self.mongo_client = None
        self.db = None
        self._initialize_logging()

        if mongo_uri:
            self._connect_to_mongodb(mongo_uri, db_name)

    def _initialize_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("db_manager.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _connect_to_mongodb(self, mongo_uri: str, db_name: str):
        try:
            self.mongo_client = MongoClient(
                mongo_uri,
                connectTimeoutMS=5000,
                socketTimeoutMS=30000,
                serverSelectionTimeoutMS=5000
            )
            self.db = self.mongo_client[db_name]
            self._create_indexes()
            self.logger.info(f"Successfully connected to MongoDB: {db_name}")

            self.mongo_client.admin.command('ping')

        except Exception as e:
            self.logger.error(f"Failed to connect to MongoDB: {e}")
            raise ConnectionError(f"Could not connect to MongoDB: {e}")

    def _create_indexes(self):
        indexes = {
            'files': [
                ("file_hash", 1),
                ("file_name", 1),
                ("page_range_hash", 1)
            ],
            'chunks': [
                ("file_hash", 1),
                ("chunk_id", 1),
                [("file_name", 1), ("chunk_id", 1)],
                ("content_hash", 1)
            ],
            'sessions': [
                ("session_id", 1),
                ("file_hash", 1),
                ("created_at", -1)
            ],
            'questions': [
                [("session_id", 1), ("chunk_id", 1)],
                ("question_type", 1),
                ("difficulty", 1),
                ("quality_score", -1),
                ("times_shown", 1),
                ("correct_rate", -1)
            ]
        }

        for collection_name, collection_indexes in indexes.items():
            collection = self.db[collection_name]

            for index_spec in collection_indexes:
                try:
                    if isinstance(index_spec, list):
                        existing_indexes = collection.list_indexes()
                        index_name = "_".join([f"{field}_{direction}" for field, direction in index_spec])

                        index_exists = False
                        for existing_index in existing_indexes:
                            if existing_index.get("name") == index_name:
                                index_exists = True
                                break

                        if not index_exists:
                            collection.create_index(index_spec)
                            self.logger.info(f"Created compound index {index_spec} for {collection_name}")
                        else:
                            self.logger.info(f"Index {index_spec} already exists for {collection_name}")

                    else:
                        existing_indexes = collection.list_indexes()
                        index_name = f"{index_spec[0]}_{index_spec[1]}" if isinstance(index_spec,
                                                                                      tuple) else f"{index_spec}_1"

                        index_exists = False
                        for existing_index in existing_indexes:
                            if existing_index.get("name") == index_name:
                                index_exists = True
                                break

                        if not index_exists:
                            collection.create_index([index_spec])
                            self.logger.info(f"Created index {index_spec} for {collection_name}")
                        else:
                            self.logger.info(f"Index {index_spec} already exists for {collection_name}")

                except Exception as e:
                    self.logger.warning(f"Failed to create index {index_spec} for {collection_name}: {e}")

        try:
            existing_indexes = list(self.db.files.list_indexes())
            unique_page_range_exists = any(
                idx.get("unique") and "page_range_hash" in str(idx.get("key", {}))
                for idx in existing_indexes
            )

            if not unique_page_range_exists:
                self.db.files.create_index("page_range_hash", unique=True, name="unique_page_range_hash")
                self.logger.info("Created unique index on page_range_hash")
            else:
                self.logger.info("Unique page_range_hash index already exists")

        except Exception as e:
            self.logger.warning(f"Failed to create unique page_range_hash index: {e}")

        try:
            existing_indexes = list(self.db.sessions.list_indexes())
            unique_session_exists = any(
                idx.get("unique") and "session_id" in str(idx.get("key", {}))
                for idx in existing_indexes
            )

            if not unique_session_exists:
                self.db.sessions.create_index("session_id", unique=True, name="unique_session_id")
                self.logger.info("Created unique index on session_id")
            else:
                self.logger.info("Unique session_id index already exists")

        except Exception as e:
            self.logger.warning(f"Failed to create unique session_id index: {e}")

        try:
            existing_indexes = list(self.db.chunks.list_indexes())
            unique_compound_exists = any(
                idx.get("unique") and "file_name" in str(idx.get("key", {})) and "chunk_id" in str(idx.get("key", {}))
                for idx in existing_indexes
            )

            if not unique_compound_exists:
                self.db.chunks.create_index([("file_name", 1), ("chunk_id", 1)], unique=True, name="unique_file_chunk")
                self.logger.info("Created unique compound index on file_name + chunk_id")
            else:
                self.logger.info("Unique compound index already exists")

        except Exception as e:
            self.logger.warning(f"Failed to create unique compound index: {e}")

    def register_file(self, file_path: str, file_name: str, page_numbers: List[int] = None) -> tuple:

        base_file_hash = self._calculate_file_hash(file_path)
        page_range_hash = self._calculate_page_range_hash(base_file_hash, page_numbers)

        existing = self.db.files.find_one({"page_range_hash": page_range_hash})

        if existing:
            self.logger.info(f"Found existing file with same page range: {page_range_hash}")
            return (page_range_hash, True)

        file_record = {
            "file_hash": base_file_hash,
            "page_range_hash": page_range_hash,
            "file_name": file_name,
            "original_path": file_path,
            "page_numbers": page_numbers,
            "page_range_description": self._format_page_range(page_numbers),
            "created_at": datetime.now(),
            "chunk_count": 0
        }

        self.db.files.insert_one(file_record)
        self.logger.info(f"Registered new file with page range: {page_range_hash}")
        return page_range_hash, False

    def create_question_session(self, file_hash: str, file_name: str, config: dict) -> str:
        session_id = self._generate_session_id(file_hash, config)

        existing_session = self.db.sessions.find_one({"session_id": session_id})

        if existing_session:
            self.logger.info(f"Reusing existing session: {session_id}")
            return session_id

        session_data = {
            "session_id": session_id,
            "file_hash": file_hash,
            "file_name": file_name,
            "config": config,
            "created_at": datetime.now(),
            "status": "active"
        }

        try:
            self.db.sessions.insert_one(session_data)
            self.logger.info(f"Created new session: {session_id}")
            return session_id
        except Exception as e:
            if "duplicate key error" in str(e):
                self.logger.info(f"Session created concurrently, reusing: {session_id}")
                return session_id
            else:
                raise e

    def store_questions_with_metadata(self, questions: List[Dict], session_id: str) -> bool:
        if not questions:
            return False

        operations = []
        for question in questions:
            quality_score = self._calculate_quality_score(question)
            difficulty = self._determine_difficulty(question)

            question_id = self._generate_question_id(question, session_id)

            operations.append(UpdateOne(
                {"question_id": question_id},
                {"$set": {
                    **question,
                    "session_id": session_id,
                    "question_id": question_id,
                    "quality_score": quality_score,
                    "difficulty": difficulty,
                    "times_shown": 0,
                    "times_answered": 0,
                    "correct_rate": 0.0,
                    "last_shown": None,
                    "created_at": datetime.now()
                }},
                upsert=True
            ))

        result = self.db.questions.bulk_write(operations)
        self.logger.info(f"Stored {result.upserted_count} new questions, updated {result.modified_count}")
        return True

    def get_questions_smart(
            self,
            session_id: str,
            max_questions: int = 35,
            filters: dict = None
    ) -> List[Dict]:
        if not filters:
            filters = {}

        session = self.db.sessions.find_one({"session_id": session_id})
        if not session:
            return []

        query = {"session_id": session_id, "status": {"$ne": "archived"}}
        if "difficulty" in filters:
            query["difficulty"] = filters["difficulty"]
        if "question_types" in filters:
            query["question_type"] = {"$in": filters["question_types"]}

        requested_types = session["config"]["question_types"]
        questions_per_chunk = session["config"]["questions_per_chunk"]

        if not requested_types:
            return self._get_questions_simple(query, max_questions)

        return self._get_questions_with_distribution(
            query,
            requested_types,
            max_questions,
            questions_per_chunk
        )

    def _get_questions_simple(self, query: dict, max_questions: int) -> List[Dict]:
        try:
            questions = list(self.db.questions.find(query)
                             .sort([("quality_score", -1), ("times_shown", 1)])
                             .limit(max_questions))

            if questions:
                question_ids = [q["_id"] for q in questions]
                self.db.questions.update_many(
                    {"_id": {"$in": question_ids}},
                    {
                        "$inc": {"times_shown": 1},
                        "$set": {"last_shown": datetime.now()}
                    }
                )

            return questions
        except Exception as e:
            self.logger.error(f"Error in simple question retrieval: {e}")
            return []

    def _get_questions_with_distribution(
            self,
            query: dict,
            requested_types: list,
            max_questions: int,
            questions_per_chunk: int
    ) -> List[Dict]:
        questions = []
        per_type = max_questions // len(requested_types)
        remainder = max_questions % len(requested_types)

        for i, q_type in enumerate(requested_types):
            limit = per_type + (1 if i < remainder else 0)
            if limit <= 0:
                continue

            type_query = {**query, "question_type": q_type}

            pipeline = [
                {"$match": type_query},
                {"$sort": {"quality_score": -1, "times_shown": 1}},
                {"$limit": limit * 3},
                {"$group": {
                    "_id": "$chunk_id",
                    "questions": {"$push": "$$ROOT"},
                    "count": {"$sum": 1}
                }},
                {"$project": {
                    "chunk_id": "$_id",
                    "questions": {"$slice": ["$questions", 2]},
                    "_id": 0
                }}
            ]

            chunk_results = list(self.db.questions.aggregate(pipeline))
            for result in chunk_results:
                questions.extend(result["questions"])
                if len(questions) >= max_questions:
                    break

        if questions:
            question_ids = [q["_id"] for q in questions[:max_questions]]
            self.db.questions.update_many(
                {"_id": {"$in": question_ids}},
                {
                    "$inc": {"times_shown": 1},
                    "$set": {"last_shown": datetime.now()}
                }
            )

        return questions[:max_questions]

    def get_question_statistics(self, session_id):
        try:
            if self.db is None:
                return {}

            pipeline = [
                {"$match": {"session_id": session_id, "status": {"$ne": "archived"}}},
                {"$group": {
                    "_id": "$question_type",
                    "count": {"$sum": 1},
                    "avg_quality": {"$avg": "$quality_score"},
                    "avg_shown": {"$avg": "$times_shown"},
                    "avg_correct_rate": {"$avg": "$correct_rate"}
                }}
            ]

            type_stats = list(self.db.questions.aggregate(pipeline))

            total_questions = self.db.questions.count_documents({
                "session_id": session_id,
                "status": {"$ne": "archived"}
            })

            difficulty_pipeline = [
                {"$match": {"session_id": session_id, "status": {"$ne": "archived"}}},
                {"$group": {
                    "_id": "$difficulty",
                    "count": {"$sum": 1}
                }}
            ]

            difficulty_stats = list(self.db.questions.aggregate(difficulty_pipeline))

            performance_pipeline = [
                {"$match": {"session_id": session_id, "status": {"$ne": "archived"}}},
                {"$group": {
                    "_id": None,
                    "total_answered": {"$sum": "$times_answered"},
                    "avg_quality": {"$avg": "$quality_score"},
                    "high_quality_count": {
                        "$sum": {"$cond": [{"$gte": ["$quality_score", 75]}, 1, 0]}
                    },
                    "never_shown": {
                        "$sum": {"$cond": [{"$eq": ["$times_shown", 0]}, 1, 0]}
                    }
                }}
            ]

            performance_stats = list(self.db.questions.aggregate(performance_pipeline))
            performance = performance_stats[0] if performance_stats else {}

            stats = {
                "total_questions": total_questions,
                "by_type": {stat["_id"]: {
                    "count": stat["count"],
                    "avg_quality": round(stat.get("avg_quality", 0), 1),
                    "avg_shown": round(stat.get("avg_shown", 0), 1),
                    "avg_correct_rate": round(stat.get("avg_correct_rate", 0), 2)
                } for stat in type_stats},
                "by_difficulty": {stat["_id"] or "unspecified": stat["count"] for stat in difficulty_stats},
                "performance": {
                    "total_answered": performance.get("total_answered", 0),
                    "avg_quality": round(performance.get("avg_quality", 0), 1),
                    "high_quality_count": performance.get("high_quality_count", 0),
                    "never_shown": performance.get("never_shown", 0),
                    "high_quality_percentage": round(
                        (performance.get("high_quality_count",
                                         0) / total_questions * 100) if total_questions > 0 else 0, 1
                    )
                }
            }

            return stats

        except Exception as e:
            self.logger.error(f"Error getting question statistics: {e}")
            return {}

    def update_question_performance(self, question_id, answered_correctly):
        try:
            if self.db is None:
                return False

            question = self.db.questions.find_one({"question_id": question_id})
            if not question:
                try:
                    from bson import ObjectId
                    question = self.db.questions.find_one({"_id": ObjectId(question_id)})
                except:
                    self.logger.error(f"Question not found: {question_id}")
                    return False

            if not question:
                return False

            current_answered = question.get("times_answered", 0)
            current_correct = question.get("correct_count", 0)

            new_times_answered = current_answered + 1
            new_correct_count = current_correct + (1 if answered_correctly else 0)
            new_correct_rate = new_correct_count / new_times_answered if new_times_answered > 0 else 0

            update_data = {
                "times_answered": new_times_answered,
                "correct_count": new_correct_count,
                "correct_rate": new_correct_rate,
                "last_answered": datetime.now()
            }

            if new_times_answered >= 3:
                performance_bonus = 0
                if new_correct_rate >= 0.8:
                    performance_bonus = 5
                elif new_correct_rate <= 0.3:
                    performance_bonus = -5

                if performance_bonus != 0:
                    current_quality = question.get("quality_score", 50)
                    new_quality = max(0, min(100, current_quality + performance_bonus))
                    update_data["quality_score"] = new_quality

            result = self.db.questions.update_one(
                {"_id": question["_id"]},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                self.logger.info(f"Updated performance for question {question_id}")
                return True
            else:
                self.logger.warning(f"No changes made to question {question_id}")
                return False

        except Exception as e:
            self.logger.error(f"Error updating question performance: {e}")
            return False

    def regenerate_questions_smart(
            self,
            session_id: str,
            chunk_id: str,
            new_questions: List[Dict],
            keep_best: bool = True
    ) -> bool:
        try:
            kept_questions = []
            if keep_best:
                existing = list(self.db.questions.find({
                    "session_id": session_id,
                    "chunk_id": chunk_id
                }).sort("quality_score", -1).limit(5))

                kept_questions = [q for q in existing
                                  if q.get("correct_rate", 0) > 0.7
                                  and q.get("times_answered", 0) > 3]

            self.db.questions.update_many(
                {"session_id": session_id, "chunk_id": chunk_id},
                {"$set": {"status": "archived", "archived_at": datetime.now()}}
            )

            all_questions = kept_questions + new_questions
            for q in all_questions:
                q.update({
                    "session_id": session_id,
                    "chunk_id": chunk_id,
                    "status": "active",
                    "regenerated": True,
                    "regenerated_at": datetime.now()
                })

            return self.store_questions_with_metadata(all_questions, session_id)

        except Exception as e:
            self.logger.error(f"Error in smart regeneration: {e}")
            return False

    def get_chunks_by_file_hash(self, file_hash: str) -> List[Dict]:
        try:
            if self.db is None:
                return []

            chunks = list(self.db.chunks.find({"file_hash": file_hash}))
            return chunks
        except Exception as e:
            self.logger.error(f"Error getting chunks for file_hash {file_hash}: {e}")
            return []

    def check_file_exists(self, file_hash: str) -> bool:
        try:
            if self.db is None:
                return False

            return self.db.files.find_one({"page_range_hash": file_hash}) is not None
        except Exception as e:
            self.logger.error(f"Error checking file existence: {e}")
            return False

    def get_session_by_id(self, session_id: str) -> Optional[Dict]:
        try:
            if self.db is None:
                return None

            return self.db.sessions.find_one({"session_id": session_id})
        except Exception as e:
            self.logger.error(f"Error getting session {session_id}: {e}")
            return None

    def _calculate_file_hash(self, file_path: str) -> str:
        import hashlib
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256()
                chunk = f.read(8192)
                while chunk:
                    file_hash.update(chunk)
                    chunk = f.read(8192)
            return file_hash.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating file hash: {e}")
            return hashlib.sha256(str(file_path).encode()).hexdigest()

    def _calculate_page_range_hash(self, base_file_hash: str, page_numbers: List[int] = None) -> str:
        import hashlib

        if page_numbers:
            page_str = "-".join(map(str, sorted(page_numbers)))
        else:
            page_str = "all_pages"

        combined = f"{base_file_hash}_{page_str}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def _format_page_range(self, page_numbers: List[int] = None) -> str:
        if not page_numbers:
            return "All pages"
        elif len(page_numbers) == 1:
            return f"Page {page_numbers[0]}"
        else:
            sorted_pages = sorted(page_numbers)
            if len(sorted_pages) <= 5:
                return f"Pages {', '.join(map(str, sorted_pages))}"
            else:
                return f"Pages {sorted_pages[0]}-{sorted_pages[-1]} ({len(sorted_pages)} pages)"

    @staticmethod
    def _generate_session_id(file_hash: str, config: dict) -> str:
        import hashlib

        config_str = json.dumps(config, sort_keys=True)
        combined = f"{file_hash}_{config_str}"

        return hashlib.md5(combined.encode()).hexdigest()[:16]

    def _calculate_quality_score(self, question: dict) -> float:
        score = 50

        q_length = len(question.get("question", "").split())
        if 10 <= q_length <= 30:
            score += 10
        elif q_length < 5 or q_length > 50:
            score -= 10

        if question.get("question_type") == "mcq":
            options = question.get("options", [])
            if len(options) == 4:
                score += 10
            option_lengths = [len(opt) for opt in options]
            if option_lengths and max(option_lengths) / min(option_lengths) < 3:
                score += 10

        if question.get("answer"):
            score += 10
            if len(str(question["answer"])) < 3:
                score -= 5

        return max(0, min(100, score))

    @staticmethod
    def _determine_difficulty(question: dict) -> str:
        question_text = question.get("question", "").lower()
        answer_text = str(question.get("answer", "")).lower()

        easy_keywords = ["what", "when", "who", "define", "name", "identify"]
        medium_keywords = ["how", "why", "explain", "describe", "compare"]
        hard_keywords = ["analyze", "evaluate", "critique", "prove", "derive"]

        if any(kw in question_text for kw in hard_keywords):
            return "hard"
        elif any(kw in question_text for kw in medium_keywords):
            return "medium"
        elif any(kw in question_text for kw in easy_keywords):
            return "easy"

        answer_length = len(answer_text.split())
        if answer_length > 20:
            return "hard"
        elif answer_length > 10:
            return "medium"
        return "easy"

    @staticmethod
    def _generate_question_id(question: dict, session_id: str) -> str:
        import hashlib
        core_data = {
            "session": session_id,
            "chunk": question.get("chunk_id"),
            "content": question.get("question"),
            "type": question.get("question_type")
        }
        return hashlib.md5(json.dumps(core_data, sort_keys=True).encode()).hexdigest()[:16]

    def close(self):
        if self.mongo_client:
            self.mongo_client.close()
            self.logger.info("MongoDB connection closed")