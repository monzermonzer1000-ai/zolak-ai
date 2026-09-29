"use strict";

// =========================================================
// عناصر واجهة المحادثة
// =========================================================

const promptBox = document.getElementById("prompt");
const sendButton = document.getElementById("send");
const messages = document.getElementById("messages");


// =========================================================
// المحادثة الحالية
// =========================================================

let currentConversationId = null;


// =========================================================
// إضافة رسالة للواجهة
// =========================================================

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


// =========================================================
// تحديث بيانات الحساب والرصيد
// =========================================================

async function refreshAccount() {

    try {

        const response = await fetch("/api/me");

        const data = await response.json();

        if (!data.logged_in) return;

        const loginLink =
            document.getElementById("loginLink");

        const logout =
            document.getElementById("logout");

        const who =
            document.getElementById("who");

        const credits =
            document.getElementById("credits");

        const adminLink =
            document.getElementById("adminLink");

        if (loginLink) {
            loginLink.hidden = true;
        }

        if (logout) {
            logout.hidden = false;
        }

        if (who) {

            who.textContent =
                "يا " + data.name + " ❤️";
        }

        if (credits) {

            credits.textContent =
                "🎁 باقي ليك " +
                data.credits +
                " استخدام";
        }

        if (adminLink && data.is_admin) {

            adminLink.hidden = false;
        }

    } catch (error) {

        console.error(
            "خطأ في تحديث الحساب:",
            error
        );
    }
}


// =========================================================
// إنشاء منطقة المحادثات في القائمة الجانبية
// =========================================================

function getConversationList() {

    if (!sidebar) {
        return null;
    }

    let list =
        sidebar.querySelector(
            ".conversation-list"
        );

    if (!list) {

        list = document.createElement("div");

        list.className =
            "conversation-list";

        list.innerHTML = `
            <div class="conversation-list-title">
                محادثاتك
            </div>

            <div class="conversation-items"></div>
        `;

        const newButton =
            sidebar.querySelector(".new-chat");

        if (newButton) {

            newButton.insertAdjacentElement(
                "afterend",
                list
            );

        } else {

            sidebar.appendChild(list);
        }
    }

    return list;
}


// =========================================================
// تنسيق بسيط لقائمة المحادثات
// =========================================================

function styleConversationList() {

    const list =
        getConversationList();

    if (!list) return;

    list.style.marginTop = "12px";

    list.style.padding =
        "0 10px";

    const title =
        list.querySelector(
            ".conversation-list-title"
        );

    if (title) {

        title.style.fontSize =
            "13px";

        title.style.opacity =
            "0.65";

        title.style.padding =
            "8px 6px";
    }

    const items =
        list.querySelector(
            ".conversation-items"
        );

    if (items) {

        items.style.display =
            "flex";

        items.style.flexDirection =
            "column";

        items.style.gap =
            "5px";
    }
}


// =========================================================
// تحميل قائمة المحادثات
// =========================================================

