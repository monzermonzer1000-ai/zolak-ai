"use strict";

/* =========================
   ZOLAK AI — APP
========================= */

const promptBox = document.getElementById("prompt");
const sendButton = document.getElementById("send");
const messages = document.getElementById("messages");
const sidebar = document.querySelector(".sidebar");
const mobileMenu = document.querySelector(".mobile-menu");
const appShell = document.querySelector(".app.chatgpt-layout");
const desktopSidebarToggle = document.getElementById("sidebarCollapseButton");
const explorePanel = document.getElementById("explorePanel");

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
let pendingImageAttachment = null;
let lastRequestPayload = null;

/* Attach navigation handlers before the rest of the app initializes. */
bindZolakSidebarControls();

/* =========================
   SIDEBAR
========================= */

/* No full-screen overlay: it can never intercept taps on the drawer. */

function openSidebar() {
    if (!sidebar || window.innerWidth > 800) return;

    sidebar.classList.add("open");

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

/* Outside taps close the drawer without a transparent overlay layer. */
document.addEventListener("click", function (event) {
    if (window.innerWidth > 800 || !sidebar || !sidebar.classList.contains("open")) return;
    if (sidebar.contains(event.target) || (mobileMenu && mobileMenu.contains(event.target))) return;
    closeSidebar();
});


/* HOME HEADER + COMPOSER CONTROLS */
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

function addMessage(text, type, retryPayload = null) {
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
            const copied = await copyZolakText(String(text || ""));
            copyButton.textContent = copied ? "تم النسخ ✓" : "تعذر النسخ";
            window.setTimeout(function () { if (copyButton.isConnected) copyButton.textContent = "نسخ الرد"; }, 1800);
        });
        actions.appendChild(copyButton);
        if (retryPayload) {
            const retryButton = document.createElement("button");
            retryButton.type = "button";
            retryButton.className = "message-retry";
            retryButton.textContent = "إعادة المحاولة";
            retryButton.addEventListener("click", function () {
                if (isSending) return;
                sendMessage(retryPayload);
            });
            actions.appendChild(retryButton);
        }
        content.appendChild(actions);
    } else {
        content.textContent = text;
        const imageAttachment = retryPayload && retryPayload.attachments && retryPayload.attachments.find(function (item) {
            return String(item.mime_type || "").startsWith("image/");
        });
        if (imageAttachment) {
            const image = document.createElement("img");
            image.className = "message-attachment-image";
            image.alt = "الصورة المرفقة";
            image.src = "data:" + imageAttachment.mime_type + ";base64," + imageAttachment.data;
            content.appendChild(image);
        }
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

// Populate login/logout/admin controls as soon as the page is ready.
refreshAccount();

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

async function sendMessage(retryPayload = null) {
    if (!promptBox || !sendButton || !messages || isSending) return;
    const question = retryPayload ? String(retryPayload.message || "").trim() : promptBox.value.trim();
    const attachments = retryPayload ? (retryPayload.attachments || []) : (pendingImageAttachment ? [pendingImageAttachment] : []);
    if (!question && !attachments.length) return;
    const requestPayload = { message: question, attachments: attachments };
    if (retryPayload && retryPayload.conversation_id) requestPayload.conversation_id = retryPayload.conversation_id;
    else if (currentConversationId !== null) requestPayload.conversation_id = currentConversationId;
    lastRequestPayload = { message: question, attachments: attachments.map(function (item) { return Object.assign({}, item); }) };
    isSending = true;

    addMessage(question || "حلّل الصورة المرفقة", "user", requestPayload);
    promptBox.value = "";
    if (!retryPayload) {
        pendingImageAttachment = null;
        renderPendingImage();
    }
    updateComposerMode();
    sendButton.disabled = true;
    sendButton.setAttribute("aria-busy", "true");
    sendButton.innerHTML = '<span class="send-icon">…</span>';
    let liveMessage = null, liveContent = null, typingIndicator = null, streamedText = "", streamError = "", completed = false;
    function removeTypingIndicator() {
        if (typingIndicator) { typingIndicator.remove(); typingIndicator = null; }
    }
    function showTypingIndicator() {
        removeTypingIndicator();
        typingIndicator = document.createElement("div");
        typingIndicator.className = "message assistant typing-message";
        typingIndicator.setAttribute("role", "status");
        typingIndicator.setAttribute("aria-live", "polite");
        typingIndicator.setAttribute("aria-label", "زولك AI يكتب الرد الآن");
        const bubble = document.createElement("div");
        bubble.className = "message-content typing-indicator";
        bubble.innerHTML = '<span class="typing-label">زولك AI يفكر</span><span class="typing-dots" aria-hidden="true"><i></i><i></i><i></i></span>';
        typingIndicator.appendChild(bubble);
        messages.appendChild(typingIndicator);
        messages.scrollTop = messages.scrollHeight;
    }
    showTypingIndicator();
    try {
        const response = await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json","Accept":"text/event-stream"},body:JSON.stringify(requestPayload)});
        if (response.status === 401) { removeTypingIndicator(); window.location.href="/login"; return; }
        if (!response.ok) { removeTypingIndicator(); const data=await response.json().catch(function(){return {};}); addMessage(data.error || "حصل خطأ، جرّب تاني.","assistant"); await refreshAccount(); return; }
        if (!response.body || !response.body.getReader) throw new Error("المتصفح لا يدعم استقبال الرد المباشر.");
        const reader=response.body.getReader(), decoder=new TextDecoder("utf-8");
        let buffer="", streamFinished=false;
        function handleEvent(rawEvent) {
            const lines=rawEvent.split(/\r?\n/); let eventName="message", payloadText="";
            lines.forEach(function(line){if(line.startsWith("event:"))eventName=line.slice(6).trim();if(line.startsWith("data:"))payloadText+=line.slice(5).trim();});
            if(!payloadText)return; let payload; try{payload=JSON.parse(payloadText);}catch(_){return;}
            if(eventName==="meta"&&payload.conversation_id)currentConversationId=Number(payload.conversation_id);
            else if(eventName==="token"&&payload.text){
                if(!liveMessage){removeTypingIndicator();liveMessage=document.createElement("div");liveMessage.className="message assistant streaming-message";liveContent=document.createElement("div");liveContent.className="message-content streaming-content";liveMessage.appendChild(liveContent);messages.appendChild(liveMessage);}
                streamedText+=payload.text;liveContent.textContent=streamedText;messages.scrollTop=messages.scrollHeight;
            }else if(eventName==="error"){streamError=payload.error||"حصل خطأ أثناء توليد الرد.";streamFinished=true;}
            else if(eventName==="done"){completed=true;streamFinished=true;if(payload.conversation_id)currentConversationId=Number(payload.conversation_id);}
        }
        while(!streamFinished){const result=await reader.read();if(result.done)break;buffer+=decoder.decode(result.value,{stream:true});const events=buffer.split(/\r?\n\r?\n/);buffer=events.pop()||"";for(const eventText of events){handleEvent(eventText);if(streamFinished)break;}}
        if(streamFinished){try{await reader.cancel();}catch(_){}}else{buffer+=decoder.decode();if(buffer.trim())handleEvent(buffer);}
        removeTypingIndicator();
        if(liveMessage)liveMessage.remove();
        if(streamedText)addMessage(streamedText,"assistant",requestPayload);
        if(streamError)addMessage(streamError,"assistant",requestPayload);else if(!completed)addMessage("انقطع الاتصال قبل اكتمال الرد. حاول تاني.","assistant");
        await refreshAccount();
    }catch(error){console.error("خطأ في إرسال الرسالة:",error);removeTypingIndicator();if(liveMessage)liveMessage.remove();addMessage("ما قدرنا نكمل الاتصال بالخدمة. تأكد من الإنترنت وحاول تاني.","assistant");}
    finally{removeTypingIndicator();isSending=false;sendButton.disabled=false;sendButton.removeAttribute("aria-busy");sendButton.innerHTML='<span class="send-icon">↑</span>';if(promptBox)promptBox.focus();}
}

async function copyZolakText(value) {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(value);
            return true;
        }
    } catch (_) {}
    const fallback = document.createElement("textarea");
    fallback.value = value;
    fallback.setAttribute("readonly", "");
    fallback.style.position = "fixed";
    fallback.style.opacity = "0";
    document.body.appendChild(fallback);
    fallback.select();
    fallback.setSelectionRange(0, fallback.value.length);
    let copied = false;
    try { copied = document.execCommand("copy"); } catch (_) {}
    fallback.remove();
    return copied;
}

