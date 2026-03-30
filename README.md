# 🎓 AI-Based Educational Question Generator

An AI-powered platform that automatically generates curriculum-aligned questions from science textbooks using LLaMA 3.1.

## 📌 Overview
This project is a full-stack educational platform designed to generate high-quality, curriculum-aligned questions from science textbooks. It leverages LLaMA 3.1 through Ollama to generate questions from textbook content, after applying a preprocessing pipeline that handles complex scientific notation and mathematical expressions.

The system processes PDF textbooks and produces questions that closely match human-generated ones in quality and relevance.

## ✨ Key Features
- 📄 Automatic processing of PDF science textbooks
- 🤖 AI-powered question generation using LLaMA 3.1 (Ollama)
- 🔍 Intelligent text chunking and preprocessing pipeline
- 📊 Real-time feedback and question export functionality
- 🌐 Responsive and interactive web interface
- ✅ 93% semantic similarity to human-written questions
- 📝 82% content retention score

## 🛠️ Tech Stack

| Category       | Technology                                         |
|----------------|----------------------------------------------------|
| Backend        | Python, Flask                                      |
| Database       | MongoDB                                            |
| AI Model       | LLaMA 3.1 (via Ollama)                             |
| Frontend       | HTML, CSS, JavaScript                              |
| PDF Processing | Text extraction, preprocessing & chunking pipeline |
| Evaluation     | BLEU, ROUGE-1, ROUGE-L, Cosine Similarity          |

## 🏗️ System Architecture
- Flask REST API handles backend logic and communication
- MongoDB stores textbooks, generated questions, and user data
- Text processing pipeline handles chunking and preprocessing of PDF content
- LLaMA 3.1 generates context-aware questions via Ollama
- Frontend UI enables real-time interaction and export features

## ⚙️ Getting Started

### Prerequisites
- Python 3.9+
- MongoDB installed and running
- Ollama installed with LLaMA 3.1 model

### Installation & Setup

1. Clone the repository
```bash
git clone https://github.com/RoaaHK/ai-science-question-generator.git
cd ai-science-question-generator
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Download the model
```bash
ollama pull llama3.1
```

4. Start MongoDB
```bash
mongod
```

5. Run the application
```bash
python app.py
```

6. Open in browser
```
http://localhost:5000
```

## 📊 Model Evaluation

| Metric            | Score |
|-------------------|-------|
| Cosine Similarity | 0.93  |
| ROUGE-1           | 0.82  |
| ROUGE-L           | 0.78  |
| BLEU              | 0.44  |

## 👨‍💻 Authors
- Roaa Al-Kisbeh
- Maryam Ali

Graduation Project — 2025

## 📄 License
This project is licensed under the MIT License.