async function loadConversations() {

    try {

        const response =
            await fetch(
                "/api/conversations"
            );

        if (response.status === 401) {

            return;
        }

        const data =
            await response.json();

        const list =
            getConversationList();

        if (!list) return;

        styleConversationList();

        const items =
            list.querySelector(
                ".conversation-items"
            );

        if (!items) return;

        items.innerHTML = "";

        const conversations =
            data.conversations || [];

        if (conversations.length === 0) {

            const empty =
                document.createElement("div");

            empty.textContent =
                "لسه ما عندك محادثات محفوظة";

            empty.style.fontSize =
                "12px";

            empty.style.opacity =
                "0.5";

            empty.style.padding =
                "8px 6px";

            items.appendChild(empty);

            return;
        }

        conversations.forEach(
            function (conversation) {

                const item =
                    document.createElement("div");

                item.className =
                    "conversation-item";

                if (
                    Number(
                        conversation.id
                    ) ===
                    Number(
                        currentConversationId
                    )
                ) {

                    item.classList.add(
                        "active"
                    );
                }

                item.style.display =
                    "flex";

                item.style.alignItems =
                    "center";

                item.style.gap =
                    "5px";

                item.style.padding =
                    "9px 8px";

                item.style.borderRadius =
                    "10px";

                item.style.cursor =
                    "pointer";

                item.style.transition =
                    "0.2s";

                const title =
                    document.createElement(
                        "div"
                    );

                title.className =
                    "conversation-title";

                title.textContent =
                    conversation.title ||
                    "محادثة جديدة";

                title.style.flex =
                    "1";

                title.style.overflow =
                    "hidden";

                title.style.textOverflow =
                    "ellipsis";

                title.style.whiteSpace =
                    "nowrap";

                const deleteButton =
                    document.createElement(
                        "button"
                    );

                deleteButton.type =
                    "button";

                deleteButton.textContent =
                    "×";

                deleteButton.title =
                    "حذف المحادثة";

                deleteButton.style.border =
                    "0";

                deleteButton.style.background =
                    "transparent";

                deleteButton.style.cursor =
                    "pointer";

                deleteButton.style.opacity =
                    "0.55";

                deleteButton.style.fontSize =
                    "18px";

                deleteButton.style.padding =
                    "0 4px";

                deleteButton.addEventListener(
                    "click",
                    async function (event) {

                        event.stopPropagation();

                        const confirmed =
                            confirm(
                                "متأكد داير تحذف المحادثة دي؟"
                            );

                        if (!confirmed) {
                            return;
                        }

                        try {

                            const response =
                                await fetch(
                                    "/api/conversations/" +
                                    conversation.id,
                                    {
                                        method:
                                            "DELETE"
                                    }
                                );

                            const result =
                                await response.json();

                            if (!response.ok) {

                                alert(
                                    result.error ||
                                    "ما قدرنا نحذف المحادثة."
                                );

                                return;
                            }

                            if (
                                Number(
                                    currentConversationId
                                ) ===
                                Number(
                                    conversation.id
                                )
                            ) {

                                currentConversationId =
                                    null;

                                showWelcome();
                            }

                            loadConversations();

                        } catch (error) {

                            console.error(
                                "خطأ في حذف المحادثة:",
                                error
                            );

                            alert(
                                "حصلت مشكلة، حاول تاني."
                            );
                        }
                    }
                );

                item.appendChild(title);

                item.appendChild(
                    deleteButton
                );

                item.addEventListener(
                    "click",
                    function () {

                        openConversation(
                            conversation.id
                        );
                    }
                );

                items.appendChild(item);
            }
        );
    }

    styleActiveConversation();
}


// =========================================================
// تمييز المحادثة الحالية
// =========================================================

function styleActiveConversation() {

    document
        .querySelectorAll(
            ".conversation-item"
        )
        .forEach(
            function (item) {

                const active =
                    item.classList.contains(
                        "active"
                    );

                if (active) {

                    item.style.background =
                        "rgba(0, 200, 150, 0.15)";

                    item.style.opacity =
                        "1";

                } else {

                    item.style.background =
                        "transparent";

                    item.style.opacity =
                        "0.85";
                }
            }
        );
}


// =========================================================
// فتح محادثة قديمة
// =========================================================

async function openConversation(
    conversationId
) {

    try {

        const response =
            await fetch(
                "/api/conversations/" +
                conversationId
            );

        if (response.status === 401) {

            window.location.href =
                "/login";

            return;
        }

        const data =
            await response.json();

        if (!response.ok) {

            alert(
                data.error ||
                "ما قدرنا نفتح المحادثة."
            );

            return;
        }

        currentConversationId =
            Number(conversationId);

        if (messages) {

            messages.innerHTML = "";
        }

        const chats =
            data.chats || [];

        chats.forEach(
            function (chat) {

                addMessage(
                    chat.content,
                    chat.role === "user"
                        ? "user"
                        : "assistant"
                );
            }
        );

        if (
            chats.length === 0
        ) {

            showWelcome(
                false
            );
        }

        loadConversations();

        closeSidebar();

        if (promptBox) {

            promptBox.focus();
        }

    } catch (error) {

        console.error(
            "خطأ في فتح المحادثة:",
            error
        );

        alert(
            "ما قدرنا نفتح المحادثة، حاول تاني."
        );
    }
}


// =========================================================
// إرسال الرسالة
// =========================================================

