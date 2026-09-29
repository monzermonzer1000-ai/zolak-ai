"use strict";

const promptBox = document.getElementById("prompt");
const sendButton = document.getElementById("send");
const messages = document.getElementById("messages");
const sidebar = document.querySelector(".sidebar");
const mobileMenu = document.querySelector(".mobile-menu");

let currentConversationId = null;


/* =========================
   الرسائل
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
   الحساب
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
            credits.textContent =
                "🎁 باقي ليك " + data.credits + " استخدام";
        }

        if (adminLink && data.is_admin) {
            adminLink.hidden = false;
        }

    } catch (error) {
        console.error("خطأ في تحديث الحساب:", error);
    }
}


/* =========================
   قائمة المحادثات
========================= */

function getConversationItems() {

    let items =
        document.getElementById("conversationItems");

    if (!items && sidebar) {

        let list =
            document.getElementById("conversationList");

        if (!list) {

            list = document.createElement("div");

            list.id = "conversationList";
            list.className = "conversation-list";

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

        items = document.createElement("div");

        items.id = "conversationItems";
        items.className = "conversation-items";

        list.appendChild(items);
    }

    return items;
}


/* =========================
   تحميل المحادثات
========================= */

async function loadConversations() {

    const items = getConversationItems();

    if (!items) return;

    try {

        const response =
            await fetch("/api/conversations");

        if (response.status === 401) {
            return;
        }

        const data =
            await response.json();

        items.innerHTML = "";

        const conversations =
            data.conversations || [];

        if (conversations.length === 0) {

            const empty =
                document.createElement("div");

            empty.textContent =
                "ما عندك محادثات محفوظة";

            empty.style.padding = "8px";
            empty.style.fontSize = "12px";
            empty.style.opacity = "0.55";

            items.appendChild(empty);

            return;
        }


        conversations.forEach(function (conversation) {

            const item =
                document.createElement("div");

            item.className =
                "conversation-item";

            if (
                Number(conversation.id) ===
                Number(currentConversationId)
            ) {
                item.classList.add("active");
            }


            const title =
                document.createElement("span");

            title.className =
                "conversation-title";

            title.textContent =
                conversation.title ||
                "محادثة جديدة";


            const deleteButton =
                document.createElement("button");

            deleteButton.type = "button";
            deleteButton.className =
                "conversation-delete";

            deleteButton.textContent = "×";
            deleteButton.title =
                "حذف المحادثة";


            deleteButton.addEventListener(
                "click",
                async function (event) {

                    event.stopPropagation();

                    const confirmed =
                        confirm(
                            "متأكد داير تحذف المحادثة دي؟"
                        );

                    if (!confirmed) return;

                    try {

                        const response =
                            await fetch(
                                "/api/conversations/" +
                                conversation.id,
                                {
                                    method: "DELETE"
                                }
                            );

                        const data =
                            await response.json();

                        if (!response.ok) {

                            alert(
                                data.error ||
                                "ما قدرنا نحذف المحادثة."
                            );

                            return;
                        }


                        if (
                            Number(
                                currentConversationId
                            ) ===
                            Number(conversation.id)
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
                            "حصل خطأ، حاول تاني."
                        );
                    }
                }
            );


            item.appendChild(title);
            item.appendChild(deleteButton);


            item.addEventListener(
                "click",
                function () {

                    openConversation(
                        conversation.id
                    );
                }
            );


            items.appendChild(item);

        });


    } catch (error) {

        console.error(
            "خطأ في تحميل المحادثات:",
            error
        );
    }
}


/* =========================
   فتح محادثة قديمة
========================= */

async function openConversation(conversationId) {

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


        chats.forEach(function (chat) {

            addMessage(
                chat.content,
                chat.role === "user"
                    ? "user"
                    : "assistant"
            );

        });


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
            "ما قدرنا نفتح المحادثة."
        );
    }
}


/* =========================
   محادثة جديدة
========================= */

async function createNewConversation() {

    currentConversationId = null;

    showWelcome();

    closeSidebar();

    /*
     * لا ننشئ السجل في قاعدة البيانات
     * إلا بعد إرسال أول رسالة.
     * ده يمنع إنشاء محادثات فارغة.
     */

    if (promptBox) {
        promptBox.focus();
    }

    await loadConversations();
}


const newChatButton =
    document.querySelector(".new-chat");


if (newChatButton) {

    newChatButton.addEventListener(
        "click",
        function (event) {

            event.preventDefault();

            createNewConversation();

        }
    );
}


/* =========================
   إرسال الرسالة
========================= */

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

    sendButton.disabled = true;

    sendButton.innerHTML =
        '<span class="send-icon">…</span>';


    try {

        const body = {
            message: question
        };


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


        if (response.status === 401) {

            window.location.href =
                "/login";

            return;
        }


        if (!response.ok) {

            addMessage(
                data.error ||
                "حصل خطأ، جرّب تاني.",
                "assistant"
            );

            refreshAccount();

            return;
        }


        /*
         * أول رسالة في المحادثة
         * تنشئ conversation_id من السيرفر.
         */

        if (
            data.conversation_id
        ) {

            currentConversationId =
                Number(
                    data.conversation_id
                );
        }


        addMessage(
            data.answer ||
            data.error ||
            "حصل خطأ، جرّب تاني.",
            "assistant"
        );


        await refreshAccount();

        await loadConversations();


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

        sendButton.disabled = false;

        sendButton.innerHTML =
            '<span class="send-icon">↑</span>';

        promptBox.focus();
    }
}


/* =========================
   زر الإرسال
========================= */

if (sendButton) {

    sendButton.addEventListener(
        "click",
        sendMessage
    );
}


/* =========================
   Enter
========================= */

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


/* =========================
   القائمة الجانبية للموبايل
========================= */

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

    document.body.appendChild(
        sidebarOverlay
    );
}


sidebarOverlay.style.position =
    "fixed";

sidebarOverlay.style.inset =
    "0";

sidebarOverlay.style.zIndex =
    "40";

sidebarOverlay.style.background =
    "rgba(0,0,0,0.35)";

sidebarOverlay.style.backdropFilter =
    "blur(2px)";

sidebarOverlay.style.opacity =
    "0";

sidebarOverlay.style.pointerEvents =
    "none";

sidebarOverlay.style.transition =
    "opacity 0.25s ease";


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


sidebarOverlay.addEventListener(
    "click",
    function () {

        closeSidebar();

    }
);


document.addEventListener(
    "keydown",
    function (event) {

        if (
            event.key === "Escape"
        ) {

            closeSidebar();
        }
    }
);


window.addEventListener(
    "resize",
    function () {

        if (
            window.innerWidth > 800
        ) {

            closeSidebar();
        }
    }
);


/* =========================
   بطاقات الاقتراح
========================= */

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

        promptBox.value = text;

        sendMessage();

    },
    true
);


/* =========================
   الترحيب
========================= */

function showWelcome(
    focusInput = true
) {

    if (!messages) return;


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
   تشغيل الموقع
========================= */

async function initializeApp() {

    await refreshAccount();

    await loadConversations();

}


initializeApp();
