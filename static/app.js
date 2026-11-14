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
const conversationSearch = document.getElementById("conversationSearch");

const sidebarSearchButton = document.getElementById("sidebarSearch");
if (sidebarSearchButton) {
    sidebarSearchButton.addEventListener("click", function () {
        const term = window.prompt("ابحث في محادثاتك:");
        if (term === null || !term.trim()) return;
        const query = term.trim().toLocaleLowerCase();
        document.querySelectorAll("#conversationItems .conversation-item").forEach(function (item) {
            item.hidden = !item.textContent.toLocaleLowerCase().includes(query);
        });
    });
}
document.querySelectorAll(".sidebar-tool").forEach(function (tool) {
    tool.addEventListener("click", function () {
        const labels = {images:"الصور",library:"المكتبة",projects:"المشروعات",explore:"استكشاف"};
        const label = labels[tool.dataset.tool];
        if (!label) return;
        let notice = document.querySelector(".sidebar-feature-notice");
        if (!notice) {
            notice = document.createElement("div");
            notice.className = "sidebar-feature-notice";
            document.body.appendChild(notice);
        }
        notice.textContent = "ميزة " + label + " قيد التجهيز.";
        notice.hidden = false;
        window.setTimeout(function () { notice.hidden = true; }, 2200);
    });
});


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

if (mobileMenu) {
    mobileMenu.setAttribute("aria-expanded", "false");
    mobileMenu.setAttribute("aria-label", "فتح القائمة");

    mobileMenu.addEventListener("click", function (event) {
        event.preventDefault();

        if (window.innerWidth <= 800) {
            toggleSidebar();
        }
    });
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
const historyButton = document.getElementById("historyButton");
if (historyButton) historyButton.addEventListener("click", openSidebar);
function showSidebarNotice(message) {
    let notice = document.querySelector(".sidebar-feature-notice");
    if (!notice) { notice = document.createElement("div"); notice.className = "sidebar-feature-notice"; document.body.appendChild(notice); }
    notice.textContent = message; notice.hidden = false;
    window.clearTimeout(notice._hideTimer);
    notice._hideTimer = window.setTimeout(function () { notice.hidden = true; }, 2400);
}
const plusSubscribe = document.getElementById("plusSubscribe");
if (plusSubscribe) plusSubscribe.addEventListener("click", function () { showSidebarNotice("اشتراك زولاك بلس قيد التجهيز."); });
document.querySelectorAll(".home-quick-action").forEach(function (button) {
    button.addEventListener("click", function () {
        if (!promptBox) return;
        promptBox.value = button.dataset.prompt || "";
        promptBox.focus();
        promptBox.setSelectionRange(promptBox.value.length, promptBox.value.length);
    });
});
const composerAdd = document.getElementById("composerAdd");
const attachmentInput = document.getElementById("attachmentInput");
const attachmentPreview = document.getElementById("attachmentPreview");
let selectedAttachments = [];

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
        if (file.type.startsWith("image/")) {
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
            "application/pdf", "text/plain", "text/markdown", "text/csv"
        ]);
        const incoming = Array.from(attachmentInput.files || []);
        for (const file of incoming) {
            if (!accepted.has(file.type)) {
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
                mime_type: file.type,
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
const composerVoice = document.getElementById("composerVoice");
if (composerVoice) composerVoice.addEventListener("click", function () {
    const last = messages ? Array.from(messages.querySelectorAll(".message.assistant .message-content")).pop() : null;
    if (!last) { showSidebarNotice("لما يوصلك رد، اضغط هنا لسماعه بالصوت."); return; }
    if (!("speechSynthesis" in window)) { showSidebarNotice("قراءة الرد صوتياً غير مدعومة."); return; }
    window.speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(last.textContent); utterance.lang = "ar"; window.speechSynthesis.speak(utterance);
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

function renderAssistantMarkdown(container, source) {
    const lines = String(source || "").replace(/\r\n/g, "\n").split("\n");
    let paragraph = [];
    let list = null;
    let codeLines = null;

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

    function appendCodeBlock(code) {
        const wrapper = document.createElement("div");
        wrapper.className = "code-block";
        const toolbar = document.createElement("div");
        toolbar.className = "code-toolbar";
        const label = document.createElement("span");
        label.textContent = "كود";
        const copy = document.createElement("button");
        copy.type = "button";
        copy.className = "code-copy";
        copy.textContent = "نسخ الكود";
        copy.addEventListener("click", async function () {
            try {
                await navigator.clipboard.writeText(code);
                copy.textContent = "تم النسخ ✓";
            } catch (error) {
                copy.textContent = "تعذر النسخ";
            }
        });
        toolbar.appendChild(label);
        toolbar.appendChild(copy);
        const pre = document.createElement("pre");
        const codeElement = document.createElement("code");
        codeElement.textContent = code;
        pre.appendChild(codeElement);
        wrapper.appendChild(toolbar);
        wrapper.appendChild(pre);
        container.appendChild(wrapper);
    }

    lines.forEach(function (line) {
        if (codeLines !== null) {
            if (/^\s*```/.test(line)) {
                appendCodeBlock(codeLines.join("\n"));
                codeLines = null;
            } else {
                codeLines.push(line);
            }
            return;
        }

        if (/^\s*```/.test(line)) {
            flushParagraph();
            flushList();
            codeLines = [];
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

    if (codeLines !== null) appendCodeBlock(codeLines.join("\n"));
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

async function loadConversations(searchTerm = "") {
    const items = getConversationItems();
    if (!items) return;

    try {
        const response = await fetch("/api/conversations" + (searchTerm ? "?q=" + encodeURIComponent(searchTerm) : ""));

        if (response.status === 401) return;

        const data = await response.json();
        items.innerHTML = "";

        const conversations = data.conversations || [];

        if (conversations.length === 0) {
            const empty = document.createElement("div");
            empty.textContent = searchTerm ? "ما لقينا محادثات مطابقة للبحث" : "ما عندك محادثات محفوظة";
            empty.className = "conversation-empty";
            items.appendChild(empty);
            return;
        }

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

            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "conversation-menu-action danger";
            deleteButton.textContent = "حذف المحادثة";

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

        });
    } catch (error) {
        console.error("خطأ في تحميل المحادثات:", error);
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

const newChatButton = document.querySelector(".new-chat");

if (newChatButton) {
    newChatButton.addEventListener("click", function (event) {
        event.preventDefault();
        createNewConversation();
    });
}

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
        return {name:file.name,type:file.type,preview:file.type.startsWith("image/") ? URL.createObjectURL(file) : null};
    });
    const attachmentNames = selectedAttachments.map(function (file) { return file.name; });
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
        clearSelectedAttachments();

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

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

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
            } else if (eventName === "done") {
                completed = true;
                if (payload.conversation_id) currentConversationId = Number(payload.conversation_id);
            }
        }

        while (true) {
            const result = await reader.read();
            if (result.done) break;
            buffer += decoder.decode(result.value, { stream: true });
            const events = buffer.split(/\r?\n\r?\n/);
            buffer = events.pop() || "";
            events.forEach(handleEvent);
        }
        buffer += decoder.decode();
        if (buffer.trim()) handleEvent(buffer);

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


