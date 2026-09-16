* {
    box-sizing: border-box;
}

html,
body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    font-family: Arial, "Noto Sans Arabic", sans-serif;
    background: #212121;
    color: #fff;
}

body {
    overflow: hidden;
}

button,
textarea {
    font-family: inherit;
}

.chatgpt-layout {
    display: flex;
    width: 100%;
    height: 100vh;
    background: #212121;
}

/* =========================
   الشريط الجانبي
========================= */

.sidebar {
    width: 260px;
    height: 100%;
    background: #171717;
    display: flex;
    flex-direction: column;
    padding: 14px;
    flex-shrink: 0;
}

.brand {
    font-size: 20px;
    font-weight: 700;
    padding: 12px 10px 18px;
}

.new-chat {
    width: 100%;
    border: 1px solid #444;
    background: transparent;
    color: #fff;
    border-radius: 9px;
    padding: 11px;
    font-size: 14px;
    cursor: pointer;
    text-align: right;
}

.new-chat:hover {
    background: #2a2a2a;
}

.chat-list {
    margin-top: 15px;
    flex: 1;
}

.chat-item {
    padding: 11px 10px;
    border-radius: 8px;
    color: #ddd;
    font-size: 14px;
}

.chat-item.active {
    background: #2a2a2a;
}

.account-area {
    border-top: 1px solid #333;
    padding-top: 12px;
}

.account-area a,
.account-area button {
    display: block;
    width: 100%;
    padding: 9px 10px;
    color: #ddd;
    text-decoration: none;
    background: transparent;
    border: 0;
    text-align: right;
    cursor: pointer;
    border-radius: 7px;
}

.account-area a:hover,
.account-area button:hover {
    background: #2a2a2a;
}

/* =========================
   الصفحة الرئيسية
========================= */

.main-chat {
    flex: 1;
    min-width: 0;
    height: 100%;
    display: flex;
    flex-direction: column;
    background: #212121;
}

/* =========================
   الهيدر
========================= */

.chat-navbar {
    height: 58px;
    border-bottom: 1px solid #303030;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 22px;
    flex-shrink: 0;
}

.model-name {
    font-size: 15px;
    font-weight: 600;
}

.online-status {
    font-size: 12px;
    color: #aaa;
}

/* =========================
   الرسائل
========================= */

.messages {
    flex: 1;
    overflow-y: auto;
    padding: 30px 20px 150px;
}

.messages::-webkit-scrollbar {
    width: 7px;
}

.messages::-webkit-scrollbar-thumb {
    background: #444;
    border-radius: 10px;
}

/* =========================
   شاشة الترحيب
========================= */

.welcome {
    max-width: 760px;
    margin: 80px auto 0;
    text-align: center;
}

.welcome h1 {
    font-size: 30px;
    margin: 0 0 12px;
}

.welcome p {
    color: #aaa;
    font-size: 15px;
    margin-bottom: 30px;
}

.quick-actions {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
}

.quick-card {
    background: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 12px;
    padding: 16px;
    color: #ddd;
    cursor: pointer;
    text-align: right;
}

.quick-card:hover {
    background: #303030;
}

/* =========================
   الرسائل
========================= */

.message {
    max-width: 820px;
    margin: 0 auto 24px;
    line-height: 1.8;
    font-size: 15px;
}

.message.user {
    text-align: right;
}

.message.assistant {
    text-align: right;
}

.message-content {
    display: inline-block;
    max-width: 85%;
    padding: 12px 16px;
    border-radius: 14px;
    white-space: pre-wrap;
    word-break: break-word;
}

.message.user .message-content {
    background: #303030;
}

.message.assistant .message-content {
    background: transparent;
}

/* =========================
   منطقة الكتابة
========================= */

.composer-area {
    position: fixed;
    bottom: 0;
    left: 260px;
    right: 0;
    padding: 18px 20px 22px;
    background: linear-gradient(
        to top,
        #212121 75%,
        rgba(33, 33, 33, 0)
    );
}

.composer {
    max-width: 820px;
    margin: 0 auto;
    position: relative;
}

#prompt {
    width: 100%;
    min-height: 54px;
    max-height: 180px;
    resize: none;
    border: 1px solid #444;
    outline: none;
    border-radius: 15px;
    background: #2f2f2f;
    color: #fff;
    padding: 15px 55px 15px 16px;
    font-size: 15px;
    line-height: 1.5;
}

#prompt::placeholder {
    color: #999;
}

#prompt:focus {
    border-color: #555;
}

/* =========================
   زر الإرسال
========================= */

#send {
    position: absolute;
    right: 11px;
    bottom: 11px;

    width: 32px;
    height: 32px;

    border: none;
    border-radius: 10px;

    background: #fff;
    color: #111;

    display: flex;
    align-items: center;
    justify-content: center;

    padding: 0;
    margin: 0;

    font-size: 18px;
    line-height: 1;

    cursor: pointer;
    transition: 0.15s ease;
}

#send:hover {
    transform: scale(1.05);
}

#send:active {
    transform: scale(0.95);
}

#send:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
}

/* =========================
   الرصيد
========================= */

.credits {
    max-width: 820px;
    margin: 7px auto 0;
    text-align: center;
    color: #888;
    font-size: 11px;
}

/* =========================
   الموبايل
========================= */

@media (max-width: 700px) {

    .sidebar {
        display: none;
    }

    .main-chat {
        width: 100%;
    }

    .chat-navbar {
        padding: 0 15px;
    }

    .messages {
        padding: 20px 12px 140px;
    }

    .welcome {
        margin-top: 60px;
    }

    .welcome h1 {
        font-size: 25px;
    }

    .quick-actions {
        grid-template-columns: 1fr;
    }

    .composer-area {
        left: 0;
        padding: 12px 10px 15px;
    }

    #prompt {
        min-height: 50px;
        border-radius: 14px;
        padding-right: 52px;
    }

    #send {
        width: 32px;
        height: 32px;
        right: 9px;
        bottom: 9px;
    }

    .message-content {
        max-width: 92%;
    }
}
