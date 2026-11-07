/**
 * Cémantix Solver — Module Interactions Indices IA & Commutateurs (M13)
 * Gère le double switch (Source: IA vs RAG / Format: Phrase vs Mot)
 * et le démasquage anti-spoiler.
 */
document.addEventListener("DOMContentLoaded", function() {
    var tabAi = document.getElementById("tab-hints-ai");
    var tabRag = document.getElementById("tab-hints-rag");
    var panelAi = document.getElementById("panel-hints-ai");
    var panelRag = document.getElementById("panel-hints-rag");
    var formatToolbar = document.getElementById("hints-ai-format");
    var btnPhrase = document.getElementById("btn-format-phrase");
    var btnWord = document.getElementById("btn-format-word");

    if (tabAi && tabRag && panelAi && panelRag) {
        tabAi.addEventListener("click", function() {
            tabAi.classList.add("active");
            tabAi.setAttribute("aria-selected", "true");
            tabRag.classList.remove("active");
            tabRag.setAttribute("aria-selected", "false");
            panelAi.classList.add("active");
            panelAi.removeAttribute("hidden");
            panelRag.classList.remove("active");
            panelRag.setAttribute("hidden", "");
            if (formatToolbar) formatToolbar.style.display = "";
        });

        tabRag.addEventListener("click", function() {
            tabRag.classList.add("active");
            tabRag.setAttribute("aria-selected", "true");
            tabAi.classList.remove("active");
            tabAi.setAttribute("aria-selected", "false");
            panelRag.classList.add("active");
            panelRag.removeAttribute("hidden");
            panelAi.classList.remove("active");
            panelAi.setAttribute("hidden", "");
            if (formatToolbar) formatToolbar.style.display = "none";
        });
    }

    if (btnPhrase && btnWord) {
        btnPhrase.addEventListener("click", function() {
            btnPhrase.classList.add("active");
            btnPhrase.setAttribute("aria-checked", "true");
            btnWord.classList.remove("active");
            btnWord.setAttribute("aria-checked", "false");
            var phrases = document.querySelectorAll(".hint-view-phrase");
            var words = document.querySelectorAll(".hint-view-word");
            phrases.forEach(function(el) { el.classList.add("active"); });
            words.forEach(function(el) { el.classList.remove("active"); });
        });

        btnWord.addEventListener("click", function() {
            btnWord.classList.add("active");
            btnWord.setAttribute("aria-checked", "true");
            btnPhrase.classList.remove("active");
            btnPhrase.setAttribute("aria-checked", "false");
            var phrases = document.querySelectorAll(".hint-view-phrase");
            var words = document.querySelectorAll(".hint-view-word");
            words.forEach(function(el) { el.classList.add("active"); });
            phrases.forEach(function(el) { el.classList.remove("active"); });
        });
    }

    var spoilerBoxes = document.querySelectorAll(".spoiler-box");
    spoilerBoxes.forEach(function(box) {
        function reveal(e) {
            if (box.classList.contains("revealed")) return;
            box.classList.add("revealed");
            var btn = box.querySelector(".btn-reveal");
            if (btn) btn.style.display = "none";
            var texts = box.querySelectorAll(".spoiler-text");
            texts.forEach(function(t) { t.removeAttribute("data-spoiler"); });
        }
        box.addEventListener("click", reveal);
        var btn = box.querySelector(".btn-reveal");
        if (btn) {
            btn.addEventListener("click", function(e) {
                e.stopPropagation();
                reveal(e);
            });
        }
    });

    document.addEventListener("click", function(e) {
        var sp = e.target.closest(".word-spoiler");
        if (sp) {
            sp.classList.toggle("is-hidden");
        }
    });
});
