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
    if (desktopSidebarToggle) {
        desktopSidebarToggle.setAttribute("aria-expanded", String(!collapsed));
        desktopSidebarToggle.setAttribute("aria-label", collapsed ? "إظهار القائمة الجانبية" : "إخفاء القائمة الجانبية");
        desktopSidebarToggle.title = collapsed ? "إظهار القائمة الجانبية" : "إخفاء القائمة الجانبية";
    }
    try { localStorage.setItem("zolak-sidebar-collapsed", collapsed ? "1" : "0"); } catch (_) {}
}

if (appShell && window.innerWidth > 800) {
    try { setDesktopSidebarCollapsed(localStorage.getItem("zolak-sidebar-collapsed") === "1"); } catch (_) {}
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
    if (!question) return;
    isSending = true;
    if (homeQuickActions) homeQuickActions.hidden = true;
    addMessage(question, "user");
    promptBox.value = "";
    updateComposerMode();
    sendButton.disabled = true;
    sendButton.innerHTML = '<span class="send-icon">…</span>';
    let liveMessage = null, liveContent = null, streamedText = "", streamError = "", completed = false;
    try {
        const body = {message:question};
        if (currentConversationId !== null) body.conversation_id = currentConversationId;
        const response = await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json","Accept":"text/event-stream"},body:JSON.stringify(body)});
        if (response.status === 401) { window.location.href="/login"; return; }
        if (!response.ok) { const data=await response.json().catch(function(){return {};}); addMessage(data.error || "حصل خطأ، جرّب تاني.","assistant"); await refreshAccount(); return; }
        if (!response.body || !response.body.getReader) throw new Error("المتصفح لا يدعم استقبال الرد المباشر.");
        const reader=response.body.getReader(), decoder=new TextDecoder("utf-8");
        let buffer="", streamFinished=false;
        function handleEvent(rawEvent) {
            const lines=rawEvent.split(/\r?\n/); let eventName="message", payloadText="";
            lines.forEach(function(line){if(line.startsWith("event:"))eventName=line.slice(6).trim();if(line.startsWith("data:"))payloadText+=line.slice(5).trim();});
            if(!payloadText)return; let payload; try{payload=JSON.parse(payloadText);}catch(_){return;}
            if(eventName==="meta"&&payload.conversation_id)currentConversationId=Number(payload.conversation_id);
            else if(eventName==="token"&&payload.text){
                if(!liveMessage){liveMessage=document.createElement("div");liveMessage.className="message assistant";liveContent=document.createElement("div");liveContent.className="message-content streaming-content";liveMessage.appendChild(liveContent);messages.appendChild(liveMessage);}
                streamedText+=payload.text;liveContent.textContent=streamedText;messages.scrollTop=messages.scrollHeight;
            }else if(eventName==="error"){streamError=payload.error||"حصل خطأ أثناء توليد الرد.";streamFinished=true;}
            else if(eventName==="done"){completed=true;streamFinished=true;if(payload.conversation_id)currentConversationId=Number(payload.conversation_id);}
        }
        while(!streamFinished){const result=await reader.read();if(result.done)break;buffer+=decoder.decode(result.value,{stream:true});const events=buffer.split(/\r?\n\r?\n/);buffer=events.pop()||"";for(const eventText of events){handleEvent(eventText);if(streamFinished)break;}}
        if(streamFinished){try{await reader.cancel();}catch(_){}}else{buffer+=decoder.decode();if(buffer.trim())handleEvent(buffer);}
        if(liveMessage)liveMessage.remove();
        if(streamedText)addMessage(streamedText,"assistant");
        if(streamError)addMessage(streamError,"assistant");else if(!completed)addMessage("انقطع الاتصال قبل اكتمال الرد. حاول تاني.","assistant");
        await refreshAccount();
    }catch(error){console.error("خطأ في إرسال الرسالة:",error);if(liveMessage)liveMessage.remove();addMessage("ما قدرنا نكمل الاتصال بالخدمة. تأكد من الإنترنت وحاول تاني.","assistant");}
    finally{isSending=false;sendButton.disabled=false;sendButton.innerHTML='<span class="send-icon">↑</span>';if(promptBox)promptBox.focus();}
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
   ZOLAK SIDEBAR CONTROLLER — minimal, explicit actions
========================================================= */
(function bindZolakSidebarControls() {
    if (!sidebar || sidebar.dataset.controllerBound === "1") return;
    sidebar.dataset.controllerBound = "1";
    sidebar.addEventListener("click", function (event) {
        const target=event.target instanceof Element?event.target:event.target&&event.target.parentElement;
        if(!target)return;
        const newChat=target.closest("#newChat"), exploreButton=target.closest('[data-tool="explore"]'), explorePrompt=target.closest(".explore-prompt[data-explore-prompt]");
        if(!newChat&&!exploreButton&&!explorePrompt)return;
        event.preventDefault();
        if(newChat){if(newChat.disabled)return;newChat.disabled=true;createNewConversation().finally(function(){newChat.disabled=false;});closeSidebar();return;}
        if(exploreButton){const willOpen=Boolean(explorePanel&&explorePanel.hidden);if(explorePanel)explorePanel.hidden=!willOpen;exploreButton.setAttribute("aria-expanded",String(willOpen));return;}
        if(explorePrompt){if(promptBox){promptBox.value=explorePrompt.dataset.explorePrompt||"";promptBox.focus();promptBox.setSelectionRange(promptBox.value.length,promptBox.value.length);updateComposerMode();}if(explorePanel)explorePanel.hidden=true;const button=sidebar.querySelector('[data-tool="explore"]');if(button)button.setAttribute("aria-expanded","false");closeSidebar();}
    },true);
    if(mobileMenu)mobileMenu.addEventListener("click",function(event){event.preventDefault();event.stopPropagation();toggleSidebar();});
    if(desktopSidebarToggle)desktopSidebarToggle.addEventListener("click",function(event){event.preventDefault();event.stopPropagation();if(window.innerWidth>800)setDesktopSidebarCollapsed(!appShell.classList.contains("sidebar-collapsed"));else toggleSidebar();});
})();
