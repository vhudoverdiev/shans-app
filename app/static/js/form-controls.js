(function () {
    "use strict";

    const SELECTOR_SELECT = "select.form-input:not([multiple]):not([data-native-control])";
    const SELECTOR_DATE = [
        "input.form-input[type='date']:not([data-native-control])",
        "input.form-input[type='datetime-local']:not([data-native-control])",
    ].join(", ");
    const SELECTOR_MONTH = "input.form-input[type='month']:not([data-native-control])";
    const MONTH_NAMES = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ];
    const WEEKDAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

    let activeControl = null;

    function closeActiveControl() {
        if (activeControl && typeof activeControl.close === "function") {
            activeControl.close();
        }
    }

    function padNumber(value) {
        return String(value).padStart(2, "0");
    }

    function formatIsoDate(year, monthIndex, day) {
        return year + "-" + padNumber(monthIndex + 1) + "-" + padNumber(day);
    }

    function parseIsoDate(value) {
        const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
        if (!match) return null;

        const year = Number(match[1]);
        const monthIndex = Number(match[2]) - 1;
        const day = Number(match[3]);
        const date = new Date(year, monthIndex, day);
        if (
            date.getFullYear() !== year
            || date.getMonth() !== monthIndex
            || date.getDate() !== day
        ) {
            return null;
        }

        return date;
    }

    function parseIsoMonth(value) {
        const match = /^(\d{4})-(\d{2})$/.exec(String(value || ""));
        if (!match) return null;

        const year = Number(match[1]);
        const monthIndex = Number(match[2]) - 1;
        if (monthIndex < 0 || monthIndex > 11) return null;
        return { year: year, monthIndex: monthIndex };
    }

    function datePart(value) {
        return String(value || "").split("T")[0] || "";
    }

    function timePart(value) {
        const parts = String(value || "").split("T");
        return parts.length > 1 && parts[1] ? parts[1] : "00:00";
    }

    function formatDateButtonText(input) {
        const date = parseIsoDate(datePart(input.value));
        if (!date) return input.getAttribute("placeholder") || "";

        const dateText = [
            padNumber(date.getDate()),
            padNumber(date.getMonth() + 1),
            date.getFullYear(),
        ].join(".");
        if (input.type !== "datetime-local") return dateText;

        return dateText + " " + timePart(input.value);
    }

    function formatMonthButtonText(input) {
        const selected = parseIsoMonth(input.value);
        if (!selected) return input.getAttribute("placeholder") || "";

        return padNumber(selected.monthIndex + 1) + "." + selected.year;
    }

    function compareIsoDates(first, second) {
        if (!first || !second) return 0;
        if (first === second) return 0;
        return first < second ? -1 : 1;
    }

    function dispatchNativeChange(element) {
        element.dispatchEvent(new Event("input", { bubbles: true }));
        element.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function placeFloatingPanel(panel, anchor) {
        const rect = anchor.getBoundingClientRect();
        const gap = 8;
        const viewportPadding = 12;
        const shouldMatchAnchorWidth = !panel.classList.contains("custom-date-panel");
        const preferredWidth = shouldMatchAnchorWidth
            ? Math.max(rect.width, panel.offsetWidth || 0)
            : (panel.offsetWidth || rect.width);

        panel.style.minWidth = shouldMatchAnchorWidth ? rect.width + "px" : "";
        panel.style.maxWidth = "calc(100vw - " + (viewportPadding * 2) + "px)";

        const panelRect = panel.getBoundingClientRect();
        let left = rect.left;
        if (left + preferredWidth > window.innerWidth - viewportPadding) {
            left = window.innerWidth - viewportPadding - preferredWidth;
        }
        left = Math.max(viewportPadding, left);

        let top = rect.bottom + gap;
        if (top + panelRect.height > window.innerHeight - viewportPadding) {
            const aboveTop = rect.top - panelRect.height - gap;
            if (aboveTop >= viewportPadding) {
                top = aboveTop;
            } else {
                top = window.innerHeight - viewportPadding - panelRect.height;
            }
        }

        panel.style.left = Math.round(left) + "px";
        panel.style.top = Math.round(Math.max(viewportPadding, top)) + "px";
    }

    function isClickInside(event, elements) {
        return elements.some(function (element) {
            return element && (element === event.target || element.contains(event.target));
        });
    }

    function enhanceSelect(select) {
        if (select.dataset.customControlReady === "select") return;
        select.dataset.customControlReady = "select";

        const wrapper = document.createElement("div");
        wrapper.className = "custom-select";
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);
        select.classList.add("custom-native-control");
        select.tabIndex = -1;

        const button = document.createElement("button");
        button.type = "button";
        button.className = "custom-select-button";
        button.setAttribute("aria-haspopup", "listbox");
        button.setAttribute("aria-expanded", "false");
        button.disabled = select.disabled;

        const buttonText = document.createElement("span");
        buttonText.className = "custom-select-button-text";
        const arrow = document.createElement("span");
        arrow.className = "custom-select-arrow";
        arrow.setAttribute("aria-hidden", "true");
        button.append(buttonText, arrow);
        wrapper.appendChild(button);

        const menu = document.createElement("div");
        menu.className = "custom-select-menu custom-floating-panel";
        menu.setAttribute("role", "listbox");
        menu.hidden = true;
        document.body.appendChild(menu);

        let activeIndex = Math.max(0, select.selectedIndex);

        function options() {
            return Array.from(select.options);
        }

        function selectedOption() {
            return select.options[select.selectedIndex] || select.options[0] || null;
        }

        function syncButton() {
            const option = selectedOption();
            buttonText.textContent = option ? option.textContent.trim() : "Выберите";
            button.disabled = select.disabled;
            wrapper.classList.toggle("custom-control-disabled", select.disabled);
        }

        function setActiveIndex(nextIndex) {
            const optionNodes = Array.from(menu.querySelectorAll(".custom-select-option"));
            const enabledNodes = optionNodes.filter(function (node) {
                return node.getAttribute("aria-disabled") !== "true";
            });
            if (!optionNodes.length || !enabledNodes.length) return;

            const clampedIndex = Math.max(0, Math.min(nextIndex, optionNodes.length - 1));
            activeIndex = clampedIndex;
            optionNodes.forEach(function (node, index) {
                node.classList.toggle("custom-select-option-active", index === activeIndex);
            });

            const activeNode = optionNodes[activeIndex];
            if (activeNode && activeNode.getAttribute("aria-disabled") === "true") {
                const fallback = enabledNodes[0];
                activeIndex = optionNodes.indexOf(fallback);
                fallback.classList.add("custom-select-option-active");
            }
        }

        function chooseOption(index) {
            const option = select.options[index];
            if (!option || option.disabled) return;

            select.selectedIndex = index;
            syncButton();
            dispatchNativeChange(select);
            close();
            button.focus();
        }

        function renderMenu() {
            menu.textContent = "";
            options().forEach(function (option, index) {
                const item = document.createElement("button");
                item.type = "button";
                item.className = "custom-select-option";
                item.setAttribute("role", "option");
                item.setAttribute("aria-selected", index === select.selectedIndex ? "true" : "false");
                if (option.disabled) {
                    item.setAttribute("aria-disabled", "true");
                    item.disabled = true;
                }
                item.textContent = option.textContent.trim();
                item.addEventListener("click", function () {
                    chooseOption(index);
                });
                menu.appendChild(item);
            });
            activeIndex = Math.max(0, select.selectedIndex);
            setActiveIndex(activeIndex);
        }

        function reposition() {
            if (!menu.hidden) {
                placeFloatingPanel(menu, button);
            }
        }

        function open() {
            if (select.disabled) return;
            if (activeControl && activeControl.close !== close) {
                closeActiveControl();
            }
            renderMenu();
            menu.hidden = false;
            button.setAttribute("aria-expanded", "true");
            wrapper.classList.add("custom-control-open");
            activeControl = { close: close };
            window.requestAnimationFrame(reposition);
        }

        function close() {
            menu.hidden = true;
            button.setAttribute("aria-expanded", "false");
            wrapper.classList.remove("custom-control-open");
            if (activeControl && activeControl.close === close) {
                activeControl = null;
            }
        }

        button.addEventListener("click", function () {
            if (menu.hidden) {
                open();
            } else {
                close();
            }
        });

        button.addEventListener("keydown", function (event) {
            const optionCount = select.options.length;
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                if (menu.hidden) {
                    open();
                    return;
                }
                const direction = event.key === "ArrowDown" ? 1 : -1;
                let nextIndex = activeIndex;
                for (let step = 0; step < optionCount; step += 1) {
                    nextIndex = (nextIndex + direction + optionCount) % optionCount;
                    if (!select.options[nextIndex].disabled) break;
                }
                setActiveIndex(nextIndex);
                return;
            }

            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                if (menu.hidden) {
                    open();
                } else {
                    chooseOption(activeIndex);
                }
                return;
            }

            if (event.key === "Escape") {
                close();
            }
        });

        select.addEventListener("change", syncButton);
        select.addEventListener("invalid", function () {
            button.classList.add("custom-control-invalid");
            button.focus();
        });
        select.addEventListener("input", function () {
            button.classList.remove("custom-control-invalid");
        });
        select.form && select.form.addEventListener("reset", function () {
            window.setTimeout(syncButton, 0);
        });
        window.addEventListener("resize", reposition);
        window.addEventListener("scroll", reposition, true);

        syncButton();
    }

    function enhanceDateInput(input) {
        if (input.dataset.customControlReady === "date") return;
        input.dataset.customControlReady = "date";

        const wrapper = document.createElement("div");
        wrapper.className = "custom-date";
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);
        input.classList.add("custom-date-input", "custom-native-control");
        input.tabIndex = -1;

        const button = document.createElement("button");
        button.type = "button";
        button.className = "custom-date-button";
        button.setAttribute("aria-label", "Открыть календарь");
        const buttonText = document.createElement("span");
        buttonText.className = "custom-date-value";
        const buttonIcon = document.createElement("span");
        buttonIcon.className = "custom-date-icon";
        buttonIcon.setAttribute("aria-hidden", "true");
        button.append(buttonText, buttonIcon);
        wrapper.appendChild(button);

        const panel = document.createElement("div");
        panel.className = "custom-date-panel custom-floating-panel";
        panel.hidden = true;
        panel.setAttribute("role", "dialog");
        panel.setAttribute("aria-label", "Календарь");
        document.body.appendChild(panel);

        const today = new Date();
        let visibleYear = today.getFullYear();
        let visibleMonth = today.getMonth();

        function selectedDate() {
            return parseIsoDate(datePart(input.value));
        }

        function selectedIso() {
            const date = selectedDate();
            return date ? formatIsoDate(date.getFullYear(), date.getMonth(), date.getDate()) : "";
        }

        function minIso() {
            return datePart(input.getAttribute("min"));
        }

        function maxIso() {
            return datePart(input.getAttribute("max"));
        }

        function isOutsideLimits(isoValue) {
            return (minIso() && compareIsoDates(isoValue, minIso()) < 0)
                || (maxIso() && compareIsoDates(isoValue, maxIso()) > 0);
        }

        function setVisibleFromValue() {
            const date = selectedDate() || parseIsoDate(datePart(input.getAttribute("value"))) || today;
            visibleYear = date.getFullYear();
            visibleMonth = date.getMonth();
        }

        function setInputDate(isoValue) {
            if (input.type === "datetime-local" && isoValue) {
                input.value = isoValue + "T" + timePart(input.value);
            } else {
                input.value = isoValue;
            }
            syncButton();
            dispatchNativeChange(input);
            close();
            button.focus();
        }

        function syncButton() {
            buttonText.textContent = formatDateButtonText(input);
            button.disabled = input.disabled || input.readOnly;
            wrapper.classList.toggle("custom-control-disabled", input.disabled || input.readOnly);
        }

        function renderPanel() {
            const currentSelected = selectedIso();
            const todayIso = formatIsoDate(today.getFullYear(), today.getMonth(), today.getDate());
            const firstDay = new Date(visibleYear, visibleMonth, 1);
            const firstGridOffset = (firstDay.getDay() + 6) % 7;
            const gridStart = new Date(visibleYear, visibleMonth, 1 - firstGridOffset);

            panel.textContent = "";

            const header = document.createElement("div");
            header.className = "custom-date-header";

            const title = document.createElement("div");
            title.className = "custom-date-title";
            title.textContent = MONTH_NAMES[visibleMonth] + " " + visibleYear;

            const nav = document.createElement("div");
            nav.className = "custom-date-nav";

            const previousButton = document.createElement("button");
            previousButton.type = "button";
            previousButton.className = "custom-date-nav-button";
            previousButton.setAttribute("aria-label", "Предыдущий месяц");
            previousButton.textContent = "‹";

            const nextButton = document.createElement("button");
            nextButton.type = "button";
            nextButton.className = "custom-date-nav-button";
            nextButton.setAttribute("aria-label", "Следующий месяц");
            nextButton.textContent = "›";

            nav.append(previousButton, nextButton);
            header.append(title, nav);
            panel.appendChild(header);

            const calendar = document.createElement("div");
            calendar.className = "custom-date-calendar";
            WEEKDAY_NAMES.forEach(function (weekday) {
                const label = document.createElement("span");
                label.className = "custom-date-weekday";
                label.textContent = weekday;
                calendar.appendChild(label);
            });

            for (let index = 0; index < 42; index += 1) {
                const date = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + index);
                const isoValue = formatIsoDate(date.getFullYear(), date.getMonth(), date.getDate());
                const dayButton = document.createElement("button");
                dayButton.type = "button";
                dayButton.className = "custom-date-day";
                dayButton.textContent = String(date.getDate());
                dayButton.dataset.dateValue = isoValue;
                dayButton.classList.toggle("custom-date-day-outside", date.getMonth() !== visibleMonth);
                dayButton.classList.toggle("custom-date-day-today", isoValue === todayIso);
                dayButton.classList.toggle("custom-date-day-selected", isoValue === currentSelected);
                if (isOutsideLimits(isoValue)) {
                    dayButton.disabled = true;
                    dayButton.classList.add("custom-date-day-disabled");
                }
                dayButton.addEventListener("click", function () {
                    setInputDate(isoValue);
                });
                calendar.appendChild(dayButton);
            }
            panel.appendChild(calendar);

            const footer = document.createElement("div");
            footer.className = "custom-date-footer";

            const clearButton = document.createElement("button");
            clearButton.type = "button";
            clearButton.className = "custom-date-footer-button";
            clearButton.textContent = "Очистить";
            clearButton.disabled = input.required;
            clearButton.hidden = input.required;
            clearButton.addEventListener("click", function () {
                setInputDate("");
            });

            const todayButton = document.createElement("button");
            todayButton.type = "button";
            todayButton.className = "custom-date-footer-button custom-date-footer-primary";
            todayButton.textContent = "Сегодня";
            todayButton.disabled = isOutsideLimits(todayIso);
            todayButton.addEventListener("click", function () {
                setInputDate(todayIso);
            });

            footer.append(clearButton, todayButton);
            panel.appendChild(footer);

            previousButton.addEventListener("click", function () {
                visibleMonth -= 1;
                if (visibleMonth < 0) {
                    visibleMonth = 11;
                    visibleYear -= 1;
                }
                renderPanel();
                placeFloatingPanel(panel, wrapper);
            });

            nextButton.addEventListener("click", function () {
                visibleMonth += 1;
                if (visibleMonth > 11) {
                    visibleMonth = 0;
                    visibleYear += 1;
                }
                renderPanel();
                placeFloatingPanel(panel, wrapper);
            });
        }

        function reposition() {
            if (!panel.hidden) {
                placeFloatingPanel(panel, wrapper);
            }
        }

        function open() {
            if (input.disabled || input.readOnly) return;
            if (activeControl && activeControl.close !== close) {
                closeActiveControl();
            }
            setVisibleFromValue();
            renderPanel();
            panel.hidden = false;
            wrapper.classList.add("custom-control-open");
            activeControl = { close: close };
            window.requestAnimationFrame(reposition);
        }

        function close() {
            panel.hidden = true;
            wrapper.classList.remove("custom-control-open");
            if (activeControl && activeControl.close === close) {
                activeControl = null;
            }
        }

        button.addEventListener("click", open);
        input.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                close();
            }
        });
        input.addEventListener("change", function () {
            syncButton();
            if (!panel.hidden) {
                setVisibleFromValue();
                renderPanel();
                reposition();
            }
        });
        input.addEventListener("invalid", function () {
            wrapper.classList.add("custom-control-invalid");
            button.focus();
        });
        input.addEventListener("input", function () {
            syncButton();
            wrapper.classList.remove("custom-control-invalid");
        });
        input.form && input.form.addEventListener("reset", function () {
            window.setTimeout(function () {
                setVisibleFromValue();
                renderPanel();
                syncButton();
            }, 0);
        });
        window.addEventListener("resize", reposition);
        window.addEventListener("scroll", reposition, true);
        syncButton();
    }

    function enhanceMonthInput(input) {
        if (input.dataset.customControlReady === "month") return;
        input.dataset.customControlReady = "month";

        const wrapper = document.createElement("div");
        wrapper.className = "custom-date custom-month";
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);
        input.classList.add("custom-date-input", "custom-month-input", "custom-native-control");
        input.tabIndex = -1;

        const button = document.createElement("button");
        button.type = "button";
        button.className = "custom-date-button";
        button.setAttribute("aria-label", "Открыть выбор месяца");
        const buttonText = document.createElement("span");
        buttonText.className = "custom-date-value";
        const buttonIcon = document.createElement("span");
        buttonIcon.className = "custom-date-icon";
        buttonIcon.setAttribute("aria-hidden", "true");
        button.append(buttonText, buttonIcon);
        wrapper.appendChild(button);

        const panel = document.createElement("div");
        panel.className = "custom-date-panel custom-month-panel custom-floating-panel";
        panel.hidden = true;
        panel.setAttribute("role", "dialog");
        panel.setAttribute("aria-label", "Выбор месяца");
        document.body.appendChild(panel);

        const today = new Date();
        let visibleYear = today.getFullYear();

        function selectedMonth() {
            return parseIsoMonth(input.value);
        }

        function selectedIso() {
            const selected = selectedMonth();
            return selected ? selected.year + "-" + padNumber(selected.monthIndex + 1) : "";
        }

        function minIso() {
            return input.getAttribute("min") || "";
        }

        function maxIso() {
            return input.getAttribute("max") || "";
        }

        function isOutsideLimits(isoValue) {
            return (minIso() && compareIsoDates(isoValue, minIso()) < 0)
                || (maxIso() && compareIsoDates(isoValue, maxIso()) > 0);
        }

        function setVisibleFromValue() {
            const selected = selectedMonth()
                || parseIsoMonth(input.getAttribute("value"))
                || { year: today.getFullYear(), monthIndex: today.getMonth() };
            visibleYear = selected.year;
        }

        function setInputMonth(isoValue) {
            input.value = isoValue;
            syncButton();
            dispatchNativeChange(input);
            close();
            button.focus();
        }

        function syncButton() {
            buttonText.textContent = formatMonthButtonText(input);
            button.disabled = input.disabled || input.readOnly;
            wrapper.classList.toggle("custom-control-disabled", input.disabled || input.readOnly);
        }

        function renderPanel() {
            const currentSelected = selectedIso();
            const todayIso = today.getFullYear() + "-" + padNumber(today.getMonth() + 1);

            panel.textContent = "";

            const header = document.createElement("div");
            header.className = "custom-date-header";

            const title = document.createElement("div");
            title.className = "custom-date-title";
            title.textContent = String(visibleYear);

            const nav = document.createElement("div");
            nav.className = "custom-date-nav";

            const previousButton = document.createElement("button");
            previousButton.type = "button";
            previousButton.className = "custom-date-nav-button";
            previousButton.setAttribute("aria-label", "Предыдущий год");
            previousButton.textContent = "‹";

            const nextButton = document.createElement("button");
            nextButton.type = "button";
            nextButton.className = "custom-date-nav-button";
            nextButton.setAttribute("aria-label", "Следующий год");
            nextButton.textContent = "›";

            nav.append(previousButton, nextButton);
            header.append(title, nav);
            panel.appendChild(header);

            const monthGrid = document.createElement("div");
            monthGrid.className = "custom-month-grid";
            MONTH_NAMES.forEach(function (monthName, monthIndex) {
                const isoValue = visibleYear + "-" + padNumber(monthIndex + 1);
                const monthButton = document.createElement("button");
                monthButton.type = "button";
                monthButton.className = "custom-month-option";
                monthButton.textContent = monthName;
                monthButton.classList.toggle("custom-month-option-selected", isoValue === currentSelected);
                monthButton.classList.toggle("custom-month-option-current", isoValue === todayIso);
                if (isOutsideLimits(isoValue)) {
                    monthButton.disabled = true;
                }
                monthButton.addEventListener("click", function () {
                    setInputMonth(isoValue);
                });
                monthGrid.appendChild(monthButton);
            });
            panel.appendChild(monthGrid);

            const footer = document.createElement("div");
            footer.className = "custom-date-footer";

            const clearButton = document.createElement("button");
            clearButton.type = "button";
            clearButton.className = "custom-date-footer-button";
            clearButton.textContent = "Очистить";
            clearButton.disabled = input.required;
            clearButton.hidden = input.required;
            clearButton.addEventListener("click", function () {
                setInputMonth("");
            });

            const todayButton = document.createElement("button");
            todayButton.type = "button";
            todayButton.className = "custom-date-footer-button custom-date-footer-primary";
            todayButton.textContent = "Текущий месяц";
            todayButton.disabled = isOutsideLimits(todayIso);
            todayButton.addEventListener("click", function () {
                setInputMonth(todayIso);
            });

            footer.append(clearButton, todayButton);
            panel.appendChild(footer);

            previousButton.addEventListener("click", function () {
                visibleYear -= 1;
                renderPanel();
                placeFloatingPanel(panel, wrapper);
            });

            nextButton.addEventListener("click", function () {
                visibleYear += 1;
                renderPanel();
                placeFloatingPanel(panel, wrapper);
            });
        }

        function reposition() {
            if (!panel.hidden) {
                placeFloatingPanel(panel, wrapper);
            }
        }

        function open() {
            if (input.disabled || input.readOnly) return;
            if (activeControl && activeControl.close !== close) {
                closeActiveControl();
            }
            setVisibleFromValue();
            renderPanel();
            panel.hidden = false;
            wrapper.classList.add("custom-control-open");
            activeControl = { close: close };
            window.requestAnimationFrame(reposition);
        }

        function close() {
            panel.hidden = true;
            wrapper.classList.remove("custom-control-open");
            if (activeControl && activeControl.close === close) {
                activeControl = null;
            }
        }

        button.addEventListener("click", open);
        input.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                close();
            }
        });
        input.addEventListener("change", function () {
            syncButton();
            if (!panel.hidden) {
                setVisibleFromValue();
                renderPanel();
                reposition();
            }
        });
        input.addEventListener("invalid", function () {
            wrapper.classList.add("custom-control-invalid");
            button.focus();
        });
        input.addEventListener("input", function () {
            syncButton();
            wrapper.classList.remove("custom-control-invalid");
        });
        input.form && input.form.addEventListener("reset", function () {
            window.setTimeout(function () {
                setVisibleFromValue();
                renderPanel();
                syncButton();
            }, 0);
        });
        window.addEventListener("resize", reposition);
        window.addEventListener("scroll", reposition, true);
        syncButton();
    }

    function initFormControls(root) {
        const scope = root || document;
        scope.querySelectorAll(SELECTOR_SELECT).forEach(enhanceSelect);
        scope.querySelectorAll(SELECTOR_DATE).forEach(enhanceDateInput);
        scope.querySelectorAll(SELECTOR_MONTH).forEach(enhanceMonthInput);
    }

    document.addEventListener("click", function (event) {
        if (!activeControl) return;
        const target = event.target;
        if (isClickInside(event, [
            target.closest && target.closest(".custom-select"),
            target.closest && target.closest(".custom-date"),
            target.closest && target.closest(".custom-floating-panel"),
        ])) {
            return;
        }
        closeActiveControl();
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeActiveControl();
        }
    });

    document.addEventListener("DOMContentLoaded", function () {
        initFormControls(document);

        if ("MutationObserver" in window) {
            const observer = new MutationObserver(function (mutations) {
                mutations.forEach(function (mutation) {
                    mutation.addedNodes.forEach(function (node) {
                        if (node instanceof HTMLElement) {
                            initFormControls(node);
                        }
                    });
                });
            });
            observer.observe(document.body, { childList: true, subtree: true });
        }
    });
}());
