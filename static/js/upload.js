document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('uploadForm');
    const allPagesCheckbox = document.getElementById('all_pages');
    const fromPageInput = document.getElementById('from_page');
    const toPageInput = document.getElementById('to_page');
    const fileInput = document.getElementById('file-input');
    const fileNameDisplay = document.getElementById('file-name-display');
    const fileError = document.getElementById('file-error');
    const questionTypeError = document.getElementById('question-type-error');
    const pageRangeError = document.getElementById('page-range-error');
    const questionsPerChunkInput = document.getElementById('questions_per_chunk');

    fromPageInput.disabled = allPagesCheckbox.checked;
    toPageInput.disabled = allPagesCheckbox.checked;

    allPagesCheckbox.addEventListener('change', function() {
        fromPageInput.disabled = this.checked;
        toPageInput.disabled = this.checked;

        if(this.checked) {
            fromPageInput.value = '';
            toPageInput.value = '';
            pageRangeError.style.display = 'none';
        }
    });

    fileInput.addEventListener('change', function() {
        if(this.files.length > 0) {
            const file = this.files[0];
            fileNameDisplay.textContent = file.name;
            fileInput.parentElement.classList.add('has-file');

            if (file.type !== 'application/pdf') {
                fileError.textContent = 'Please upload a PDF file';
                fileError.style.display = 'block';
                this.value = '';
                fileNameDisplay.textContent = 'No file chosen';
                fileInput.parentElement.classList.remove('has-file');
            } else {
                fileError.style.display = 'none';
            }
        } else {
            fileNameDisplay.textContent = 'No file chosen';
            fileError.style.display = 'none';
            fileInput.parentElement.classList.remove('has-file');
        }
    });

    const questionTypeCheckboxes = document.querySelectorAll('input[name="question_types"]');
    questionTypeCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const anySelected = Array.from(questionTypeCheckboxes).some(cb => cb.checked);
            if (anySelected) {
                questionTypeError.style.display = 'none';
            }
        });
    });

    questionsPerChunkInput.addEventListener('input', function() {
        this.setCustomValidity('');
    });

    fromPageInput.addEventListener('input', function() {
        if (pageRangeError.style.display === 'block') {
            pageRangeError.style.display = 'none';
        }
    });

    toPageInput.addEventListener('input', function() {
        if (pageRangeError.style.display === 'block') {
            pageRangeError.style.display = 'none';
        }
    });

    form.addEventListener('submit', function(e) {
        let isValid = true;

        questionTypeError.style.display = 'none';
        pageRangeError.style.display = 'none';
        questionsPerChunkInput.setCustomValidity('');

        const questionTypes = document.querySelectorAll('input[name="question_types"]:checked');
        if (questionTypes.length === 0) {
            questionTypeError.textContent = 'Please select at least one question type';
            questionTypeError.style.display = 'block';
            isValid = false;
        }

        const questionsPerChunkValue = parseInt(questionsPerChunkInput.value);
        if (!questionsPerChunkInput.value || isNaN(questionsPerChunkValue) || questionsPerChunkValue < 1 || questionsPerChunkValue > 35) {
            questionsPerChunkInput.setCustomValidity('Please enter a number between 1 and 35');
            questionsPerChunkInput.reportValidity();
            isValid = false;
        }

        if (!allPagesCheckbox.checked) {
            const fromPage = parseInt(fromPageInput.value);
            const toPage = parseInt(toPageInput.value);

            if (!fromPageInput.value || isNaN(fromPage) || fromPage < 1) {
                pageRangeError.textContent = 'Please enter a valid starting page (minimum 1)';
                pageRangeError.style.display = 'block';
                isValid = false;
            } else if (!toPageInput.value || isNaN(toPage) || toPage < 1) {
                pageRangeError.textContent = 'Please enter a valid ending page (minimum 1)';
                pageRangeError.style.display = 'block';
                isValid = false;
            } else if (fromPage > toPage) {
                pageRangeError.textContent = 'Ending page must be greater than or equal to starting page';
                pageRangeError.style.display = 'block';
                isValid = false;
            }
        }

        if (!isValid) {
            e.preventDefault();
        }
    });
});