/* Image attachment: resize on-device before sending to the existing Gemini attachment API. */
const imageInput = document.getElementById("imageInput");
const cameraInput = document.getElementById("cameraInput");
const imagePreview = document.getElementById("imagePreview");
const attachImageButton = document.getElementById("attachImageButton");
const cameraButton = document.getElementById("cameraButton");
const removeImageButton = document.getElementById("removeImageButton");
const composerStatus = document.getElementById("composerStatus");

function setComposerStatus(message, isError) {
    if (!composerStatus) return;
    composerStatus.textContent = message || "";
    composerStatus.classList.toggle("is-error", Boolean(isError));
}
function renderPendingImage() {
    if (!imagePreview) return;
    imagePreview.replaceChildren();
    if (!pendingImageAttachment) {
        imagePreview.hidden = true;
        return;
    }
    imagePreview.hidden = false;
    const thumbnail = document.createElement("img");
    thumbnail.className = "pending-image-thumbnail";
    thumbnail.alt = "معاينة الصورة المرفقة";
    thumbnail.src = "data:" + pendingImageAttachment.mime_type + ";base64," + pendingImageAttachment.data;
    const label = document.createElement("span");
    label.textContent = "صورة جاهزة للإرسال: " + pendingImageAttachment.name;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-image";
    remove.textContent = "إزالة";
    remove.setAttribute("aria-label", "إزالة الصورة المرفقة");
    remove.addEventListener("click", function () {
        pendingImageAttachment = null;
        if (imageInput) imageInput.value = "";
        if (cameraInput) cameraInput.value = "";
        renderPendingImage();
        setComposerStatus("");
    });
    imagePreview.append(thumbnail, label, remove);
}
function loadImageForCompression(file) {
    return new Promise(function (resolve, reject) {
        if (window.createImageBitmap) {
            createImageBitmap(file).then(resolve).catch(reject);
            return;
        }
        const url = URL.createObjectURL(file);
        const image = new Image();
        image.onload = function () {
            URL.revokeObjectURL(url);
            resolve(image);
        };
        image.onerror = function () {
            URL.revokeObjectURL(url);
            reject(new Error("تعذر فتح الصورة."));
        };
        image.src = url;
    });
}
async function prepareImageAttachment(file) {
    if (!file || !file.type || !file.type.startsWith("image/")) throw new Error("اختَر ملف صورة صالحاً.");
    if (file.size > 12 * 1024 * 1024) throw new Error("الصورة الأصلية كبيرة جداً. الحد قبل الضغط 12 ميجابايت.");
    const image = await loadImageForCompression(file);
    const originalWidth = image.width || image.naturalWidth;
    const originalHeight = image.height || image.naturalHeight;
    const scale = Math.min(1, 1600 / Math.max(originalWidth, originalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(originalWidth * scale));
    canvas.height = Math.max(1, Math.round(originalHeight * scale));
    const context = canvas.getContext("2d", { alpha: false });
    if (!context) throw new Error("المتصفح لا يدعم تجهيز الصورة.");
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    if (image.close) image.close();
    let blob = await new Promise(function (resolve) { canvas.toBlob(resolve, "image/jpeg", 0.82); });
    if (!blob) throw new Error("تعذر ضغط الصورة.");
    if (blob.size > 2 * 1024 * 1024) {
        blob = await new Promise(function (resolve) { canvas.toBlob(resolve, "image/jpeg", 0.68); });
    }
    if (!blob || blob.size > 2.4 * 1024 * 1024) throw new Error("تعذر تقليل حجم الصورة بما يكفي. جرّب صورة أصغر.");
    const dataUrl = await new Promise(function (resolve, reject) {
        const reader = new FileReader();
        reader.onload = function () { resolve(String(reader.result || "")); };
        reader.onerror = function () { reject(new Error("تعذرت قراءة الصورة.")); };
        reader.readAsDataURL(blob);
    });
    return {
        name: (file.name || "zolak-image").replace(/\.[^.]+$/, "") + ".jpg",
        mime_type: "image/jpeg",
        data: dataUrl.split(",")[1]
    };
}
async function handleImageSelection(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    if (attachImageButton) attachImageButton.disabled = true;
    if (cameraButton) cameraButton.disabled = true;
    setComposerStatus("جارٍ تجهيز الصورة...");
    try {
        pendingImageAttachment = await prepareImageAttachment(file);
        renderPendingImage();
        setComposerStatus("الصورة جاهزة. اكتب سؤالك ثم اضغط إرسال.");
        if (promptBox) promptBox.focus();
    } catch (error) {
        pendingImageAttachment = null;
        renderPendingImage();
        setComposerStatus(error.message || "تعذر تجهيز الصورة.", true);
    } finally {
        if (attachImageButton) attachImageButton.disabled = false;
        if (cameraButton) cameraButton.disabled = false;
        event.target.value = "";
    }
}
if (imageInput) imageInput.addEventListener("change", handleImageSelection);
if (cameraInput) cameraInput.addEventListener("change", handleImageSelection);
if (attachImageButton && imageInput) attachImageButton.addEventListener("click", function () { imageInput.click(); });
if (cameraButton && cameraInput) cameraButton.addEventListener("click", function () { cameraInput.click(); });
if (removeImageButton) removeImageButton.addEventListener("click", function () {
    pendingImageAttachment = null; renderPendingImage(); setComposerStatus("");
});

/* Live voice chat: native Gemini audio-to-audio over a short-lived token. */
const microphoneButton = document.getElementById("microphoneButton");
const voicePanel = document.getElementById("voiceChatPanel");
const voiceStatus = document.getElementById("voiceStatus");
const voiceTranscript = document.getElementById("voiceTranscript");
const voiceEndButton = document.getElementById("voiceEndButton");
const voiceMuteButton = document.getElementById("voiceMuteButton");
const voiceCloseButton = document.getElementById("voiceCloseButton");
let liveVoiceSocket = null;
let liveVoiceStream = null;
let liveVoiceContext = null;
let liveVoiceSource = null;
let liveVoiceProcessor = null;
let liveVoiceActive = false;
let liveVoiceMuted = false;
let liveVoiceSetupReady = false;
let liveVoiceNextPlayTime = 0;
let liveVoiceTurnComplete = false;
let liveVoicePlayingSources = new Set();
let liveVoiceUserText = "";
let liveVoiceAssistantText = "";

function setLiveVoiceStatus(message, state) {
    if (voiceStatus) voiceStatus.textContent = message;
    if (voicePanel) {
        voicePanel.dataset.state = state || "idle";
        voicePanel.querySelector(".voice-orb")?.setAttribute("data-state", state || "idle");
    }
}
function showVoiceTranscript() {
    if (!voiceTranscript) return;
    const parts = [];
    if (liveVoiceUserText) parts.push("أنت: " + liveVoiceUserText);
    if (liveVoiceAssistantText) parts.push("زولك: " + liveVoiceAssistantText);
    voiceTranscript.textContent = parts.join("\n\n");
}
function floatToPcm16Base64(floatSamples) {
    const pcm = new Int16Array(floatSamples.length);
    for (let i = 0; i < floatSamples.length; i++) {
        const sample = Math.max(-1, Math.min(1, floatSamples[i]));
        pcm[i] = sample < 0 ? sample * 32768 : sample * 32767;
    }
    const bytes = new Uint8Array(pcm.buffer);
    let binary = "";
    for (let i = 0; i < bytes.length; i += 0x8000) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, Math.min(i + 0x8000, bytes.length)));
    }
    return btoa(binary);
}
function resampleTo16k(input, inputRate) {
    if (inputRate === 16000) return input;
    const ratio = inputRate / 16000;
    const outputLength = Math.max(1, Math.floor(input.length / ratio));
    const output = new Float32Array(outputLength);
    for (let i = 0; i < outputLength; i++) {
        const position = i * ratio;
        const left = Math.floor(position);
        const right = Math.min(left + 1, input.length - 1);
        const fraction = position - left;
        output[i] = input[left] * (1 - fraction) + input[right] * fraction;
    }
    return output;
}
function playLivePcm(base64Audio) {
    if (!liveVoiceContext || !base64Audio) return;
    const binary = atob(base64Audio);
    const samples = new Int16Array(binary.length / 2);
    for (let i = 0; i < samples.length; i++) {
        const low = binary.charCodeAt(i * 2);
        const high = binary.charCodeAt(i * 2 + 1);
        let value = (high << 8) | low;
        if (value >= 32768) value -= 65536;
        samples[i] = value;
    }
    if (!samples.length) return;
    const audioBuffer = liveVoiceContext.createBuffer(1, samples.length, 24000);
    const channel = audioBuffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 32768;
    const source = liveVoiceContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(liveVoiceContext.destination);
    const startAt = Math.max(liveVoiceContext.currentTime + 0.025, liveVoiceNextPlayTime);
    source.onended = function () {
        liveVoicePlayingSources.delete(source);
        if (liveVoiceTurnComplete && liveVoicePlayingSources.size === 0 && liveVoiceActive) {
            setLiveVoiceStatus("سامعك الآن... اتكلم براحتك", "listening");
        }
    };
    liveVoicePlayingSources.add(source);
    liveVoiceTurnComplete = false;
    source.start(startAt);
    liveVoiceNextPlayTime = startAt + audioBuffer.duration;
    setLiveVoiceStatus("زولك بيتكلم معاك...", "speaking");
}
function stopLivePlayback() {
    liveVoicePlayingSources.forEach(function (source) { try { source.stop(); } catch (_) {} });
    liveVoicePlayingSources.clear();
    if (liveVoiceContext) liveVoiceNextPlayTime = liveVoiceContext.currentTime;
}
function startLiveMicrophone() {
    if (!liveVoiceStream || !liveVoiceContext || !liveVoiceSocket || liveVoiceSocket.readyState !== WebSocket.OPEN) return;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) throw new Error("المتصفح لا يدعم معالجة الصوت المباشر.");
    liveVoiceSource = liveVoiceContext.createMediaStreamSource(liveVoiceStream);
    liveVoiceProcessor = liveVoiceContext.createScriptProcessor(4096, 1, 1);
    liveVoiceProcessor.onaudioprocess = function (event) {
        if (!liveVoiceActive || liveVoiceMuted || liveVoiceSocket?.readyState !== WebSocket.OPEN) return;
        const samples = resampleTo16k(event.inputBuffer.getChannelData(0), liveVoiceContext.sampleRate);
        if (!samples.length) return;
        liveVoiceSocket.send(JSON.stringify({
            realtimeInput: {
                audio: {
                    data: floatToPcm16Base64(samples),
                    mimeType: "audio/pcm;rate=16000"
                }
            }
        }));
    };
    liveVoiceSource.connect(liveVoiceProcessor);
    liveVoiceProcessor.connect(liveVoiceContext.destination);
}
function cleanupLiveVoice(closePanel) {
    liveVoiceActive = false;
    liveVoiceSetupReady = false;
    if (liveVoiceProcessor) {
        liveVoiceProcessor.onaudioprocess = null;
        try { liveVoiceProcessor.disconnect(); } catch (_) {}
        liveVoiceProcessor = null;
    }
    if (liveVoiceSource) {
        try { liveVoiceSource.disconnect(); } catch (_) {}
        liveVoiceSource = null;
    }
    if (liveVoiceStream) {
        liveVoiceStream.getTracks().forEach(function (track) { track.stop(); });
        liveVoiceStream = null;
    }
    if (liveVoiceSocket) {
        const socket = liveVoiceSocket;
        liveVoiceSocket = null;
        try { socket.close(1000, "User ended voice chat"); } catch (_) {}
    }
    if (liveVoiceContext) {
        const context = liveVoiceContext;
        liveVoiceContext = null;
        try { context.close(); } catch (_) {}
    }
    stopLivePlayback();
    liveVoiceNextPlayTime = 0;
    liveVoiceTurnComplete = false;
    liveVoiceMuted = false;
    if (voiceMuteButton) {
        voiceMuteButton.textContent = "كتم الميكروفون";
        voiceMuteButton.setAttribute("aria-pressed", "false");
    }
    if (microphoneButton) {
        microphoneButton.disabled = false;
        microphoneButton.classList.remove("is-live");
        microphoneButton.setAttribute("aria-pressed", "false");
    }
    if (closePanel && voicePanel) voicePanel.hidden = true;
}
function endLiveVoiceChat() {
    cleanupLiveVoice(true);
    setComposerStatus("");
}
function appendVoiceText(target, text) {
    if (!text) return;
    if (target === "user") liveVoiceUserText += text;
    else liveVoiceAssistantText += text;
    showVoiceTranscript();
}
async function startLiveVoiceChat() {
    if (liveVoiceActive) { endLiveVoiceChat(); return; }
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.WebSocket) {
        setComposerStatus("الدردشة الصوتية تحتاج متصفحاً حديثاً واتصال HTTPS مع دعم الميكروفون.", true);
        return;
    }
    if (!voicePanel) {
        setComposerStatus("واجهة الدردشة الصوتية غير متاحة في هذه النسخة.", true);
        return;
    }

    liveVoiceActive = true;
    liveVoiceUserText = "";
    liveVoiceAssistantText = "";
    liveVoiceNextPlayTime = 0;
    if (voiceTranscript) voiceTranscript.textContent = "";
    voicePanel.hidden = false;
    setLiveVoiceStatus("جارٍ تجهيز الاتصال الصوتي...", "connecting");
    if (microphoneButton) {
        microphoneButton.disabled = true;
        microphoneButton.classList.add("is-live");
        microphoneButton.setAttribute("aria-pressed", "true");
    }

    try {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        liveVoiceContext = new AudioContextClass();
        await liveVoiceContext.resume();

        const tokenResponse = await fetch("/api/live-token", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ conversation_id: currentConversationId })
        });
        if (tokenResponse.status === 401) {
            cleanupLiveVoice(true);
            window.location.href = "/login";
            return;
        }
        const tokenData = await tokenResponse.json().catch(function () { return {}; });
        if (!tokenResponse.ok || !tokenData.token) {
            throw new Error(tokenData.error || "تعذر بدء الدردشة الصوتية.");
        }

        const modelName = String(tokenData.model || "gemini-3.8-live").replace(/^models\//, "");
        const socketUrl = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained?access_token=" + encodeURIComponent(tokenData.token);
        liveVoiceSocket = new WebSocket(socketUrl);

        liveVoiceSocket.onopen = function () {
            if (!liveVoiceActive || !liveVoiceSocket) return;
            liveVoiceSocket.send(JSON.stringify({
                setup: {
                    model: "models/" + modelName,
                    generationConfig: {
                        responseModalities: ["AUDIO"],
                        speechConfig: {
                            languageCode: "ar",
                            voiceConfig: { prebuiltVoiceConfig: { voiceName: "Kore" } }
                        },
                        inputAudioTranscription: {},
                        outputAudioTranscription: {}
                    },
                    systemInstruction: {
                        parts: [{ text: tokenData.system_instruction || "أنت زولك AI، مساعد سوداني. تحدث بالعربية بوضوح وبلهجة سودانية طبيعية عند ملاءمتها. أجب بصوت طبيعي ومباشر، استمع جيداً ولا تخترع معلومات." }]
                    },
                    realtimeInputConfig: {
                        automaticActivityDetection: {
                            disabled: false,
                            silenceDurationMs: 800
                        }
                    }
                }
            }));
            setLiveVoiceStatus("تم الاتصال. بنجهز الميكروفون...", "connecting");
        };

        liveVoiceSocket.onmessage = async function (event) {
            let packet;
            try { packet = JSON.parse(event.data); } catch (_) { return; }
            if (packet.setupComplete) {
                liveVoiceSetupReady = true;
                try {
                    liveVoiceStream = await navigator.mediaDevices.getUserMedia({
                        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
                    });
                    if (!liveVoiceActive) return;
                    startLiveMicrophone();
                    setLiveVoiceStatus("سامعك الآن... اتكلم براحتك", "listening");
                } catch (error) {
                    const denied = error && (error.name === "NotAllowedError" || error.name === "PermissionDeniedError");
                    setLiveVoiceStatus(denied
                        ? "إذن الميكروفون مرفوض. اسمح لزولك AI باستخدام الميكروفون من إعدادات الموقع."
                        : "ما قدرنا نفتح الميكروفون. تأكد أنه غير مستخدم بواسطة تطبيق آخر.", "error");
                    cleanupLiveVoice(false);
                }
                return;
            }
            if (packet.error) {
                const detail = packet.error.message || "خدمة الصوت أرسلت خطأ.";
                setLiveVoiceStatus(detail, "error");
                cleanupLiveVoice(false);
                return;
            }
            const content = packet.serverContent;
            if (!content) return;
            if (content.interrupted) {
                stopLivePlayback();
                setLiveVoiceStatus("سامعك الآن...", "listening");
            }
            if (content.inputTranscription?.text) {
                appendVoiceText("user", content.inputTranscription.text);
                setLiveVoiceStatus("وصل كلامك لزولك...", "thinking");
            }
            if (content.outputTranscription?.text) {
                appendVoiceText("assistant", content.outputTranscription.text);
                setLiveVoiceStatus("زولك بيتكلم معاك...", "speaking");
            }
            const parts = content.modelTurn?.parts || [];
            for (const part of parts) {
                const audioData = part.inlineData?.data || part.inline_data?.data;
                if (audioData) playLivePcm(audioData);
            }
            if (content.turnComplete) {
                liveVoiceTurnComplete = true;
                if (!content.outputTranscription?.text && liveVoiceAssistantText) showVoiceTranscript();
                if (liveVoicePlayingSources.size === 0) {
                    setLiveVoiceStatus("سامعك الآن... اتكلم براحتك", "listening");
                }
            }
        };
        liveVoiceSocket.onerror = function () {
            if (!liveVoiceActive) return;
            setLiveVoiceStatus("حصلت مشكلة في اتصال الصوت. تحقق من الإنترنت وحاول مرة أخرى.", "error");
            cleanupLiveVoice(false);
        };
        liveVoiceSocket.onclose = function (event) {
            if (!liveVoiceActive) return;
            const message = event.code === 1008
                ? "انتهت صلاحية جلسة الصوت. اضغط زر البدء وحاول مجدداً."
                : "انقطع اتصال الدردشة الصوتية. تحقق من الإنترنت وحاول مجدداً.";
            setLiveVoiceStatus(message, "error");
            cleanupLiveVoice(false);
        };
    } catch (error) {
        console.error("Live voice chat error:", error);
        setLiveVoiceStatus(error.message || "تعذر تشغيل الدردشة الصوتية.", "error");
        cleanupLiveVoice(false);
    }
}
if (microphoneButton) microphoneButton.addEventListener("click", startLiveVoiceChat);
if (voiceEndButton) voiceEndButton.addEventListener("click", endLiveVoiceChat);
if (voiceCloseButton) voiceCloseButton.addEventListener("click", endLiveVoiceChat);
if (voiceMuteButton) voiceMuteButton.addEventListener("click", function () {
    if (!liveVoiceActive) return;
    liveVoiceMuted = !liveVoiceMuted;
    voiceMuteButton.textContent = liveVoiceMuted ? "تشغيل الميكروفون" : "كتم الميكروفون";
    voiceMuteButton.setAttribute("aria-pressed", String(liveVoiceMuted));
    setLiveVoiceStatus(liveVoiceMuted ? "الميكروفون مكتوم. اضغط تشغيل الميكروفون للمتابعة." : "سامعك الآن... اتكلم براحتك", liveVoiceMuted ? "muted" : "listening");
});

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
   SIDEBAR CONTROLS — named handlers + direct click bindings
