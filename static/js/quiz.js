document.addEventListener('DOMContentLoaded', function() {
    const questions = document.querySelectorAll('.quiz-question');
    const prevButton = document.getElementById('prev-button');
    const nextButton = document.getElementById('next-button');
    const currentQuestionEl = document.getElementById('current-question');
    const totalQuestionsEl = document.getElementById('total-questions');
    const resultsEl = document.querySelector('.quiz-results');
    const scoreEl = document.getElementById('score');
    const totalEl = document.getElementById('total');
    const retryButton = document.getElementById('retry-button');
    const resultsBreakdownEl = document.getElementById('results-breakdown');
    const loadingOverlay = document.getElementById('loading-overlay');
    const filterForm = document.getElementById('filter-form');

    let currentIndex = 0;
    let answers = new Array(questions.length).fill(null);
    let results = new Array(questions.length).fill(null);
    let answeredCount = 0;
    let checkedQuestions = new Set();

    updateButtonState();

    function showLoading() {
        if (loadingOverlay) {
            loadingOverlay.style.display = 'flex';
        }
    }

    function hideLoading() {
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
    }

    prevButton.addEventListener('click', showPreviousQuestion);
    nextButton.addEventListener('click', handleNextClick);
    retryButton.addEventListener('click', resetQuiz);

    if (filterForm) {
        filterForm.addEventListener('submit', function() {
            showLoading();
        });
    }

    document.querySelectorAll('.filter-option').forEach(option => {
        option.addEventListener('click', function() {
            const checkbox = this.querySelector('input[type="checkbox"]');
            if (checkbox) {
                checkbox.checked = !checkbox.checked;
                this.classList.toggle('active');
            }
        });
    });

    document.querySelectorAll('.mcq-option').forEach(option => {
        option.addEventListener('click', function() {
            const questionElement = this.closest('.quiz-question');
            const questionIndex = parseInt(questionElement.dataset.index) - 1;
            const options = questionElement.querySelectorAll('.mcq-option');

            options.forEach(opt => {
                opt.classList.remove('selected');
            });

            this.classList.add('selected');

            answers[questionIndex] = this.dataset.value;
            console.log(`MCQ Question ${questionIndex + 1}: Selected ${this.dataset.value}`);
        });
    });

    document.querySelectorAll('.tf-option').forEach(option => {
        option.addEventListener('click', function() {
            const questionElement = this.closest('.quiz-question');
            const questionIndex = parseInt(questionElement.dataset.index) - 1;
            const options = questionElement.querySelectorAll('.tf-option');

            options.forEach(opt => {
                opt.classList.remove('selected');
            });

            this.classList.add('selected');

            answers[questionIndex] = this.dataset.value;
            console.log(`T/F Question ${questionIndex + 1}: Selected ${this.dataset.value}`);
        });
    });

    document.querySelectorAll('.user-answer').forEach((textarea, index) => {
        textarea.addEventListener('input', function() {
            answers[index] = this.value.trim();
            console.log(`Short Answer Question ${index + 1}: "${this.value.trim()}"`);
        });
    });

    document.querySelectorAll('.check-answer').forEach((button, index) => {
        button.addEventListener('click', function() {
            checkAnswer(index);
        });
    });

    function showQuestion(index) {
        questions.forEach(q => q.classList.remove('active'));
        questions[index].classList.add('active');
        currentQuestionEl.textContent = index + 1;
        currentIndex = index;
        updateButtonState();
    }

    function handleNextClick() {
        if (currentIndex < questions.length - 1) {
            showNextQuestion();
        } else {
            finishQuiz();
        }
    }

    function showNextQuestion() {
        if (currentIndex < questions.length - 1) {
            showQuestion(currentIndex + 1);
        }
    }

    function showPreviousQuestion() {
        if (currentIndex > 0) {
            showQuestion(currentIndex - 1);
        }
    }

    function updateButtonState() {
        prevButton.disabled = currentIndex === 0;
        nextButton.textContent = currentIndex === questions.length - 1 ? 'Finish' : 'Next';
    }

    function finishQuiz() {
        showLoading();

        questions.forEach((question, index) => {
            if (!checkedQuestions.has(index)) {
                gradeQuestion(index, false);
            }
        });

        setTimeout(() => {
            hideLoading();
            showResults();
        }, 500);
    }

    function checkAnswer(index) {
        showLoading();

        setTimeout(() => {
            gradeQuestion(index, true);
            hideLoading();
        }, 300);
    }

    function gradeQuestion(index, showFeedback = true) {
        const question = questions[index];
        const questionType = question.dataset.type;
        let correctAnswer = question.dataset.answer;
        let userAnswer = answers[index] || '';

        console.log(`\n=== Grading Question ${index + 1} ===`);
        console.log(`Type: ${questionType}`);
        console.log(`Correct Answer: "${correctAnswer}"`);
        console.log(`User Answer: "${userAnswer}"`);

        if (!userAnswer) {
            if (questionType === 'mcq') {
                const selectedOption = question.querySelector('.mcq-option.selected');
                userAnswer = selectedOption ? selectedOption.dataset.value : '';
            } else if (questionType === 'true_false') {
                const selectedOption = question.querySelector('.tf-option.selected');
                userAnswer = selectedOption ? selectedOption.dataset.value : '';
            } else {
                const textArea = question.querySelector('.user-answer');
                userAnswer = textArea ? textArea.value.trim() : '';
            }
            answers[index] = userAnswer;
        }

        let isCorrect = false;

        if (questionType === 'mcq' || questionType === 'true_false') {
            const cleanCorrect = normalizeAnswer(correctAnswer);
            const cleanUser = normalizeAnswer(userAnswer);

            isCorrect = cleanCorrect === cleanUser;

            if (!isCorrect && questionType === 'mcq') {
                const correctLetter = correctAnswer.match(/^([A-D])\)/)?.[1];
                if (correctLetter && userAnswer === correctLetter) {
                    isCorrect = true;
                }

                if (correctAnswer.length === 1 && correctAnswer.match(/[A-D]/) && userAnswer === correctAnswer) {
                    isCorrect = true;
                }
            }

        } else if (questionType === 'short_answer') {
            isCorrect = checkShortAnswer(userAnswer, correctAnswer);
        }

        console.log(`Result: ${isCorrect ? 'CORRECT' : 'INCORRECT'}`);

        results[index] = isCorrect;
        checkedQuestions.add(index);

        if (showFeedback) {
            const feedbackEl = question.querySelector('.feedback');
            const correctAnswerEl = question.querySelector('.correct-answer');
            const checkButton = question.querySelector('.check-answer');

            if (questionType === 'mcq' || questionType === 'true_false') {
                const optionSelector = questionType === 'mcq' ? '.mcq-option' : '.tf-option';
                question.querySelectorAll(optionSelector).forEach(option => {
                    const optionValue = option.dataset.value;
                    const normalizedOptionValue = normalizeAnswer(optionValue);
                    const normalizedCorrectAnswer = normalizeAnswer(correctAnswer);

                    if (normalizedOptionValue === normalizedCorrectAnswer ||
                        (questionType === 'mcq' && correctAnswer.startsWith(optionValue + ')'))) {
                        option.classList.add('correct');
                    } else if (option.classList.contains('selected') && !isCorrect) {
                        option.classList.add('incorrect');
                    }
                });
            }

            showFeedbackMessage(feedbackEl, isCorrect ? 'Correct!' : 'Incorrect', isCorrect);
            if (correctAnswerEl) {
                correctAnswerEl.style.display = 'block';
            }

            if (checkButton) {
                checkButton.style.display = 'none';
            }
            question.querySelectorAll('.mcq-option, .tf-option').forEach(option => {
                option.style.pointerEvents = 'none';
            });

            const textArea = question.querySelector('.user-answer');
            if (textArea) {
                textArea.disabled = true;
            }

            question.classList.add('answered');
        }

        sendAnswerToServer(question, isCorrect);
    }

    function normalizeAnswer(answer) {
        if (!answer) return '';

        return answer.toString()
            .toLowerCase()
            .trim()
            .replace(/[^\w\s]/g, '')
            .replace(/\s+/g, ' ');
    }

    function checkShortAnswer(userAnswer, correctAnswer) {
        if (!userAnswer || !correctAnswer) return false;

        const userNorm = normalizeAnswer(userAnswer);
        const correctNorm = normalizeAnswer(correctAnswer);

        console.log(`Short answer comparison:`);
        console.log(`  User (normalized): "${userNorm}"`);
        console.log(`  Correct (normalized): "${correctNorm}"`);

        if (userNorm === correctNorm) {
            console.log(`  Match type: Direct`);
            return true;
        }

        if (userNorm.includes(correctNorm) || correctNorm.includes(userNorm)) {
            console.log(`  Match type: Contains`);
            return true;
        }

        const correctWords = correctNorm.split(' ').filter(word => word.length > 2);
        const userWords = userNorm.split(' ').filter(word => word.length > 2);

        const matchingWords = correctWords.filter(word => userWords.includes(word));
        const matchRatio = matchingWords.length / correctWords.length;

        console.log(`  Key words match: ${matchingWords.length}/${correctWords.length} (${Math.round(matchRatio * 100)}%)`);

        if (matchRatio >= 0.6) {
            console.log(`  Match type: Key words`);
            return true;
        }

        const scientificMatches = [
            ['boiling point', 'boiling', 'bp'],
            ['melting point', 'melting', 'mp'],
            ['density', 'dense'],
            ['mass', 'weight'],
            ['volume', 'size'],
            ['temperature', 'temp'],
            ['magnetism', 'magnetic', 'magnet'],
            ['conductivity', 'conductive', 'conduct']
        ];

        for (const synonyms of scientificMatches) {
            if (synonyms.some(syn => correctNorm.includes(syn)) &&
                synonyms.some(syn => userNorm.includes(syn))) {
                console.log(`  Match type: Scientific synonym`);
                return true;
            }
        }

        console.log(`  Match type: None`);
        return false;
    }

    function sendAnswerToServer(question, isCorrect) {
        const questionId = question.dataset.questionId || question.querySelector('[data-question-id]')?.dataset.questionId;

        if (questionId) {
            fetch(`/api/question/${questionId}/answer`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    correct: isCorrect
                })
            }).catch(error => {
                console.log('Failed to record answer:', error);
            });
        }
    }

    function showFeedbackMessage(element, message, isCorrect) {
        if (element) {
            element.textContent = message;
            element.className = 'feedback ' + (isCorrect ? 'correct' : 'incorrect');
            element.style.display = 'block';
        }
    }

    function showResults() {
        document.querySelector('.quiz-container').style.display = 'none';

        const score = results.filter(result => result === true).length;
        const totalQuestions = questions.length;
        const percentage = Math.round((score / totalQuestions) * 100);

        scoreEl.textContent = score;
        totalEl.textContent = totalQuestions;

        const scoreElement = document.querySelector('.quiz-score');
        scoreElement.innerHTML = `
            Score: <span style="color: ${getScoreColor(percentage)}">${score} / ${totalQuestions}</span>
            <div style="font-size: 0.8em; margin-top: 10px; color: #666;">
                ${percentage}% - ${getPerformanceMessage(percentage)}
            </div>
        `;

        resultsBreakdownEl.innerHTML = generateDetailedResultsBreakdown();

        resultsEl.style.display = 'block';

        resultsEl.scrollIntoView({ behavior: 'smooth' });
    }

    function getScoreColor(percentage) {
        if (percentage >= 80) return '#28a745';
        if (percentage >= 60) return '#ffc107';
        if (percentage >= 40) return '#fd7e14';
        return '#dc3545';
    }

    function getPerformanceMessage(percentage) {
        if (percentage >= 90) return 'Excellent!';
        if (percentage >= 80) return 'Great job!';
        if (percentage >= 70) return 'Good work!';
        if (percentage >= 60) return 'Not bad!';
        if (percentage >= 50) return 'Keep studying!';
        return 'Need more practice!';
    }

    function generateDetailedResultsBreakdown() {
        let breakdownHTML = '<div style="max-height: 400px; overflow-y: auto; text-align: left;">';
        breakdownHTML += '<h4 style="text-align: center; margin-bottom: 20px;">Question Breakdown</h4>';

        results.forEach((result, index) => {
            const question = questions[index];
            const questionText = question.querySelector('.question-text').textContent;
            const questionType = question.dataset.type;
            const correctAnswer = question.dataset.answer;
            const userAnswer = answers[index] || 'No answer';

            const truncatedQuestion = questionText.length > 80 ?
                questionText.substring(0, 80) + '...' : questionText;

            const resultColor = result ? '#d4edda' : '#f8d7da';
            const resultIcon = result ? '' : '';
            const resultText = result ? 'Correct' : 'Incorrect';

            breakdownHTML += `
                <div style="margin-bottom: 15px; padding: 12px; border-radius: 8px; background-color: ${resultColor}; };">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <strong>Q${index + 1}. [${questionType.replace('_', ' ').toUpperCase()}]</strong>
                        <span style="font-weight: bold;">${resultIcon} ${resultText}</span>
                    </div>
                    <div style="margin-bottom: 8px; font-size: 0.9em; color: #495057;">
                        ${truncatedQuestion}
                    </div>
                    <div style="font-size: 0.8em; color: #6c757d;">
                        <div><strong>Your answer:</strong> ${userAnswer}</div>
                        <div><strong>Correct answer:</strong> ${correctAnswer}</div>
                    </div>
                </div>
            `;
        });

        breakdownHTML += '</div>';
        return breakdownHTML;
    }

    function resetQuiz() {
        showLoading();

        setTimeout(() => {
            answers = new Array(questions.length).fill(null);
            results = new Array(questions.length).fill(null);
            answeredCount = 0;
            checkedQuestions.clear();

            document.querySelectorAll('.mcq-option, .tf-option').forEach(option => {
                option.classList.remove('selected', 'correct', 'incorrect');
                option.style.pointerEvents = 'auto';
            });

            document.querySelectorAll('.user-answer').forEach(textarea => {
                textarea.value = '';
                textarea.disabled = false;
            });

            document.querySelectorAll('.feedback, .correct-answer').forEach(el => {
                el.style.display = 'none';
            });

            document.querySelectorAll('.check-answer').forEach(button => {
                button.style.display = 'block';
            });

            document.querySelectorAll('.quiz-question').forEach(q => {
                q.classList.remove('answered');
            });

            document.querySelector('.quiz-container').style.display = 'block';

            resultsEl.style.display = 'none';

            showQuestion(0);

            hideLoading();
        }, 300);
    }
});