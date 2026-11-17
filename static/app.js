"use strict";

/* =========================
   ZOLAK AI — APP
========================= */

const promptBox = document.getElementById("prompt");
const sendButton = document.getElementById("send");
const homeQuickActions = document.getElementById("homeQuickActions");
const messages = document.getElementById("messages");
const sidebar = document.querySelector(".sidebar");
const mobileMenu = document.querySelector(".mobile-menu");
const appShell = document.querySelector(".app.chatgpt-layout");
const desktopSidebarToggle = document.getElementById("sidebarCollapseButton");

function setDesktopSidebarCollapsed(collapsed) {
    if (!appShell || window.innerWidth <= 800) return;
    appShell.classList.toggle("sidebar-collapsed", Boolean(collapsed));
    const conversationSearch = document.getElementById("conversationSearch");
const pinnedItems = document.getElementById("pinnedItems");
const sidebarPinnedSection = document.querySelector(".sidebar-pinned");
const projectsPanel = document.getElementById("projectsPanel");
const explorePanel = document.getElementById("explorePanel");
const projectItems = document.getElementById("projectItems");
const createProjectButton = document.getElementById("createProjectButton");
const allConversationsButton = document.getElementById("allConversationsButton");
const projectPickerModal = document.getElementById("projectPickerModal");
const projectPickerSelect = document.getElementById("projectPickerSelect");
let currentProjectId = null;
let projectPickerConversationId = null;
let conversationSearchTimer = null;
let conversationSearchSequence = 0;

if (conversationSearch) {
    conversationSearch.addEventListener("input", function () {
        window.clearTimeout(conversationSearchTimer);
        conversationSearchTimer = window.setTimeout(function () {
            loadConversations(conversationSearch.value.trim());
        }, 280);
    });
}

async function createProjectFromSidebar() {
    const name = window.prompt("اكتب اسم المشروع الجديد:");
    if (name === null || !name.trim()) return;
    try {
        const response = await fetch("/api/projects", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name.trim() })
        });
        const result = await response.json();
        if (!response.ok) {
            showSidebarNotice(result.error || "ما قدرنا ننشئ المشروع.");
            return;
        }
        currentProjectId = result.project_id;
        await loadProjects();
        await loadConversations();
    } catch (error) {
        console.error("خطأ في إنشاء المشروع:", error);
        showSidebarNotice("حصل خطأ أثناء إنشاء المشروع.");
    }
}
if (projectPickerModal) {
    const cancelPicker = document.getElementById("projectPickerCancel");
    const savePicker = document.getElementById("projectPickerSave");
    if (cancelPicker) cancelPicker.addEventListener("click", function () {
        projectPickerModal.hidden = true;
        projectPickerConversationId = null;
    });
    if (savePicker) savePicker.addEventListener("click", async function () {
        if (!projectPickerConversationId) return;
        const value = projectPickerSelect ? projectPickerSelect.value : "";
        try {
            const response = await fetch("/api/conversations/" + projectPickerConversationId, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ project_id: value ? Number(value) : null })
            });
            const result = await response.json();
            if (!response.ok) {
                showSidebarNotice(result.error || "ما قدرنا ننقل المحادثة.");
                return;
            }
            projectPickerModal.hidden = true;
            projectPickerConversationId = null;
            await loadConversations();
            await loadProjects();
        } catch (error) {
            console.error("خطأ في نقل المحادثة:", error);
            showSidebarNotice("حصل خطأ أثناء نقل المحادثة.");
        }
    });
}


let currentConversationId = null;
let isSending = false;

/* =========================
   SIDEBAR
========================= */

let sidebarOverlay = document.querySelector(".sidebar-overlay");

if (!sidebarOverlay) {
    sidebarOverlay = document.createElement("div");
    sidebarOverlay.className = "sidebar-overlay";
    document.body.appendChild(sidebarOverlay);
}

function openSidebar() {
    if (!sidebar || window.innerWidth > 800) return;

    sidebar.classList.add("open");
    sidebarOverlay.classList.add("active");

    document.body.style.overflow = "hidden";

    if (mobileMenu) {
        mobileMenu.setAttribute("aria-expanded", "true");
        mobileMenu.setAttribute("aria-label", "إغلاق القائمة");
    }
}

function closeSidebar() {
    if (sidebar) {
        sidebar.classList.remove("open");
    }

    if (sidebarOverlay) {
        sidebarOverlay.classList.remove("active");
    }

    document.body.style.overflow = "";

    if (mobileMenu) {
        mobileMenu.setAttribute("aria-expanded", "false");
        mobileMenu.setAttribute("aria-label", "فتح القائمة");
    }
}

function toggleSidebar() {
    if (!sidebar) return;

    if (sidebar.classList.contains("open")) {
        closeSidebar();
    } else {
        openSidebar();
    }
}

if (sidebarOverlay) {
    sidebarOverlay.addEventListener("click", closeSidebar);
}

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
        closeSidebar();
    }
});

window.addEventListener("resize", function () {
    if (window.innerWidth > 800) {
        closeSidebar();
    }
});

/* إغلاق القائمة عند اختيار رابط داخلها */
if (sidebar) {
    sidebar.addEventListener("click", function (event) {
        const link = event.target.closest("a");

        if (link && window.innerWidth <= 800) {
            closeSidebar();
        }
    });
}


/* HOME HEADER + COMPOSER CONTROLS */
function showSidebarNotice(message) {
    let notice = document.querySelector(".sidebar-feature-notice");
    if (!notice) { notice = document.createElement("div"); notice.className = "sidebar-feature-notice"; document.body.appendChild(notice); }
    notice.textContent = message; notice.hidden = false;
    window.clearTimeout(notice._hideTimer);
    notice._hideTimer = window.setTimeout(function () { notice.hidden = true; }, 2400);
}
const composerAdd = document.getElementById("composerAdd");
const attachmentInput = document.getElementById("attachmentInput");
const attachmentPreview = document.getElementById("attachmentPreview");
let selectedAttachments = [];

