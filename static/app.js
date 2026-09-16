const promptBox = document.getElementById("prompt");
const sendButton = document.getElementById("send");
const messages = document.getElementById("messages");


// =========================
// إضافة رسالة
// =========================

function addMessage(text, type) {

    const message = document.createElement("div");

    message.className = "message " + type;

    const content = document.createElement("div");

    content.className = "message-content";

    content.textContent = text;

    message.appendChild(content);

    messages.appendChild(message);

    messages.scrollTop = messages.scrollHeight;
}


// =========================
// تحديث الحساب
// =========================

async function refreshAccount() {

    try {

        const response = await fetch("/api/me");

        const data = await response.json();

        if (data.logged_in) {

            document.getElementById("loginLink").hidden = true;

            document.getElementById("logout").hidden = false;

            document.getElementById("who").textContent =
                "يا " + data.name + " ❤️";

            document.getElementById("credits").textContent =
                "🎁 باقي ليك " + data.credits + " استخدام";

            if (data.is_admin) {

                document.getElementById("adminLink").hidden = false;

            }

        }

    } catch (error) {

        console.log("Account refresh error:", error);

    }

}


// =========================
// إرسال الرسالة
// =========================

async function sendMessage() {

    const question = promptBox.value.trim();

    if (!question) return;

    addMessage(question, "user");

    promptBox.value = "";

    sendButton.disabled = true;

    sendButton.textContent = "…";

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

        addMessage(
            "ما قدرنا نتصل بالخدمة، جرّب تاني.",
            "assistant"
        );

    }

    sendButton.disabled = false;

    sendButton.textContent = "↑";
}


// =========================
// زر الإرسال
// =========================

if (sendButton) {

    sendButton.addEventListener("click", sendMessage);

}


// =========================
// زر Enter
// =========================

if (promptBox) {

    promptBox.addEventListener("keydown", function (event) {

        if (event.key === "Enter" && !event.shiftKey) {

            event.preventDefault();

            sendMessage();

        }

    });

}


// =========================
// الأزرار السريعة
// =========================

document.querySelectorAll(".quick-actions button").forEach(function (button) {

    button.addEventListener("click", function () {

        const title = button.querySelector("strong");

        if (!title) return;

        const action = title.textContent.trim();

        const prompts = {

            "اكتب لي":
                "اكتب لي منشور أو رسالة جميلة ومناسبة.",

            "ساعدني أفهم":
                "اشرح لي الموضوع بطريقة بسيطة وسهلة الفهم.",

            "عدّل الكلام":
                "عدّل لي الكلام وصيغه بطريقة أفضل وأوضح.",

            "أديني فكرة":
                "أديني فكرة جديدة ومميزة."

        };

        promptBox.value =
            prompts[action] || "";

        promptBox.focus();

    });

});


// =========================
// محادثة جديدة
// =========================

const newChatButton =
    document.querySelector(".new-chat");

if (newChatButton) {

    newChatButton.addEventListener("click", function () {

        messages.innerHTML = `
            <div class="welcome-screen">

                <div class="welcome-logo">
                    Z
                </div>

                <h1>كيف أقدر أساعدك؟</h1>

                <p>
                    زولك AI — مساعدك الذكي بطابع سوداني 🇸🇩
                </p>

                <div class="quick-actions">

                    <button type="button">
                        <span>✍️</span>
                        <div>
                            <strong>اكتب لي</strong>
                            <small>منشور أو رسالة</small>
                        </div>
                    </button>

                    <button type="button">
                        <span>📚</span>
                        <div>
                            <strong>ساعدني أفهم</strong>
                            <small>شرح وتبسيط</small>
                        </div>
                    </button>

                    <button type="button">
                        <span>📝</span>
                        <div>
                            <strong>عدّل الكلام</strong>
                            <small>صياغة وتصحيح</small>
                        </div>
                    </button>

                    <button type="button">
                        <span>💡</span>
                        <div>
                            <strong>أديني فكرة</strong>
                            <small>أفكار وحلول</small>
                        </div>
                    </button>

                </div>

            </div>
        `;

        attachQuickButtons();

        promptBox.value = "";

        promptBox.focus();

    });

}


// =========================
// تشغيل الأزرار السريعة
// =========================

function attachQuickButtons() {

    document
        .querySelectorAll(".quick-actions button")
        .forEach(function (button) {

            button.addEventListener("click", function () {

                const title =
                    button.querySelector("strong");

                if (!title) return;

                const action =
                    title.textContent.trim();

                const prompts = {

                    "اكتب لي":
                        "اكتب لي منشور أو رسالة جميلة ومناسبة.",

                    "ساعدني أفهم":
                        "اشرح لي الموضوع بطريقة بسيطة وسهلة الفهم.",

                    "عدّل الكلام":
                        "عدّل لي الكلام وصيغه بطريقة أفضل وأوضح.",

                    "أديني فكرة":
                        "أديني فكرة جديدة ومميزة."

                };

                promptBox.value =
                    prompts[action] || "";

                promptBox.focus();

            });

        });

}


// =========================
// القائمة في الهاتف
// =========================

const mobileMenu =
    document.querySelector(".mobile-menu");

if (mobileMenu) {

    mobileMenu.addEventListener("click", function () {

        const sidebar =
            document.querySelector(".sidebar");

        if (!sidebar) return;

        if (sidebar.style.display === "flex") {

            sidebar.style.display = "none";

        } else {

            sidebar.style.display = "flex";

            sidebar.style.position = "fixed";

            sidebar.style.zIndex = "1000";

            sidebar.style.right = "0";

            sidebar.style.top = "0";

            sidebar.style.bottom = "0";

        }

    });

}


// =========================
// تشغيل الحساب
// =========================

refreshAccount();
