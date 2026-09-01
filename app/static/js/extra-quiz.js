(function () {
    "use strict";
    const form = document.querySelector("[data-extra-quiz]");
    if (!form || !window.fetch) return;
    const csrf = form.querySelector('input[name="_csrf_token"]');
    const submit = form.querySelector(".quiz-submit");
    const questions = Array.from(form.querySelectorAll("[data-live-question]"));
    submit.type = "submit";
    submit.disabled = true;
    submit.textContent = "Ответьте на все вопросы";

    function answerOf(fieldset) {
        const inputs = Array.from(fieldset.querySelectorAll("input:not([type=hidden])"));
        const text = inputs.find(function (input) { return input.type === "text"; });
        if (text) return text.value.trim();
        const checked = inputs.filter(function (input) { return input.checked; });
        return fieldset.classList.contains("quiz-question-multiple")
            ? checked.map(function (input) { return input.value; })
            : (checked[0] ? checked[0].value : "");
    }

    function feedback(fieldset, text, correct) {
        const box = fieldset.querySelector("[data-live-feedback]");
        box.className = "quiz-inline-feedback " + (correct ? "quiz-inline-feedback-correct" : "quiz-inline-feedback-wrong");
        box.textContent = text;
        box.hidden = false;
    }

    function lock(fieldset) {
        fieldset.querySelectorAll("input:not([type=hidden])").forEach(function (input) {
            if ((input.type === "text" && input.value.trim()) || input.checked) {
                const mirror = document.createElement("input");
                mirror.type = "hidden";
                mirror.name = input.name;
                mirror.value = input.value;
                fieldset.appendChild(mirror);
            }
            input.disabled = true;
        });
        fieldset.dataset.answered = "true";
        fieldset.querySelector("[data-answer-question]").disabled = true;
    }

    form.addEventListener("click", async function (event) {
        const button = event.target.closest("[data-answer-question]");
        if (!button) return;
        const fieldset = button.closest("[data-live-question]");
        const answer = answerOf(fieldset);
        if ((Array.isArray(answer) && answer.length === 0) || answer === "") {
            feedback(fieldset, "Сначала выберите или напишите ответ.", false);
            return;
        }
        button.disabled = true;
        try {
            const response = await fetch(form.dataset.checkUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {"Content-Type": "application/json", "X-CSRFToken": csrf.value},
                body: JSON.stringify({course: form.dataset.course, item_number: Number(form.dataset.itemNumber), question_index: Number(fieldset.dataset.questionIndex), answer: answer})
            });
            if (!response.ok) throw new Error("check_failed");
            const result = await response.json();
            lock(fieldset);
            feedback(fieldset, result.correct ? "Верно. " + result.explanation : "Неверно. Правильный ответ: " + result.correct_answer + ". " + result.explanation, result.correct);
            const complete = questions.every(function (question) { return question.dataset.answered === "true"; });
            submit.disabled = !complete;
            submit.textContent = complete ? "Завершить тест" : "Ответьте на все вопросы";
        } catch (_error) {
            button.disabled = false;
            feedback(fieldset, "Не удалось проверить ответ. Повторите попытку.", false);
        }
    });
}());
