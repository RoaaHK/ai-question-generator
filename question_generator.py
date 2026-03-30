import requests
import logging


class QuestionGenerator:
    def __init__(self, ollama_api="http://localhost:11434/api/generate", model_name="llama3.1"):
        self.ollama_api = ollama_api
        self.model_name = model_name
        self.logger = logging.getLogger(__name__)
        self.use_mock = False

    def _call_ollama(self, prompt, max_tokens=1000, timeout=120):
        try:
            if len(prompt) > 8000:
                self.logger.warning(f"Prompt too long ({len(prompt)} chars), truncating...")
                prompt = prompt[:8000] + "..."

            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_tokens": max_tokens
                }
            }

            response = requests.post(self.ollama_api, json=payload, timeout=timeout)
            response.raise_for_status()

            result = response.json()
            return result.get("response", "").strip()

        except requests.exceptions.Timeout:
            self.logger.error(f"Ollama timeout after {timeout}s - trying shorter prompt")
            if len(prompt) > 2000:
                short_prompt = prompt[:2000] + "..."
                try:
                    payload["prompt"] = short_prompt
                    response = requests.post(self.ollama_api, json=payload, timeout=60)
                    response.raise_for_status()
                    result = response.json()
                    return result.get("response", "").strip()
                except:
                    pass

            self.logger.error("Ollama timeout - falling back to mock generation")
            self.use_mock = True
            return self._generate_mock_response(prompt)

        except Exception as e:
            self.logger.error(f"Ollama API call failed: {e}")
            self.use_mock = True
            return self._generate_mock_response(prompt)

    def _generate_mock_response(self, prompt):
        text_sample = prompt.replace("Generate", "").replace("questions", "").replace("based on", "")
        words = text_sample.split()[:50]

        if "multiple choice" in prompt.lower():
            return self._create_mock_mcq(words)
        elif "true/false" in prompt.lower():
            return self._create_mock_tf(words)
        else:
            return self._create_mock_sa(words)

    def _create_mock_mcq(self, words):
        key_concepts = [w for w in words if len(w) > 4 and w.isalpha()][:10]
        questions = []
        for i, concept in enumerate(key_concepts[:3], 1):
            questions.append(f"""Question {i}: What is the main characteristic of {concept}?
A) It is primarily used in educational contexts
B) It represents a fundamental concept in the subject
C) It requires detailed understanding
D) It is mentioned in the text

Answer: B""")
        return "\n\n".join(questions)

    def _create_mock_tf(self, words):
        key_concepts = [w for w in words if len(w) > 4 and w.isalpha()][:5]
        statements = []
        for i, concept in enumerate(key_concepts[:3], 1):
            is_true = i % 2 == 1
            statements.append(f"""Statement {i}: The text discusses {concept} in detail.
Answer: {'True' if is_true else 'False'}
Explanation: This {'is' if is_true else 'is not'} directly mentioned in the provided text.""")
        return "\n\n".join(statements)

    def _create_mock_sa(self, words):
        key_concepts = [w for w in words if len(w) > 4 and w.isalpha()][:5]
        questions = []
        for i, concept in enumerate(key_concepts[:3], 1):
            questions.append(f"""Question {i}: Explain the significance of {concept}.
Answer: {concept} is important because it represents a key concept discussed in the text and helps understand the main topics being presented.""")
        return "\n\n".join(questions)

    def generate_mcq(self, text, num_questions, difficulty="medium", custom_instructions=""):
        if len(text) > 4000:
            text = text[:4000] + "..."
            self.logger.info(f"Truncated text to prevent timeout")

        prompt = f"""Generate exactly {num_questions} multiple choice questions based on this text. 
Keep it concise and focused.

Format each question as:
Question: [question text]
A) [option 1]
B) [option 2] 
C) [option 3]
D) [option 4]
Answer: [correct letter]

Text: {text[:2000]}

{custom_instructions}"""

        response = self._call_ollama(prompt, timeout=90)
        self.logger.info(f"MCQ Response received: {len(response)} characters")

        if not response:
            return self._generate_fallback_mcq(text, num_questions)

        questions = self._parse_mcq_response(response, num_questions)

        if not questions:
            questions = self._generate_fallback_mcq(text, num_questions)

        return questions

    def _parse_mcq_response(self, response, num_questions):
        questions = []
        try:
            parts = response.split("Question")

            for i, part in enumerate(parts[1:], 1):
                if i > num_questions:
                    break

                part = "Question" + part
                lines = [line.strip() for line in part.split('\n') if line.strip()]

                if len(lines) < 6:
                    continue

                question_text = ""
                options = []
                answer = "A"

                for line in lines:
                    if line.startswith('Question'):
                        question_text = line.replace('Question:', '').replace(f'Question {i}:', '').strip()
                    elif line.startswith(('A)', 'B)', 'C)', 'D)')):
                        options.append(line[2:].strip())
                    elif line.startswith('Answer:'):
                        answer = line.replace('Answer:', '').strip()

                if question_text and len(options) >= 4:
                    questions.append({
                        "question": question_text,
                        "options": options[:4],
                        "answer": answer,
                        "source": "ollama" if not self.use_mock else "mock"
                    })

        except Exception as e:
            self.logger.error(f"Error parsing MCQ response: {e}")

        return questions

    def _generate_fallback_mcq(self, text, num_questions):
        questions = []
        sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 20][:10]

        for i in range(num_questions):
            base_sentence = sentences[i % len(sentences)] if sentences else f"content from section {i + 1}"

            questions.append({
                "question": f"According to the text, what can be said about {base_sentence[:50]}...?",
                "options": [
                    "It is mentioned as a primary concept",
                    "It is discussed in detail",
                    "It is referenced briefly",
                    "It is not covered in the text"
                ],
                "answer": "A",
                "source": "fallback"
            })

        return questions

    def generate_true_false(self, text, num_questions, difficulty="medium", custom_instructions=""):
        if len(text) > 4000:
            text = text[:4000] + "..."

        prompt = f"""Generate exactly {num_questions} true/false questions based on this text.
Be concise and clear.

Format each as:
Statement: [statement text]
Answer: True/False
Explanation: [brief explanation]

Text: {text[:2000]}

{custom_instructions}"""

        response = self._call_ollama(prompt, timeout=90)

        if not response:
            return self._generate_fallback_tf(text, num_questions)

        questions = self._parse_tf_response(response, num_questions)

        if not questions:
            questions = self._generate_fallback_tf(text, num_questions)

        return questions

    def _parse_tf_response(self, response, num_questions):
        questions = []
        try:
            parts = response.split("Statement")

            for i, part in enumerate(parts[1:], 1):
                if i > num_questions:
                    break

                lines = [line.strip() for line in part.split('\n') if line.strip()]
                if len(lines) < 3:
                    continue

                statement = lines[0].replace(':', '').strip()
                answer = True
                explanation = ""

                for line in lines[1:]:
                    if line.startswith('Answer:'):
                        answer_text = line.replace('Answer:', '').strip().lower()
                        answer = answer_text in ['true', 't', 'yes', '1']
                    elif line.startswith('Explanation:'):
                        explanation = line.replace('Explanation:', '').strip()

                if statement:
                    questions.append({
                        "question": statement,
                        "answer": answer,
                        "explanation": explanation or "Based on the content provided in the text.",
                        "source": "ollama" if not self.use_mock else "mock"
                    })

        except Exception as e:
            self.logger.error(f"Error parsing T/F response: {e}")

        return questions

    def _generate_fallback_tf(self, text, num_questions):
        questions = []
        sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 15][:10]

        for i in range(num_questions):
            if i < len(sentences):
                statement = sentences[i]
                if not statement.endswith('.'):
                    statement += '.'

                questions.append({
                    "question": f"The text states that {statement.lower()}",
                    "answer": True,
                    "explanation": "This information is directly mentioned in the provided text.",
                    "source": "fallback"
                })
            else:
                questions.append({
                    "question": f"The text covers topic number {i + 1} in detail.",
                    "answer": True,
                    "explanation": "Based on the content structure.",
                    "source": "fallback"
                })

        return questions

    def generate_short_answer(self, text, num_questions, difficulty="medium", custom_instructions=""):
        if len(text) > 4000:
            text = text[:4000] + "..."

        prompt = f"""Generate exactly {num_questions} short answer questions based on this text.
Keep questions clear and answers concise.

Format each as:
Question: [question text]
Answer: [answer text]

Text: {text[:2000]}

{custom_instructions}"""

        response = self._call_ollama(prompt, timeout=90)

        if not response:
            return self._generate_fallback_sa(text, num_questions)

        questions = self._parse_sa_response(response, num_questions)

        if not questions:
            questions = self._generate_fallback_sa(text, num_questions)

        return questions

    def _parse_sa_response(self, response, num_questions):
        questions = []
        try:
            parts = response.split("Question")

            for i, part in enumerate(parts[1:], 1):
                if i > num_questions:
                    break

                lines = [line.strip() for line in part.split('\n') if line.strip()]
                if len(lines) < 2:
                    continue

                question_text = lines[0].replace(':', '').strip()
                answer = ""

                for line in lines[1:]:
                    if line.startswith('Answer:'):
                        answer = line.replace('Answer:', '').strip()
                        break

                if question_text and answer:
                    questions.append({
                        "question": question_text,
                        "answer": answer,
                        "source": "ollama" if not self.use_mock else "mock"
                    })

        except Exception as e:
            self.logger.error(f"Error parsing SA response: {e}")

        return questions

    def _generate_fallback_sa(self, text, num_questions):
        questions = []
        sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 20][:10]

        question_starters = [
            "What is the main concept discussed about",
            "How does the text explain",
            "Why is it important to understand",
            "What are the key points regarding",
            "Describe the significance of"
        ]

        for i in range(num_questions):
            starter = question_starters[i % len(question_starters)]
            if i < len(sentences):
                words = sentences[i].split()[:5]
                topic = ' '.join(words)
            else:
                topic = f"the topic in section {i + 1}"

            questions.append({
                "question": f"{starter} {topic}?",
                "answer": f"According to the text, {topic} is significant because it relates to the core concepts discussed and provides important information for understanding the subject matter.",
                "source": "fallback"
            })

        return questions

    def test_connection(self):
        try:
            response = self._call_ollama("Hello", max_tokens=10, timeout=30)
            result = bool(response and not self.use_mock)
            self.logger.info(f"Connection test result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False