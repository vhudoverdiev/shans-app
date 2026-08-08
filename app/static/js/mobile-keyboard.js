(function () {
    const root = document.documentElement;
    const keyboardOffsetProperty = "--mobile-keyboard-offset";
    const keyboardOpenClass = "mobile-keyboard-open";
    const keyboardThreshold = 80;
    const coarsePointerQuery = window.matchMedia
        ? window.matchMedia("(pointer: coarse)")
        : null;
    let layoutViewportHeight = Math.max(
        window.innerHeight || 0,
        document.documentElement.clientHeight || 0
    );

    function isTextEditingControl(element) {
        if (!(element instanceof HTMLElement)) return false;
        if (element.matches("textarea, select, [contenteditable='true']")) return true;
        if (!element.matches("input")) return false;

        const ignoredTypes = new Set([
            "button",
            "checkbox",
            "color",
            "file",
            "hidden",
            "image",
            "radio",
            "range",
            "reset",
            "submit",
        ]);
        return !ignoredTypes.has((element.getAttribute("type") || "text").toLowerCase());
    }

    function getKeyboardOffset() {
        if (!window.visualViewport) return 0;
        const stableLayoutHeight = Math.max(
            window.innerHeight || 0,
            document.documentElement.clientHeight || 0,
            layoutViewportHeight
        );
        return Math.max(0, Math.round(stableLayoutHeight - window.visualViewport.height));
    }

    function syncKeyboardState() {
        const activeElement = document.activeElement;
        const isEditingText = isTextEditingControl(activeElement);
        if (!isEditingText) {
            layoutViewportHeight = Math.max(
                window.innerHeight || 0,
                document.documentElement.clientHeight || 0
            );
        }

        const isTouchScreen = !coarsePointerQuery || coarsePointerQuery.matches;
        const offset = getKeyboardOffset();
        const isKeyboardOpen = isTouchScreen
            && isEditingText
            && offset > keyboardThreshold;

        root.classList.toggle(keyboardOpenClass, isKeyboardOpen);
        root.style.setProperty(
            keyboardOffsetProperty,
            isKeyboardOpen ? offset + "px" : "0px"
        );
    }

    document.addEventListener("focusin", syncKeyboardState);
    document.addEventListener("focusout", function () {
        window.setTimeout(syncKeyboardState, 80);
    });
    window.addEventListener("resize", syncKeyboardState, { passive: true });
    window.addEventListener("orientationchange", syncKeyboardState, { passive: true });

    if (window.visualViewport) {
        window.visualViewport.addEventListener("resize", syncKeyboardState, { passive: true });
        window.visualViewport.addEventListener("scroll", syncKeyboardState, { passive: true });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", syncKeyboardState, { once: true });
    } else {
        syncKeyboardState();
    }
}());