async function sendMessage() {

    if (
        !promptBox ||
        !sendButton ||
        !messages
    ) {
        return;
    }

    const question =
        promptBox.value.trim();

    if (
        !question ||
        sendButton.disabled
    ) {
        return;
    }

    addMessage(
        question,
        "user"
    );

    promptBox.value = "";

    sendButton.disabled =
        true;

    sendButton.innerHTML =
        '<span class="send-icon">…</span>';

    try {

        const body = {
            message: question
        };

        // إذا كنا داخل محادثة موجودة
        if (
            currentConversationId !== null
        ) {

            body.conversation_id =
                currentConversationId;
        }

        const response =
            await fetch(
                "/api/chat",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(body)
                }
            );

        const data =
            await response.json();

        if (
            response.status === 401
        ) {

            window.location.href =
                "/login";

            return;
        }

        if (
            response.status === 402
        ) {

            addMessage(
                data.error ||
                "رصيدك المجاني خلص.",
                "assistant"
            );

            refreshAccount();

            return;
        }

        if (
            !response.ok
        ) {

            addMessage(
                data.error ||
                "حصل خطأ، جرّب تاني.",
                "assistant"
            );

            return;
        }

        // الباك إند ممكن ينشئ المحادثة
        // تلقائياً عند أول رسالة
        if (
            data.conversation_id
        ) {

            currentConversationId =
                Number(
                    data.conversation_id
                );
        }

        if (data.answer) {

            addMessage(
                data.answer,
                "assistant"
            );

        } else {

            addMessage(
                data.error ||
                "حصل خطأ، جرّب تاني.",
                "assistant"
            );
        }

        refreshAccount();

        loadConversations();

    } catch (error) {

        console.error(
            "خطأ في إرسال الرسالة:",
            error
        );

        addMessage(
            "ما قدرنا نتصل بالخدمة، تأكد من اتصالك وحاول تاني.",
            "assistant"
        );

    } finally {

        sendButton.disabled =
            false;

        sendButton.innerHTML =
            '<span class="send-icon">↑</span>';

        promptBox.focus();
    }
}


// =========================================================
// زر الإرسال
// =========================================================

if (sendButton) {

    sendButton.addEventListener(
        "click",
        sendMessage
    );
}


// =========================================================
// زر Enter
// =========================================================

if (promptBox) {

    promptBox.addEventListener(
        "keydown",
        function (event) {

            if (
                event.key === "Enter" &&
                !event.shiftKey
            ) {

                event.preventDefault();

                sendMessage();
            }
        }
    );
}


// =========================================================
// بطاقات الاقتراح
// =========================================================

document.addEventListener(
    "click",
    function (event) {

        const card =
            event.target.closest(
                ".suggestion-card"
            );

        if (
            !card ||
            !promptBox
        ) {
            return;
        }

        const text =
            card.getAttribute(
                "data-prompt"
            );

        if (!text) return;

        event.preventDefault();

        promptBox.value =
            text;

        sendMessage();
    },
    true
);


// =========================================================
// الترحيب / محادثة جديدة
// =========================================================

function showWelcome(
    focusInput = true
) {

    if (
        !messages ||
        !promptBox
    ) {
        return;
    }

    messages.innerHTML = `
        <div class="welcome-screen">

            <div class="welcome-logo">
                Z
            </div>

            <span class="welcome-eyebrow">
                أهلاً بيك في زولك AI 🇸🇩
            </span>

            <h1>
                كيف أقدر أساعدك اليوم؟
            </h1>

            <p>
                اسأل، اتعلّم، اكتب، أو ناقش أي فكرة.
                <br>
                أنا هنا عشان أساعدك.
            </p>

            <div class="welcome-suggestions">

                <button
                    class="suggestion-card"
                    type="button"
                    data-prompt="اشرح لي موضوع الذكاء الاصطناعي بطريقة بسيطة">

                    <span class="suggestion-icon">
                        ✦
                    </span>

                    <span class="suggestion-text">
                        <strong>
                            اشرح لي موضوع
                        </strong>

                        <small>
                            خلينا نفهم حاجة جديدة
                        </small>
                    </span>

                    <span class="suggestion-arrow">
                        ←
                    </span>

                </button>


                <button
                    class="suggestion-card"
                    type="button"
                    data-prompt="ساعدني أكتب رسالة احترافية">

                    <span class="suggestion-icon">
                        ✎
                    </span>

                    <span class="suggestion-text">
                        <strong>
                            ساعدني في الكتابة
                        </strong>

                        <small>
                            رسائل وأفكار ومحتوى
                        </small>
                    </span>

                    <span class="suggestion-arrow">
                        ←
                    </span>

                </button>


                <button
                    class="suggestion-card"
                    type="button"
                    data-prompt="اقترح لي أفكار لمشروع جديد">

                    <span class="suggestion-icon">
                        ◇
                    </span>

                    <span class="suggestion-text">
                        <strong>
                            أفكار لمشروع
                        </strong>

                        <small>
                            نخطط ونطوّر أفكارك
                        </small>
                    </span>

                    <span class="suggestion-arrow">
                        ←
                    </span>

                </button>


                <button
                    class="suggestion-card"
                    type="button"
                    data-prompt="ساعدني أتعلم مهارة جديدة">

                    <span class="suggestion-icon">
                        ⌘
                    </span>

                    <span class="suggestion-text">
                        <strong>
                            التعلّم والتطوير
                        </strong>

                        <small>
                            خطوات واضحة للتعلّم
                        </small>
                    </span>

                    <span class="suggestion-arrow">
                        ←
                    </span>

                </button>

            </div>
        </div>
    `;

    promptBox.value = "";

    if (focusInput) {

        promptBox.focus();
    }

    closeSidebar();

    styleActiveConversation();
}


