"use strict";

/* =========================
   ZOLAK AI — APP
========================= */

const promptBox = document.getElementById("prompt");
const sendButton = document.getElementById("send");
const messages = document.getElementById("messages");
const sidebar = document.querySelector(".sidebar");
const mobileMenu = document.querySelector(".mobile-menu");
const conversationSearch = document.getElementById("conversationSearch");
let conversationSearchTimer = null;

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

function addMessage(text, type) {
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

            const renameButton = document.createElement("button");
            renameButton.type = "button";
            renameButton.className = "conversation-rename";
            renameButton.textContent = "✎";
            renameButton.title = "إعادة تسمية المحادثة";
            renameButton.setAttribute("aria-label", "إعادة تسمية المحادثة");

            renameButton.addEventListener("click", async function (event) {
                event.stopPropagation();
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
                    await loadConversations(conversationSearch ? conversationSearch.value.trim() : "");
                } catch (error) {
                    console.error("خطأ في إعادة تسمية المحادثة:", error);
                    alert("حصل خطأ، حاول تاني.");
                }
            });

            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "conversation-delete";
            deleteButton.textContent = "×";
            deleteButton.title = "حذف المحادثة";
            deleteButton.setAttribute("aria-label", "حذف المحادثة");

            title.addEventListener("click", function () {
                openConversation(conversation.id);
            });

            deleteButton.addEventListener("click", async function (event) {
                event.stopPropagation();

                if (!confirm("متأكد داير تحذف المحادثة دي؟")) return;

                try {
                    const deleteResponse = await fetch(
                        "/api/conversations/" + conversation.id,
                        { method: "DELETE" }
                    );

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

            item.appendChild(title);
            item.appendChild(renameButton);
            item.appendChild(deleteButton);
            items.appendChild(item);
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
    if (!promptBox || !sendButton || !messages || isSending) {
        return;
    }

    const question = promptBox.value.trim();

    if (!question) return;

    isSending = true;

    addMessage(question, "user");
    promptBox.value = "";
    sendButton.disabled = true;
    sendButton.innerHTML = '<span class="send-icon">…</span>';

    try {
        const body = { message: question };

        if (currentConversationId !== null) {
            body.conversation_id = currentConversationId;
        }

        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(body)
        });

        const data = await response.json();

        if (response.status === 401) {
            window.location.href = "/login";
            return;
        }

        if (!response.ok) {
            addMessage(data.error || "حصل خطأ، جرّب تاني.", "assistant");
            await refreshAccount();
            return;
        }

        if (data.conversation_id) {
            currentConversationId = Number(data.conversation_id);
        }

        addMessage(
            data.answer || data.error || "حصل خطأ، جرّب تاني.",
            "assistant"
        );

        await refreshAccount();
        await loadConversations();
    } catch (error) {
        console.error("خطأ في إرسال الرسالة:", error);

        addMessage(
            "ما قدرنا نتصل بالخدمة، تأكد من اتصالك وحاول تاني.",
            "assistant"
        );
    } finally {
        isSending = false;
        sendButton.disabled = false;
        sendButton.innerHTML = '<span class="send-icon">↑</span>';

        if (promptBox) promptBox.focus();
    }
}

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

/* =========================
   CONVERSATION SEARCH
========================= */

if (conversationSearch) {
    conversationSearch.addEventListener("input", function () {
        window.clearTimeout(conversationSearchTimer);
        conversationSearchTimer = window.setTimeout(function () {
            loadConversations(conversationSearch.value.trim());
        }, 250);
    });
}

document.addEventListener("keydown", function (event) {
    const isSearchShortcut = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k";
    if (!isSearchShortcut) return;
    event.preventDefault();
    if (conversationSearch) {
        conversationSearch.focus();
        conversationSearch.select();
    }
});

/* =========================
   INITIALIZE
========================= */

async function initializeApp() {
    await refreshAccount();
    await loadConversations();
}

initializeApp();
