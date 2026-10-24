"use strict";

/* =========================
   ZOLAK AI — APP
========================= */

const promptBox = document.getElementById("prompt");
const sendButton = document.getElementById("send");
const messages = document.getElementById("messages");
const sidebar = document.querySelector(".sidebar");
const mobileMenu = document.querySelector(".mobile-menu");

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

function addMessage(text, type) {
    if (!messages) return;

    const message = document.createElement("div");
    message.className = "message " + type;

    const content = document.createElement("div");
    content.className = "message-content";
    content.textContent = text;

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

async function loadConversations() {
    const items = getConversationItems();
    if (!items) return;

    try {
        const response = await fetch("/api/conversations");

        if (response.status === 401) return;

        const data = await response.json();
        items.innerHTML = "";

        const conversations = data.conversations || [];

        if (conversations.length === 0) {
            const empty = document.createElement("div");
            empty.textContent = "ما عندك محادثات محفوظة";
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
   NEW CONVERSATION
========================= */

async function createNewConversation() {
    currentConversationId = null;

    showWelcome(false);
    closeSidebar();

    await loadConversations();

    if (promptBox) promptBox.focus();
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
    sendButton.textContent = "…";

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
        sendButton.textContent = "إرسال";

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
   SUGGESTION CARDS
========================= */

document.addEventListener("click", function (event) {
    const card = event.target.closest(".suggestion-card");

    if (!card || !promptBox) return;

    const text = card.getAttribute("data-prompt");

    if (!text) return;

    event.preventDefault();
    promptBox.value = text;
    sendMessage();
});

/* =========================
   WELCOME SCREEN
========================= */

function showWelcome(focusInput = true) {
    if (!messages) return;

    messages.innerHTML = `
        <div class="welcome-screen">
            <div class="welcome-logo">Z</div>

            <span class="welcome-eyebrow">
                أهلاً بيك في زولك AI 🇸🇩
            </span>

            <h1>كيف أقدر أساعدك اليوم؟</h1>

            <p>
                اسأل، اتعلّم، اكتب، أو ناقش أي فكرة.
                <br>
                أنا هنا عشان أساعدك.
            </p>
        </div>
    `;

    if (promptBox) {
        promptBox.value = "";

        if (focusInput) {
            promptBox.focus();
        }
    }
}

/* =========================
   INITIALIZE
========================= */

async function initializeApp() {
    await refreshAccount();
    await loadConversations();
}

initializeApp();