========================================================= */
function handleNewChatClick(event) {
    event.preventDefault();
    const button = event.currentTarget;
    if (button.disabled) return;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    createNewConversation().finally(function () {
        button.disabled = false;
        button.removeAttribute("aria-busy");
    });
}

async function handleClearHistoryClick(event) {
    event.preventDefault();
    const button = event.currentTarget;
    if (button.disabled) return;
    if (!window.confirm("متأكد داير تحذف كل محادثاتك؟ الحذف نهائي وما ممكن التراجع عنه.")) return;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    try {
        const listResponse = await fetch("/api/conversations", { credentials: "same-origin" });
        if (listResponse.status === 401) {
            window.location.href = "/login";
            return;
        }
        if (!listResponse.ok) throw new Error("تعذر تحميل سجل المحادثات");
        const data = await listResponse.json();
        const conversations = Array.isArray(data.conversations) ? data.conversations : [];
        for (const conversation of conversations) {
            const response = await fetch("/api/conversations/" + encodeURIComponent(conversation.id), {
                method: "DELETE",
                credentials: "same-origin"
            });
            if (response.status === 401) {
                window.location.href = "/login";
                return;
            }
            if (!response.ok) throw new Error("تعذر حذف إحدى المحادثات");
        }
        currentConversationId = null;
        showWelcome(false);
        addMessage(conversations.length ? "تم حذف سجل المحادثات بالكامل." : "ما عندك محادثات محفوظة للحذف.", "assistant");
        closeSidebar();
    } catch (error) {
        console.error("تعذر مسح سجل المحادثات:", error);
        addMessage("ما قدرنا نمسح كل المحادثات. حاول تاني.", "assistant");
    } finally {
        button.disabled = false;
        button.removeAttribute("aria-busy");
    }
}