function attachmentMime(file) {
    if (file.type) return file.type;
    const extension = (file.name.split(".").pop() || "").toLowerCase();
    const byExtension = {
        jpg:"image/jpeg", jpeg:"image/jpeg", png:"image/png", webp:"image/webp",
        gif:"image/gif", pdf:"application/pdf", docx:"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        txt:"text/plain", md:"text/markdown", csv:"text/csv"
    };
    return byExtension[extension] || "";
}

function formatAttachmentSize(bytes) {
    return bytes < 1024 * 1024
        ? Math.max(1, Math.round(bytes / 1024)) + " KB"
        : (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function renderAttachmentPreview() {
    if (!attachmentPreview) return;
    attachmentPreview.replaceChildren();
    attachmentPreview.hidden = selectedAttachments.length === 0;
    if (composerAdd) composerAdd.classList.toggle("has-files", selectedAttachments.length > 0);

    selectedAttachments.forEach(function (file, index) {
        const chip = document.createElement("div");
        chip.className = "attachment-chip";
        if (attachmentMime(file).startsWith("image/")) {
            const image = document.createElement("img");
            image.src = URL.createObjectURL(file);
            image.alt = file.name;
            chip.appendChild(image);
        } else {
            const icon = document.createElement("span");
            icon.textContent = file.type === "application/pdf" ? "PDF" : "ملف";
            chip.appendChild(icon);
        }
        const name = document.createElement("span");
        name.className = "attachment-chip-name";
        name.textContent = file.name + " · " + formatAttachmentSize(file.size);
        chip.appendChild(name);
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "attachment-remove";
        remove.setAttribute("aria-label", "إزالة " + file.name);
        remove.textContent = "×";
        remove.addEventListener("click", function () {
            selectedAttachments.splice(index, 1);
            renderAttachmentPreview();
        });
        chip.appendChild(remove);
        attachmentPreview.appendChild(chip);
    });
}

if (composerAdd && attachmentInput) {
    composerAdd.addEventListener("click", function () {
        attachmentInput.click();
    });
    attachmentInput.addEventListener("change", function () {
        const accepted = new Set([
            "image/jpeg", "image/png", "image/webp", "image/gif",
            "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown", "text/csv"
        ]);
        const incoming = Array.from(attachmentInput.files || []);
        for (const file of incoming) {
            const mimeType = attachmentMime(file);
            if (!accepted.has(mimeType)) {
                showSidebarNotice("نوع الملف غير مدعوم. أرفق صورة أو PDF أو TXT أو MD أو CSV.");
                continue;
            }
            if (selectedAttachments.length >= 4) {
                showSidebarNotice("الحد الأقصى 4 ملفات في الرسالة الواحدة.");
                break;
            }
            if (file.size > 2500000) {
                showSidebarNotice("حجم الملف الواحد أكبر من 2.5 ميجابايت.");
                continue;
            }
            const total = selectedAttachments.reduce(function (sum, item) { return sum + item.size; }, 0);
            if (total + file.size > 2500000) {
                showSidebarNotice("إجمالي حجم المرفقات لا يتجاوز 2.5 ميجابايت.");
                continue;
            }
            if (selectedAttachments.some(function (item) { return item.name === file.name && item.size === file.size; })) continue;
            selectedAttachments.push(file);
        }
        attachmentInput.value = "";
        renderAttachmentPreview();
    });
}

function fileToPayload(file) {
    return new Promise(function (resolve, reject) {
        const reader = new FileReader();
        reader.onload = function () {
            const result = String(reader.result || "");
            const comma = result.indexOf(",");
            if (comma < 0) return reject(new Error("تعذر قراءة الملف " + file.name));
            resolve({
                name: file.name,
                mime_type: attachmentMime(file),
                data: result.slice(comma + 1)
            });
        };
        reader.onerror = function () { reject(new Error("تعذر قراءة الملف " + file.name)); };
        reader.readAsDataURL(file);
    });
}

function clearSelectedAttachments() {
    selectedAttachments = [];
    renderAttachmentPreview();
}
const composerMic = document.getElementById("composerMic");
if (composerMic) composerMic.addEventListener("click", function () {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) { showSidebarNotice("الإملاء الصوتي غير مدعوم في المتصفح الحالي."); return; }
    const recognition = new Recognition(); recognition.lang = "ar"; recognition.interimResults = false;
    composerMic.classList.add("is-listening");
    recognition.onresult = function (event) { promptBox.value = (promptBox.value ? promptBox.value + " " : "") + event.results[0][0].transcript; promptBox.focus(); };
    recognition.onerror = function () { showSidebarNotice("ما قدرنا نلتقط الصوت. حاول تاني."); };
    recognition.onend = function () { composerMic.classList.remove("is-listening"); };
    try { recognition.start(); } catch (error) { composerMic.classList.remove("is-listening"); }
});

/* =========================
   MESSAGES
========================= */

function appendInlineMarkdown(container, source) {
    const pattern = /(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|__([^_]+)__|\*([^*\n]+)\*|_([^_\n]+)_)/g;
    let cursor = 0;
    let match;

    while ((match = pattern.exec(source)) !== null) {
        if (match.index > cursor) {
            container.appendChild(document.createTextNode(source.slice(cursor, match.index)));
        }

        let node;
        if (match[3]) {
            node = document.createElement("a");
            node.textContent = match[2];
            node.href = match[3];
            node.target = "_blank";
            node.rel = "noopener noreferrer";
        } else if (match[4]) {
            node = document.createElement("code");
            node.textContent = match[4];
        } else if (match[5] || match[6]) {
            node = document.createElement("strong");
            node.textContent = match[5] || match[6];
        } else {
            node = document.createElement("em");
            node.textContent = match[7] || match[8];
        }

        container.appendChild(node);
        cursor = pattern.lastIndex;
    }

    if (cursor < source.length) {
        container.appendChild(document.createTextNode(source.slice(cursor)));
    }
}

function highlightCodeElement(element, source, language) {
    const lang = String(language || "").toLowerCase();
    const keywordSets = {
        javascript: "const let var function return if else for while class new this async await try catch throw import export from default true false null undefined",
        js: "const let var function return if else for while class new this async await try catch throw import export from default true false null undefined",
        typescript: "const let var function return if else for while class new this async await try catch throw import export from default interface type enum public private readonly",
        ts: "const let var function return if else for while class new this async await try catch throw import export from default interface type enum public private readonly",
        python: "def class return if elif else for while in not and or is import from as try except finally with lambda yield async await True False None self",
        py: "def class return if elif else for while in not and or is import from as try except finally with lambda yield async await True False None self",
        json: "true false null",
        sql: "select from where insert into values update set delete create table alter drop join left right inner on as and or not null primary key foreign references order by group limit desc asc",
        css: "important inherit initial unset",
        html: "DOCTYPE html head body div span section main header footer script style link meta button input form"
    };
    const keywords = new Set((keywordSets[lang] || keywordSets.javascript).split(/\s+/));
    const pattern = /(\/\/[^\n]*|#[^\n]*|\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|\b\d+(?:\.\d+)?\b|\b[A-Za-z_$][\w$]*\b(?=\s*\()|\b[A-Za-z_$][\w$]*\b|[{}()[\];,.]/g;
    let cursor = 0;
    let match;
    const fragment = document.createDocumentFragment();
    while ((match = pattern.exec(source)) !== null) {
        if (match.index > cursor) fragment.appendChild(document.createTextNode(source.slice(cursor, match.index)));
        const token = match[0];
        let kind = "";
        if (/^(\/\/|#|\/\*)/.test(token)) kind = "comment";
        else if (/^["'`]/.test(token)) kind = "string";
        else if (/^\d/.test(token)) kind = "number";
        else if (keywords.has(token)) kind = "keyword";
        else if (/^[A-Za-z_$][\w$]*$/.test(token) && /^\s*\(/.test(source.slice(match.index + token.length))) kind = "function";
        else if (/^[{}()[\];,.]$/.test(token)) kind = "punctuation";
        if (kind) {
            const span = document.createElement("span");
            span.className = "token-" + kind;
            span.textContent = token;
            fragment.appendChild(span);
        } else {
            fragment.appendChild(document.createTextNode(token));
        }
        cursor = pattern.lastIndex;
    }
    if (cursor < source.length) fragment.appendChild(document.createTextNode(source.slice(cursor)));
    element.replaceChildren(fragment);
}

function renderAssistantMarkdown(container, source) {
    const lines = String(source || "").replace(/\r\n/g, "\n").split("\n");
    let paragraph = [];
    let list = null;
    let codeLines = null;
    let codeLanguage = "";

    function flushParagraph() {
        if (!paragraph.length) return;
        const p = document.createElement("p");
        paragraph.forEach(function (line, index) {
            if (index) p.appendChild(document.createElement("br"));
            appendInlineMarkdown(p, line);
        });
        container.appendChild(p);
        paragraph = [];
    }

    function flushList() {
        if (!list) return;
        container.appendChild(list);
        list = null;
    }

    function appendCodeBlock(code, language) {
        const wrapper = document.createElement("div");
        wrapper.className = "code-block";
        const toolbar = document.createElement("div");
        toolbar.className = "code-toolbar";
        const label = document.createElement("span");
        label.textContent = language || "كود";
        const copy = document.createElement("button");
        copy.type = "button";
        copy.className = "code-copy";
        copy.textContent = "نسخ الكود";
        copy.addEventListener("click", async function () {
            const originalLabel = copy.textContent;
            try {
                if (navigator.clipboard && window.isSecureContext) {
                    await navigator.clipboard.writeText(code);
                } else {
                    throw new Error("Clipboard API unavailable");
                }
                copy.textContent = "تم النسخ ✓";
            } catch (error) {
                const fallback = document.createElement("textarea");
                fallback.value = code;
                fallback.setAttribute("readonly", "");
                fallback.style.position = "fixed";
                fallback.style.opacity = "0";
                fallback.style.pointerEvents = "none";
                document.body.appendChild(fallback);
                fallback.select();
                fallback.setSelectionRange(0, fallback.value.length);
                let copied = false;
                try { copied = document.execCommand("copy"); } catch (_) {}
                fallback.remove();
                copy.textContent = copied ? "تم النسخ ✓" : "تعذر النسخ";
            }
            window.setTimeout(function () {
                if (copy.isConnected) copy.textContent = originalLabel;
            }, 1800);
        });
        toolbar.appendChild(label);
        toolbar.appendChild(copy);
        const pre = document.createElement("pre");
        const codeElement = document.createElement("code");
        codeElement.dataset.language = language || "text";
        highlightCodeElement(codeElement, code, language);
        pre.appendChild(codeElement);
        wrapper.appendChild(toolbar);
        wrapper.appendChild(pre);
        container.appendChild(wrapper);
    }

    lines.forEach(function (line) {
        if (codeLines !== null) {
            if (/^\s*```/.test(line)) {
                appendCodeBlock(codeLines.join("\n"), codeLanguage);
                codeLines = null;
                codeLanguage = "";
            } else {
                codeLines.push(line);
            }
            return;
        }

        const fence = line.match(/^\s*```\s*([\w+#.-]*)/);
        if (fence) {
            flushParagraph();
            flushList();
            codeLines = [];
            codeLanguage = fence[1] || "";
            return;
        }

        if (!line.trim()) {
            flushParagraph();
            flushList();
            return;
        }

        const heading = line.match(/^(#{1,3})\s+(.+)$/);
        if (heading) {
            flushParagraph();
            flushList();
            const h = document.createElement(heading[1].length === 1 ? "h2" : "h3");
            appendInlineMarkdown(h, heading[2]);
            container.appendChild(h);
            return;
        }

        const bullet = line.match(/^\s*[-*]\s+(.+)$/);
        const numbered = line.match(/^\s*\d+[.)]\s+(.+)$/);
        if (bullet || numbered) {
            flushParagraph();
            const wantedTag = bullet ? "ul" : "ol";
            if (!list || list.tagName.toLowerCase() !== wantedTag) {
                flushList();
                list = document.createElement(wantedTag);
            }
            const li = document.createElement("li");
            appendInlineMarkdown(li, (bullet || numbered)[1]);
            list.appendChild(li);
            return;
        }

        const quote = line.match(/^\s*&gt;\s*(.*)$/) || line.match(/^\s*>\s*(.*)$/);
        if (quote) {
            flushParagraph();
            flushList();
            const blockquote = document.createElement("blockquote");
            appendInlineMarkdown(blockquote, quote[1]);
            container.appendChild(blockquote);
            return;
        }

        flushList();
        paragraph.push(line);
    });

    if (codeLines !== null) appendCodeBlock(codeLines.join("\n"), codeLanguage);
    flushParagraph();
    flushList();
}

function addMessage(text, type, attachments) {
    if (!messages) return;

    const message = document.createElement("div");
    message.className = "message " + type;

    const content = document.createElement("div");
    content.className = "message-content";
    if (type === "assistant") {
        renderAssistantMarkdown(content, text);
        const actions = document.createElement("div");
        actions.className = "message-actions";
        const copyButton = document.createElement("button");
        copyButton.type = "button";
        copyButton.className = "message-copy";
        copyButton.textContent = "نسخ الرد";
        copyButton.addEventListener("click", async function () {
            try {
                await navigator.clipboard.writeText(String(text || ""));
                copyButton.textContent = "تم النسخ ✓";
            } catch (error) {
                copyButton.textContent = "تعذر النسخ";
            }
        });
        actions.appendChild(copyButton);
        content.appendChild(actions);
    } else {
        content.textContent = text;
    }

    if (type === "user" && Array.isArray(attachments) && attachments.length) {
        const previews = document.createElement("div");
        previews.className = "message-attachments";
        attachments.forEach(function (item) {
            if (item.type && item.type.startsWith("image/") && item.preview) {
                const image = document.createElement("img");
                image.src = item.preview;
                image.alt = item.name;
                previews.appendChild(image);
            } else {
                const fileLabel = document.createElement("span");
                fileLabel.className = "message-attachment-file";
                fileLabel.textContent = "📎 " + item.name;
                previews.appendChild(fileLabel);
            }
        });
        content.appendChild(previews);
    }
    message.appendChild(content);
    messages.appendChild(message);
    messages.scrollTop = messages.scrollHeight;
}

/* =========================
   ACCOUNT
========================= */

async function refreshAccount() {
    try {
        const response = await fetch("/api/me");
        const data = await response.json();

        if (!data.logged_in) return;

        const loginLink = document.getElementById("loginLink");
        const logout = document.getElementById("logout");
        const who = document.getElementById("who");
        const credits = document.getElementById("credits");
        const adminLink = document.getElementById("adminLink");

        if (loginLink) loginLink.hidden = true;
        if (logout) logout.hidden = false;

        if (who) {
            who.textContent = "يا " + data.name + " ❤️";
        }

        if (credits) {
            credits.textContent = "🎁 باقي ليك " + data.credits + " استخدام";
        }

        if (adminLink) {
            adminLink.hidden = !data.is_admin;
        }
    } catch (error) {
        console.error("خطأ في تحديث الحساب:", error);
    }
}

/* =========================
   CONVERSATIONS
========================= */

function getConversationItems() {
    let items = document.getElementById("conversationItems");

    if (!items && sidebar) {
        let list = document.getElementById("conversationList");

        if (!list) {
            list = document.createElement("div");
            list.id = "conversationList";
            list.className = "conversation-list";

            const newButton = sidebar.querySelector(".new-chat");

            if (newButton) {
                newButton.insertAdjacentElement("afterend", list);
            } else {
                sidebar.appendChild(list);
            }
        }

        items = document.createElement("div");
        items.id = "conversationItems";
        items.className = "conversation-items";

        list.appendChild(items);
    }

    return items;
}

function getConversationDateGroup(value) {
    if (!value) return "أقدم";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "أقدم";
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    date.setHours(0, 0, 0, 0);
    const daysAgo = Math.floor((today.getTime() - date.getTime()) / 86400000);
    if (daysAgo <= 0) return "اليوم";
    if (daysAgo === 1) return "أمس";
    if (daysAgo <= 7) return "آخر 7 أيام";
    return "أقدم";
}

async function loadConversations(searchTerm = "") {
    const items = getConversationItems();
    if (!items) return;

    const requestSequence = ++conversationSearchSequence;
    const activeSearchTerm = String(
        searchTerm || (conversationSearch ? conversationSearch.value : "")
    ).trim();

    try {
        const params = new URLSearchParams();
        if (activeSearchTerm) params.set("q", activeSearchTerm);
        if (currentProjectId !== null) params.set("project_id", String(currentProjectId));
        const queryString = params.toString();
        const response = await fetch("/api/conversations" + (queryString ? "?" + queryString : ""));

        if (response.status === 401) return;

        const data = await response.json();
        if (requestSequence !== conversationSearchSequence) return;
        items.innerHTML = "";
        if (pinnedItems) pinnedItems.innerHTML = "";
        if (sidebarPinnedSection) sidebarPinnedSection.hidden = true;

        const conversations = data.conversations || [];

        if (conversations.length === 0) {
            const empty = document.createElement("div");
            empty.textContent = searchTerm ? "ما لقينا محادثات مطابقة للبحث" : (currentProjectId !== null ? "المشروع دا ما فيهو محادثات لسه" : "ما عندك محادثات محفوظة");
            empty.className = "conversation-empty";
            items.appendChild(empty);
            return;
        }

        const conversationGroups = new Map();
        conversations.forEach(function (conversation) {
            const item = document.createElement("div");
            item.className = "conversation-item";

            if (Number(conversation.id) === Number(currentConversationId)) {
                item.classList.add("active");
            }

            const title = document.createElement("button");
            title.type = "button";
            title.className = "conversation-title";
            title.textContent = conversation.title || "محادثة جديدة";

            const actionsButton = document.createElement("button");
            actionsButton.type = "button";
            actionsButton.className = "conversation-more";
            actionsButton.textContent = "⋯";
            actionsButton.title = "خيارات المحادثة";
            actionsButton.setAttribute("aria-label", "خيارات المحادثة");

            const actionsMenu = document.createElement("div");
            actionsMenu.className = "conversation-menu";
            actionsMenu.hidden = true;

            const renameButton = document.createElement("button");
            renameButton.type = "button";
            renameButton.className = "conversation-menu-action";
            renameButton.textContent = "إعادة التسمية";

            const pinButton = document.createElement("button");
            pinButton.type = "button";
            pinButton.className = "conversation-menu-action";
            pinButton.textContent = Number(conversation.is_pinned) === 1 ? "إلغاء التثبيت" : "تثبيت";
            pinButton.addEventListener("click", async function (event) {
                event.stopPropagation();
                actionsMenu.hidden = true;
                try {
                    const pinResponse = await fetch("/api/conversations/" + conversation.id, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ is_pinned: Number(conversation.is_pinned) !== 1 })
                    });
                    const result = await pinResponse.json();
                    if (!pinResponse.ok) {
                        alert(result.error || "ما قدرنا نغيّر حالة التثبيت.");
                        return;
                    }
                    await loadConversations();
                } catch (error) {
                    console.error("خطأ في تثبيت المحادثة:", error);
                    alert("حصل خطأ، حاول تاني.");
                }
            });

            const projectButton = document.createElement("button");
            projectButton.type = "button";
            projectButton.className = "conversation-menu-action";
            projectButton.textContent = "نقل إلى مشروع";
            projectButton.addEventListener("click", async function (event) {
                event.stopPropagation();
                actionsMenu.hidden = true;
                try {
                    const response = await fetch("/api/projects");
                    const result = await response.json();
                    if (!response.ok) {
                        showSidebarNotice(result.error || "ما قدرنا نحمّل المشروعات.");
                        return;
                    }
                    if (!projectPickerModal || !projectPickerSelect) return;
                    projectPickerSelect.replaceChildren();
                    const noProject = document.createElement("option");
                    noProject.value = "";
                    noProject.textContent = "بدون مشروع";
                    projectPickerSelect.appendChild(noProject);
                    (result.projects || []).forEach(function (project) {
                        const option = document.createElement("option");
                        option.value = String(project.id);
                        option.textContent = project.name;
                        projectPickerSelect.appendChild(option);
                    });
                    projectPickerSelect.value = conversation.project_id ? String(conversation.project_id) : "";
                    projectPickerConversationId = Number(conversation.id);
                    projectPickerModal.hidden = false;
                } catch (error) {
                    console.error("خطأ في تحميل المشروعات:", error);
                    showSidebarNotice("حصل خطأ أثناء تحميل المشروعات.");
                }
            });

            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "conversation-menu-action danger";
            deleteButton.textContent = "حذف المحادثة";

            actionsMenu.appendChild(pinButton);
            actionsMenu.appendChild(projectButton);
            actionsMenu.appendChild(renameButton);
            actionsMenu.appendChild(deleteButton);

            actionsButton.addEventListener("click", function (event) {
                event.stopPropagation();
                document.querySelectorAll(".conversation-menu").forEach(function (menu) {
                    if (menu !== actionsMenu) menu.hidden = true;
                });
                actionsMenu.hidden = !actionsMenu.hidden;
            });

            renameButton.addEventListener("click", async function (event) {
                event.stopPropagation();
                actionsMenu.hidden = true;
                const nextTitle = prompt("اكتب الاسم الجديد للمحادثة:", conversation.title || "");
                if (nextTitle === null || !nextTitle.trim()) return;
                try {
                    const renameResponse = await fetch("/api/conversations/" + conversation.id, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ title: nextTitle.trim() })
                    });
                    const result = await renameResponse.json();
                    if (!renameResponse.ok) {
                        alert(result.error || "ما قدرنا نغيّر اسم المحادثة.");
                        return;
                    }
                    await loadConversations();
                } catch (error) {
                    console.error("خطأ في إعادة تسمية المحادثة:", error);
                    alert("حصل خطأ، حاول تاني.");
                }
            });

            deleteButton.addEventListener("click", async function (event) {
                event.stopPropagation();
                actionsMenu.hidden = true;
                if (!confirm("متأكد داير تحذف المحادثة دي؟")) return;
                try {
                    const deleteResponse = await fetch("/api/conversations/" + conversation.id, { method: "DELETE" });
                    const result = await deleteResponse.json();
                    if (!deleteResponse.ok) {
                        alert(result.error || "ما قدرنا نحذف المحادثة.");
                        return;
                    }
                    if (Number(currentConversationId) === Number(conversation.id)) {
                        currentConversationId = null;
                        showWelcome(false);
                    }
                    await loadConversations();
                } catch (error) {
                    console.error("خطأ في حذف المحادثة:", error);
                    alert("حصل خطأ، حاول تاني.");
                }
            });

            title.addEventListener("click", function () {
                openConversation(conversation.id);
            });

            item.appendChild(title);
            item.appendChild(actionsButton);
            item.appendChild(actionsMenu);
            if (Number(conversation.is_pinned) === 1 && pinnedItems) {
                pinnedItems.appendChild(item);
            } else {
                const groupName = getConversationDateGroup(conversation.updated_at);
                let group = conversationGroups.get(groupName);
                if (!group) {
                    group = document.createElement("section");
                    group.className = "conversation-group";
                    const heading = document.createElement("div");
                    heading.className = "conversation-group-heading";
                    heading.textContent = groupName;
                    const groupItems = document.createElement("div");
                    groupItems.className = "conversation-group-items";
                    group.appendChild(heading);
                    group.appendChild(groupItems);
                    items.appendChild(group);
                    conversationGroups.set(groupName, group);
                }
                group.querySelector(".conversation-group-items").appendChild(item);
            }

        });
        if (sidebarPinnedSection && pinnedItems) {
            sidebarPinnedSection.hidden = pinnedItems.children.length === 0;
        }
    } catch (error) {
        console.error("خطأ في تحميل المحادثات:", error);
    }
}

async function loadProjects() {
    if (!projectItems) return;
    try {
        const response = await fetch("/api/projects");
        if (response.status === 401) return;
        const data = await response.json();
        projectItems.replaceChildren();
        (data.projects || []).forEach(function (project) {
            const row = document.createElement("div");
            row.className = "project-item";
            const openButton = document.createElement("button");
            openButton.type = "button";
            openButton.className = "project-open";
            openButton.textContent = project.name + " · " + project.conversation_count;
            openButton.dataset.projectId = String(project.id);
            openButton.classList.toggle("active", Number(currentProjectId) === Number(project.id));
            openButton.addEventListener("click", function () {
                currentProjectId = Number(project.id);
                updateProjectFilterState();
                loadConversations();
            });
            const renameButton = document.createElement("button");
            renameButton.type = "button";
            renameButton.className = "project-small-action";
            renameButton.textContent = "✎";
            renameButton.setAttribute("aria-label", "إعادة تسمية المشروع");
            renameButton.addEventListener("click", async function () {
                const name = window.prompt("اكتب الاسم الجديد للمشروع:", project.name);
                if (name === null || !name.trim()) return;
                const update = await fetch("/api/projects/" + project.id, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name: name.trim() })
                });
                const result = await update.json();
                if (!update.ok) {
                    showSidebarNotice(result.error || "ما قدرنا نعيد تسمية المشروع.");
                    return;
                }
                await loadProjects();
            });
            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "project-small-action danger";
            deleteButton.textContent = "×";
            deleteButton.setAttribute("aria-label", "حذف المشروع");
            deleteButton.addEventListener("click", async function () {
                if (!window.confirm("حذف المشروع؟ المحادثات ستبقى محفوظة خارج المشروع.")) return;
                const remove = await fetch("/api/projects/" + project.id, { method: "DELETE" });
                const result = await remove.json();
                if (!remove.ok) {
                    showSidebarNotice(result.error || "ما قدرنا نحذف المشروع.");
                    return;
                }
                if (Number(currentProjectId) === Number(project.id)) currentProjectId = null;
                updateProjectFilterState();
                await loadProjects();
                await loadConversations();
            });
            row.appendChild(openButton);
            row.appendChild(renameButton);
            row.appendChild(deleteButton);
            projectItems.appendChild(row);
        });
        updateProjectFilterState();
    } catch (error) {
        console.error("خطأ في تحميل المشروعات:", error);
        showSidebarNotice("ما قدرنا نحمّل المشروعات.");
    }
}

function updateProjectFilterState() {
    if (allConversationsButton) {
        allConversationsButton.classList.toggle("active", currentProjectId === null);
    }
    if (projectItems) {
        projectItems.querySelectorAll(".project-open").forEach(function (button) {
            button.classList.toggle("active", Number(button.dataset.projectId) === Number(currentProjectId));
        });
    }
}

/* =========================
   OPEN CONVERSATION
========================= */

async function openConversation(conversationId) {
    try {
        const response = await fetch("/api/conversations/" + conversationId);

        if (response.status === 401) {
            window.location.href = "/login";
            return;
        }

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || "ما قدرنا نفتح المحادثة.");
            return;
        }

        currentConversationId = Number(conversationId);
        if (homeQuickActions) homeQuickActions.hidden = true;

        if (messages) {
            messages.innerHTML = "";
        }

        (data.chats || []).forEach(function (chat) {
            addMessage(
                chat.content,
                chat.role === "user" ? "user" : "assistant"
            );
        });

        await loadConversations();
        closeSidebar();

        if (promptBox) promptBox.focus();
    } catch (error) {
        console.error("خطأ في فتح المحادثة:", error);
        alert("ما قدرنا نفتح المحادثة.");
    }
}

/* =========================
   WELCOME SCREEN
========================= */

function showWelcome(focusInput = true) {
    if (!messages) return;
    if (homeQuickActions) homeQuickActions.hidden = false;

    messages.innerHTML = `
        <div class="welcome-screen">
            <div class="welcome-logo">ز</div>
            <span class="welcome-eyebrow"></span>
            <h1></h1>
            <p></p>
        </div>
    `;

    const welcome = messages.querySelector(".welcome-eyebrow");
    const title = messages.querySelector("h1");
    const subtitle = messages.querySelector("p");

    if (welcome) welcome.textContent = messages.dataset.welcome || "أهلاً بيك في زولك AI 🇸🇩";
    if (title) title.textContent = messages.dataset.homeTitle || "كيف أقدر أساعدك اليوم؟";
    if (subtitle) subtitle.textContent = messages.dataset.homeSubtitle || "اسأل، اتعلّم، اكتب، أو ناقش أي فكرة.";

    if (promptBox) {
        promptBox.value = "";
        if (focusInput) promptBox.focus();
    }
}


/* =========================
   NEW CONVERSATION
========================= */

async function createNewConversation() {
    try {
        const response = await fetch("/api/conversations", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const data = await response.json();

        if (!response.ok) {
            addMessage(data.error || "ما قدرنا نبدأ محادثة جديدة.", "assistant");
            return;
        }

        currentConversationId = Number(data.conversation_id);
        showWelcome(false);
        closeSidebar();
        await loadConversations();
        if (promptBox) promptBox.focus();
    } catch (error) {
        console.error("خطأ في بدء محادثة جديدة:", error);
        addMessage("ما قدرنا نبدأ محادثة جديدة. تأكد من اتصالك وحاول تاني.", "assistant");
    }
}

/* New Chat is handled by the unified sidebar controller below. */

/* =========================
   SEND MESSAGE
========================= */

async function sendMessage() {
    if (!promptBox || !sendButton || !messages || isSending) return;

    const question = promptBox.value.trim();
    if (!question && selectedAttachments.length === 0) return;

    isSending = true;
    if (homeQuickActions) homeQuickActions.hidden = true;
    const filesForBubble = selectedAttachments.map(function (file) {
        return {name:file.name,type:attachmentMime(file),preview:attachmentMime(file).startsWith("image/") ? URL.createObjectURL(file) : null};
    });
        addMessage(question || "راجع المرفقات التالية:", "user", filesForBubble);
    promptBox.value = "";
    updateComposerMode();
    sendButton.disabled = true;
    if (composerAdd) composerAdd.disabled = true;
    sendButton.innerHTML = '<span class="send-icon">…</span>';

    let liveMessage = null;
    let liveContent = null;
    let streamedText = "";
    let streamError = "";
    let completed = false;

    try {
        const body = { message: question, attachments: await Promise.all(selectedAttachments.map(fileToPayload)) };
        if (currentConversationId !== null) body.conversation_id = currentConversationId;
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json", "Accept": "text/event-stream" },
            body: JSON.stringify(body)
        });

        if (response.status === 401) {
            window.location.href = "/login";
            return;
        }

        if (!response.ok) {
            const data = await response.json().catch(function () { return {}; });
            addMessage(data.error || "حصل خطأ، جرّب تاني.", "assistant");
            await refreshAccount();
            return;
        }

        if (!response.body || !response.body.getReader) throw new Error("المتصفح لا يدعم استقبال الرد المباشر.");

        clearSelectedAttachments();
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        let streamFinished = false;

        function handleEvent(rawEvent) {
            const lines = rawEvent.split(/\r?\n/);
            let eventName = "message";
            let payloadText = "";
            lines.forEach(function (line) {
                if (line.startsWith("event:")) eventName = line.slice(6).trim();
                if (line.startsWith("data:")) payloadText += line.slice(5).trim();
            });
            if (!payloadText) return;
            let payload;
            try { payload = JSON.parse(payloadText); } catch (_) { return; }

            if (eventName === "meta" && payload.conversation_id) {
                currentConversationId = Number(payload.conversation_id);
            } else if (eventName === "token" && payload.text) {
                if (!liveMessage) {
                    liveMessage = document.createElement("div");
                    liveMessage.className = "message assistant";
                    liveContent = document.createElement("div");
                    liveContent.className = "message-content streaming-content";
                    liveMessage.appendChild(liveContent);
                    messages.appendChild(liveMessage);
                }
                streamedText += payload.text;
                liveContent.textContent = streamedText;
                messages.scrollTop = messages.scrollHeight;
            } else if (eventName === "error") {
                streamError = payload.error || "حصل خطأ أثناء توليد الرد.";
                streamFinished = true;
            } else if (eventName === "done") {
                completed = true;
                streamFinished = true;
                if (payload.conversation_id) currentConversationId = Number(payload.conversation_id);
            }
        }

        while (!streamFinished) {
            const result = await reader.read();
            if (result.done) break;
            buffer += decoder.decode(result.value, { stream: true });
            const events = buffer.split(/\r?\n\r?\n/);
            buffer = events.pop() || "";
            for (const eventText of events) {
                handleEvent(eventText);
                if (streamFinished) break;
            }
        }

        if (streamFinished) {
            try { await reader.cancel(); } catch (_) {}
        } else {
            buffer += decoder.decode();
            if (buffer.trim()) handleEvent(buffer);
        }

        if (liveMessage) liveMessage.remove();
        if (streamedText) addMessage(streamedText, "assistant");
        if (streamError) addMessage(streamError, "assistant");
        else if (!completed) addMessage("انقطع الاتصال قبل اكتمال الرد. حاول تاني.", "assistant");

        await refreshAccount();
        await loadConversations();
    } catch (error) {
        console.error("خطأ في إرسال الرسالة:", error);
        if (liveMessage) liveMessage.remove();
        addMessage("ما قدرنا نكمل الاتصال بالخدمة. تأكد من الإنترنت وحاول تاني.", "assistant");
    } finally {
        isSending = false;
        sendButton.disabled = false;
        if (composerAdd) composerAdd.disabled = false;
        sendButton.innerHTML = '<span class="send-icon">↑</span>';
        if (promptBox) promptBox.focus();
    }
}