// =========================================================
// القائمة الجانبية
// =========================================================

const mobileMenu =
    document.querySelector(
        ".mobile-menu"
    );

const sidebar =
    document.querySelector(
        ".sidebar"
    );


// =========================================================
// طبقة خلف القائمة
// =========================================================

let sidebarOverlay =
    document.querySelector(
        ".sidebar-overlay"
    );

if (!sidebarOverlay) {

    sidebarOverlay =
        document.createElement(
            "div"
        );

    sidebarOverlay.className =
        "sidebar-overlay";

    sidebarOverlay.style.position =
        "fixed";

    sidebarOverlay.style.inset =
        "0";

    sidebarOverlay.style.zIndex =
        "40";

    sidebarOverlay.style.background =
        "rgba(0, 0, 0, 0.35)";

    sidebarOverlay.style.backdropFilter =
        "blur(2px)";

    sidebarOverlay.style.opacity =
        "0";

    sidebarOverlay.style.pointerEvents =
        "none";

    sidebarOverlay.style.transition =
        "opacity 0.25s ease";

    document.body.appendChild(
        sidebarOverlay
    );
}


// =========================================================
// فتح القائمة
// =========================================================

function openSidebar() {

    if (!sidebar) return;

    sidebar.classList.add(
        "open"
    );

    sidebarOverlay.style.opacity =
        "1";

    sidebarOverlay.style.pointerEvents =
        "auto";

    document.body.style.overflow =
        "hidden";
}


// =========================================================
// إغلاق القائمة
// =========================================================

function closeSidebar() {

    if (!sidebar) return;

    sidebar.classList.remove(
        "open"
    );

    sidebarOverlay.style.opacity =
        "0";

    sidebarOverlay.style.pointerEvents =
        "none";

    document.body.style.overflow =
        "";
}


// =========================================================
// تبديل القائمة
// =========================================================

function toggleSidebar() {

    if (!sidebar) return;

    if (
        sidebar.classList.contains(
            "open"
        )
    ) {

        closeSidebar();

    } else {

        openSidebar();
    }
}


// =========================================================
// زر القائمة
// =========================================================

if (mobileMenu) {

    mobileMenu.addEventListener(
        "click",
        function (event) {

            event.preventDefault();

            event.stopPropagation();

            if (
                window.innerWidth <= 800
            ) {

                toggleSidebar();
            }
        }
    );
}


// =========================================================
// الضغط خارج القائمة
// =========================================================

if (sidebarOverlay) {

    sidebarOverlay.addEventListener(
        "click",
        function () {

            closeSidebar();
        }
    );
}


// =========================================================
// زر محادثة جديدة
// =========================================================

const newChatButton =
    document.querySelector(
        ".new-chat"
    );

if (newChatButton) {

    newChatButton.addEventListener(
        "click",
        function (event) {

            event.preventDefault();

            // مهم:
            // لا نرسل طلب للسيرفر هنا.
            // المحادثة الجديدة يتم إنشاؤها
            // تلقائياً عند إرسال أول رسالة.

            currentConversationId =
                null;

            showWelcome();

            loadConversations();

            closeSidebar();
        }
    );
}


// =========================================================
// إ