function applyZolakTheme(theme) {
    const dark = theme === "dark";
    document.body.classList.toggle("theme-dark", dark);
    document.body.classList.toggle("theme-light", !dark);
    const button = document.getElementById("themeToggleButton");
    if (button) {
        button.setAttribute("aria-pressed", String(dark));
        const label = button.querySelector("[data-theme-label]");
        if (label) label.textContent = dark ? "الوضع الفاتح" : "الوضع الليلي";
    }
    const themeMeta = document.querySelector('meta[name="theme-color"]');
    if (themeMeta) themeMeta.setAttribute("content", dark ? "#111827" : "#ffffff");
    try { localStorage.setItem("zolak-theme", dark ? "dark" : "light"); } catch (_) {}
}

function handleThemeToggleClick(event) {
    event.preventDefault();
    applyZolakTheme(document.body.classList.contains("theme-dark") ? "light" : "dark");
}

function handleExploreClick(event) {
    event.preventDefault();
    const button = event.currentTarget;
    const panel = document.getElementById("explorePanel");
    const willOpen = Boolean(panel && panel.hidden);
    if (panel) panel.hidden = !willOpen;
    button.setAttribute("aria-expanded", String(willOpen));
}

function handleExplorePromptClick(event) {
    event.preventDefault();
    const button = event.currentTarget;
    const panel = document.getElementById("explorePanel");
    if (promptBox) {
        promptBox.value = button.dataset.explorePrompt || "";
        promptBox.focus();
        promptBox.setSelectionRange(promptBox.value.length, promptBox.value.length);
        updateComposerMode();
    }
    if (panel) panel.hidden = true;
    const exploreButton = document.querySelector('.sidebar [data-tool="explore"]');
    if (exploreButton) exploreButton.setAttribute("aria-expanded", "false");
    closeSidebar();
}