const composerInner = document.querySelector(".composer-inner");
function updateComposerMode() {
    if (!composerInner || !promptBox) return;
    composerInner.classList.toggle("has-text", Boolean(promptBox.value.trim()));
}
if (promptBox) promptBox.addEventListener("input", updateComposerMode);
updateComposerMode();

/* =========================
   SEND BUTTON
========================= */

if (sendButton) {
    sendButton.addEventListener("click", sendMessage);
}

/* =========================
   ENTER KEY
========================= */

if (promptBox) {
    promptBox.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    });
}




/* =========================================================
   ZOLAK SIDEBAR CONTROLLER — one explicit capture-phase router
   Prevents duplicate handlers and click interception by legacy
   bubbling listeners. Only handles the primary sidebar controls.
========================================================= */
(function bindZolakSidebarControls() {
    if (document.documentElement.dataset.zolakSidebarController === "v2") return;
    document.documentElement.dataset.zolakSidebarController = "v2";

    function closestFromEvent(event, selector) {
        const target = event.target instanceof Element ? event.target : event.target && event.target.parentElement;
        return target ? target.closest(selector) : null;
    }

    function applyTheme(next) {
        const body = document.body;
        const dark = next === "dark";
        body.classList.toggle("theme-dark", dark);
        body.classList.toggle("theme-light", !dark);
        try { localStorage.setItem("zolak-theme", dark ? "dark" : "light"); } catch (_) {}
        const toggle = document.getElementById("themeToggle");
        const label = document.getElementById("themeToggleLabel");
        if (toggle) {
            toggle.setAttribute("aria-pressed", String(dark));
            toggle.setAttribute("aria-label", dark ? "التبديل إلى الوضع النهاري" : "التبديل إلى الوضع الليلي");
        }
        if (label) label.textContent = dark ? "الوضع النهاري" : "الوضع الليلي";
        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.content = dark ? "#303844" : "#f4f6f8";
    }

    let initialTheme = document.body.classList.contains("theme-light") ? "light" : "dark";
    try { const savedTheme = localStorage.getItem("zolak-theme"); if (savedTheme === "light" || savedTheme === "dark") initialTheme = savedTheme; } catch (_) {}
    applyTheme(initialTheme);

    document.addEventListener("click", function (event) {
        const newChat = closestFromEvent(event, "#newChat");
        const themeButton = closestFromEvent(event, "#themeToggle");
        const tool = closestFromEvent(event, ".sidebar-tool[data-tool]");
        const createProject = closestFromEvent(event, "#createProjectButton");
        const allChats = closestFromEvent(event, "#allConversationsButton");
        const explore = closestFromEvent(event, ".explore-prompt[data-explore-prompt]");
        const collapse = closestFromEvent(event, "#sidebarCollapseButton");
        const mobile = closestFromEvent(event, ".mobile-menu");

        if (!(newChat || themeButton || tool || createProject || allChats || explore || collapse || mobile)) return;

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        if (newChat) {
            if (newChat.dataset.busy === "1") return;
            newChat.dataset.busy = "1";
            Promise.resolve(createNewConversation())
                .catch(function (error) { console.error("New chat failed:", error); showSidebarNotice("تعذر إنشاء محادثة جديدة. حاول مرة أخرى."); })
                .finally(function () { newChat.dataset.busy = "0"; });
            closeSidebar();
            return;
        }

        if (themeButton) {
            applyTheme(document.body.classList.contains("theme-dark") ? "light" : "dark");
            return;
        }

        if (tool) {
            const action = tool.dataset.tool;
            if (action === "projects") {
                if (!projectsPanel) return;
                projectsPanel.hidden = !projectsPanel.hidden;
                if (explorePanel) explorePanel.hidden = true;
                if (!projectsPanel.hidden) loadProjects();
            } else if (action === "explore") {
                if (!explorePanel) return;
                explorePanel.hidden = !explorePanel.hidden;
                if (projectsPanel) projectsPanel.hidden = true;
            } else if (action === "images" || action === "library") {
                const picker = document.getElementById("attachmentInput");
                if (!picker) { showSidebarNotice("خيار إرفاق الملفات غير متاح حالياً."); return; }
                picker.accept = action === "images" ? "image/*" : "image/*,.pdf,.docx,.txt,.md,.csv";
                picker.click();
                closeSidebar();
            }
            return;
        }

        if (createProject) { createProjectFromSidebar().catch(function (error) { console.error(error); showSidebarNotice("تعذر إنشاء المشروع."); }); return; }
        if (allChats) {
            currentProjectId = null;
            updateProjectFilterState();
            loadConversations();
            return;
        }
        if (explore) {
            if (promptBox) {
                promptBox.value = explore.dataset.explorePrompt || "";
                promptBox.focus();
                promptBox.setSelectionRange(promptBox.value.length, promptBox.value.length);
                updateComposerMode();
            }
            if (explorePanel) explorePanel.hidden = true;
            closeSidebar();
            return;
        }
        if (collapse) {
            if (appShell && window.innerWidth > 800) setDesktopSidebarCollapsed(!appShell.classList.contains("sidebar-collapsed"));
            return;
        }
        if (mobile) toggleSidebar();
    }, true);
})();
