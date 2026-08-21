(function () {
    "use strict";

    const buttons = Array.from(document.querySelectorAll("[data-quiz-reveal-button]"));
    if (!buttons.length) {
        return;
    }

    function getShell(button) {
        const targetId = button.getAttribute("data-quiz-target");
        if (!targetId) {
            return null;
        }
        return document.getElementById(targetId);
    }

    function setButtonState(button, expanded) {
        button.setAttribute("aria-expanded", expanded ? "true" : "false");
        button.textContent = expanded ? "Скрыть тест" : "Пройти тест";
    }

    buttons.forEach((button) => {
        const shell = getShell(button);
        if (!shell) {
            return;
        }

        const quizForm = shell.querySelector("form");
        const shouldReveal = !shell.hasAttribute("hidden");
        setButtonState(button, shouldReveal);

        function revealQuiz(scrollToQuiz) {
            if (shell.hasAttribute("hidden")) {
                shell.hidden = false;
                shell.classList.remove("quiz-form-shell-animating");
                requestAnimationFrame(function () {
                    shell.classList.add("quiz-form-shell-animating");
                    window.setTimeout(function () {
                        shell.classList.remove("quiz-form-shell-animating");
                    }, 220);
                });
                setButtonState(button, true);
                if (scrollToQuiz && quizForm) {
                    const firstQuestion = quizForm.querySelector(".quiz-question");
                    if (firstQuestion) {
                        firstQuestion.scrollIntoView({ behavior: "smooth", block: "start" });
                    } else {
                        shell.scrollIntoView({ behavior: "smooth", block: "start" });
                    }
                }
            }
        }

        button.addEventListener("click", function () {
            if (shell.hasAttribute("hidden")) {
                revealQuiz(true);
            } else {
                shell.hidden = true;
                setButtonState(button, false);
            }
        });

        shell.addEventListener("livequiz:restored", function (event) {
            if (event.detail && event.detail.hasAnswers) {
                revealQuiz(false);
            }
        });
    });
})();