function handleMobileMenuClick(event) {
    event.preventDefault();
    event.stopPropagation();
    toggleSidebar();
}

function handleDesktopSidebarToggleClick(event) {
    event.preventDefault();
    event.stopPropagation();
    if (window.innerWidth > 800) {
        setDesktopSidebarCollapsed(!appShell.classList.contains("sidebar-collapsed"));
    } else {
        toggleSidebar();
    }
}

function bindZolakSidebarControls() {
    const sidebarElement = document.getElementById("appSidebar");
    if (!sidebarElement || sidebarElement.dataset.zolakEventsBound === "1") return;
    sidebarElement.dataset.zolakEventsBound = "1";

    const bindings = [
        [document.getElementById("newChat"), handleNewChatClick],
        [document.getElementById("clearHistoryButton"), handleClearHistoryClick],
        [document.getElementById("themeToggleButton"), handleThemeToggleClick],
        [sidebarElement.querySelector('[data-tool="explore"]'), handleExploreClick],
        [document.getElementById("mobileMenu"), handleMobileMenuClick],
        [document.getElementById("sidebarCollapseButton"), handleDesktopSidebarToggleClick]
    ];
    bindings.forEach(function (binding) {
        const element = binding[0];
        if (element && element.dataset.zolakClickBound !== "1") {
            element.addEventListener("click", binding[1], { passive: false });
            element.dataset.zolakClickBound = "1";
        }
    });

    sidebarElement.querySelectorAll(".explore-prompt[data-explore-prompt]").forEach(function (button) {
        if (button.dataset.zolakClickBound === "1") return;
        button.addEventListener("click", handleExplorePromptClick, { passive: false });
        button.dataset.zolakClickBound = "1";
    });

    sidebarElement.querySelectorAll("a").forEach(function (link) {
        if (link.dataset.zolakClickBound === "1") return;
        link.addEventListener("click", function () {
            if (window.innerWidth <= 800) closeSidebar();
        });
        link.dataset.zolakClickBound = "1";
    });

    let savedTheme = "light";
    try { savedTheme = localStorage.getItem("zolak-theme") === "dark" ? "dark" : "light"; } catch (_) {}
    applyZolakTheme(savedTheme);
}
