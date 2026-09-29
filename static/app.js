"use strict";

// عناصر واجهة المحادثة
const promptBox = document.getElementById("prompt");
const sendButton = document.getElementById("send");
const messages = document.getElementById("messages");

// إضافة رسالة للمحادثة
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

// تحديث بيانات الحساب والرصيد
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

        if (adminLink && data.is_admin) {
            adminLink.hidden = false;
        }
    } catch (error) {
        console.error("خطأ في تحديث الحساب:", error);
    }
}

// إرسال الرسالة واستقبال رد الذكاء الاصطناعي
async function sendMessage() {
    if (!promptBox || !sendButton || !messages) return;

    const question = promptBox.value.trim();

    if (!question || sendButton.disabled) return;

    addMessage(question, "user");
    promptBox.value = "";
    sendButton.disabled = true;
    sendButton.innerHTML = '<span class="send-icon">…</span>';

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: question
            })
        });

        const data = await response.json();

        if (response.status === 401) {
            window.location.href = "/login";
            return;
        }

        addMessage(
            data.answer || data.error || "حصل خطأ، جرّب تاني.",
            "assistant"
        );

        refreshAccount();

    } catch (error) {
        console.error("خطأ في إرسال الرسالة:", error);

        addMessage(
            "ما قدرنا نتصل بالخدمة، تأكد من اتصالك وحاول تاني.",
            "assistant"
        );
    } finally {
        sendButton.disabled = false;
        sendButton.innerHTML = '<span class="send-icon">↑</span>';
        promptBox.focus();
    }
}

// زر الإرسال
if (sendButton) {
    sendButton.addEventListener("click", sendMessage);
}

// إرسال الرسالة بزر Enter
if (promptBox) {
    promptBox.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    });
}

// التعامل مع بطاقات الاقتراح
document.addEventListener("click", function (event) {
    const card = event.target.closest(".suggestion-card");

    if (!card || !promptBox) return;

    const text = card.getAttribute("data-prompt");

    if (!text) return;

    event.preventDefault();
    promptBox.value = text;
    sendMessage();
}, true);

// محتوى الترحيب الذي يظهر عند بدء محادثة جديدة
function showWelcome() {
    if (!messages || !promptBox) return;

    messages.innerHTML = `
        <div class="welcome-screen">
            <div class="welcome-logo">Z</div>
            <span class="welcome-eyebrow">أهلاً بيك في زولك AI 🇸🇩</span>

            <h1>كيف أقدر أساعدك اليوم؟</h1>

            <p>
                اسأل، اتعلّم، اكتب، أو ناقش أي فكرة.
                <br>
                أنا هنا عشان أساعدك.
            </p>

            <div class="welcome-suggestions">

                <button class="suggestion-card" type="button"
                    data-prompt="اشرح لي موضوع الذكاء الاصطناعي بطريقة بسيطة">

                    <span class="suggestion-icon">✦</span>

                    <span class="suggestion-text">
                        <strong>اشرح لي موضوع</strong>
                        <small>خلينا نفهم حاجة جديدة</small>
                    </span>

                    <span class="suggestion-arrow">←</span>
                </button>

                <button class="suggestion-card" type="button"
                    data-prompt="ساعدني أكتب رسالة احترافية">

                    <span class="suggestion-icon">✎</span>

                    <span class="suggestion-text">
                        <strong>ساعدني في الكتابة</strong>
                        <small>رسائل وأفكار ومحتوى</small>
                    </span>

                    <span class="suggestion-arrow">←</span>
                </button>

                <button class="suggestion-card" type="button"
                    data-prompt="اقترح لي أفكار لمشروع جديد">

                    <span class="suggestion-icon">◇</span>

                    <span class="suggestion-text">
                        <strong>أفكار لمشروع</strong>
                        <small>نخطط ونطوّر أفكارك</small>
                    </span>

                    <span class="suggestion-arrow">←</span>
                </button>

                <button class="suggestion-card" type="button"
                    data-prompt="ساعدني أتعلم مهارة جديدة">

                    <span class="suggestion-icon">⌘</span>

                    <span class="suggestion-text">
                        <strong>التعلّم والتطوير</strong>
                        <small>خطوات واضحة للتعلّم</small>
                    </span>

                    <span class="suggestion-arrow">←</span>
                </button>

            </div>
        </div>
    `;

    promptBox.value = "";
    promptBox.focus();

    closeSidebar();
}

// =========================
// القائمة الجانبية
// =========================

const mobileMenu = document.querySelector(".mobile-menu");
const sidebar = document.querySelector(".sidebar");

// إنشاء طبقة خلفية للقائمة
let sidebarOverlay = document.querySelector(".sidebar-overlay");

if (!sidebarOverlay) {
    sidebarOverlay = document.createElement("div");
    sidebarOverlay.className = "sidebar-overlay";

    sidebarOverlay.style.position = "fixed";
    sidebarOverlay.style.inset = "0";
    sidebarOverlay.style.zIndex = "40";
    sidebarOverlay.style.background = "rgba(0, 0, 0, 0.35)";
    sidebarOverlay.style.backdropFilter = "blur(2px)";
    sidebarOverlay.style.opacity = "0";
    sidebarOverlay.style.pointerEvents = "none";
    sidebarOverlay.style.transition = "opacity 0.25s ease";

    document.body.appendChild(sidebarOverlay);
}

// فتح القائمة
function openSidebar() {
    if (!sidebar) return;

    sidebar.classList.add("open");

    sidebarOverlay.style.opacity = "1";
    sidebarOverlay.style.pointerEvents = "auto";

    document.body.style.overflow = "hidden";
}

// إغلاق القائمة
function closeSidebar() {
    if (!sidebar) return;

    sidebar.classList.remove("open");

    sidebarOverlay.style.opacity = "0";
    sidebarOverlay.style.pointerEvents = "none";

    document.body.style.overflow = "";
}

// تبديل القائمة
function toggleSidebar() {
    if (!sidebar) return;

    if (sidebar.classList.contains("open")) {
        closeSidebar();
    } else {
        openSidebar();
    }
}

// زر القائمة ☰
if (mobileMenu) {
    mobileMenu.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();

        if (window.innerWidth <= 800) {
            toggleSidebar();
        }
    });
}

// الضغط على المنطقة خارج القائمة
if (sidebarOverlay) {
    sidebarOverlay.addEventListener("click", function () {
        closeSidebar();
    });
}

// الضغط على روابط القائمة
document.querySelectorAll(".sidebar .sidebar-link").forEach(function (link) {
    link.addEventListener("click", function () {
        if (window.innerWidth <= 800) {
            closeSidebar();
        }
    });
});

// زر محادثة جديدة
const newChatButton = document.querySelector(".new-chat");

if (newChatButton) {
    newChatButton.addEventListener("click", function () {
        showWelcome();
        closeSidebar();
    });
}

// زر Escape يقفل القائمة
document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
        closeSidebar();
    }
});

// لو انتقلنا لشاشة كبيرة، نقفل القائمة
window.addEventListener("resize", function () {
    if (window.innerWidth > 800) {
        closeSidebar();
    }
});

// تحميل بيانات الحساب عند فتح الصفحة
refreshAccount();
