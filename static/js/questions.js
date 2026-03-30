document.addEventListener('DOMContentLoaded', function() {

    function toggleChunks(checkbox) {
        const chunkSections = document.querySelectorAll('.chunk-section');
        chunkSections.forEach(section => {
            if (checkbox.checked) {
                section.classList.remove('hidden');
            } else {
                section.classList.add('hidden');
            }
        });
    }

    function toggleAnswer(button) {
        const answerElement = button.nextElementSibling;
        if (answerElement && answerElement.classList.contains('hidden')) {
            answerElement.classList.remove('hidden');
            button.innerHTML = '<span class="toggle-icon"></span> Hide Answer';
        } else if (answerElement) {
            answerElement.classList.add('hidden');
            button.innerHTML = '<span class="toggle-icon"></span> Show Answer';
        }
    }

    const chunkToggle = document.getElementById('show-chunks-toggle');
    if (chunkToggle) {
        chunkToggle.addEventListener('change', function() {
            toggleChunks(this);
        });
    }

    const answerButtons = document.querySelectorAll('.toggle-btn');
    answerButtons.forEach(button => {
        button.addEventListener('click', function() {
            toggleAnswer(this);
        });
    });

});