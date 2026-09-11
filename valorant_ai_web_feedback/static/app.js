const input = document.getElementById("videoInput");
const fileName = document.getElementById("fileName");
const video = document.getElementById("videoPlayer");
const analyzeBtn = document.getElementById("analyzeBtn");
const statusBox = document.getElementById("status");
const results = document.getElementById("results");

let selectedFile = null;
let currentAnalysis = null;
let selectedOverallRating = null;

input.addEventListener("change", () => {
    selectedFile = input.files[0];
    if (!selectedFile) return;

    fileName.textContent =
        `${selectedFile.name} · ${(selectedFile.size / 1024 / 1024).toFixed(1)} MB`;

    video.src = URL.createObjectURL(selectedFile);
    video.style.display = "block";
    analyzeBtn.disabled = false;
    results.classList.add("hidden");
});

function timestampToSeconds(ts) {
    const p = ts.split(":").map(Number);
    if (p.length === 2) return p[0] * 60 + p[1];
    if (p.length === 3) return p[0] * 3600 + p[1] * 60 + p[2];
    return 0;
}

async function sendFeedback(payload) {
    const r = await fetch("/feedback", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });

    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "피드백 저장 실패");
    return data;
}

function renderScores(scores) {
    const labels = {
        aim: "Aim",
        movement: "Movement",
        positioning: "Positioning",
        utility: "Utility",
        decision_making: "Decision Making"
    };

    const root = document.getElementById("scoreBars");
    root.innerHTML = "";

    for (const [key, label] of Object.entries(labels)) {
        const value = scores[key] || 0;
        const row = document.createElement("div");
        row.className = "score-row";

        const name = document.createElement("div");
        name.textContent = label;

        const bar = document.createElement("div");
        bar.className = "bar";
        const fill = document.createElement("div");
        fill.style.width = `${value}%`;
        bar.appendChild(fill);

        const score = document.createElement("div");
        score.textContent = value;

        row.append(name, bar, score);
        root.appendChild(row);
    }
}

function renderEvents(events) {
    const root = document.getElementById("events");
    root.innerHTML = "";

    events.forEach((event, index) => {
        const box = document.createElement("div");
        box.className = "event";

        const head = document.createElement("div");
        head.className = "event-head";

        const ts = document.createElement("button");
        ts.className = "timestamp";
        ts.textContent = event.timestamp;
        ts.onclick = () => {
            video.currentTime = timestampToSeconds(event.timestamp);
            video.play();
            video.scrollIntoView({behavior: "smooth", block: "center"});
        };

        for (const text of [
            event.category,
            event.severity,
            `confidence ${Math.round(event.confidence * 100)}%`
        ]) {
            const badge = document.createElement("span");
            badge.className = "badge";
            badge.textContent = text;
            head.appendChild(badge);
        }

        head.prepend(ts);

        const observation = document.createElement("p");
        observation.textContent = `관찰: ${event.observation}`;

        const feedback = document.createElement("p");
        feedback.textContent = `피드백: ${event.feedback}`;

        const vote = document.createElement("div");
        vote.className = "event-feedback";

        const label = document.createElement("span");
        label.className = "muted";
        label.textContent = "이 피드백은 정확했나요?";

        const up = document.createElement("button");
        up.textContent = "👍 맞음";

        const down = document.createElement("button");
        down.textContent = "👎 틀림";

        const msg = document.createElement("span");
        msg.className = "muted";

        async function submit(rating, selectedButton) {
            try {
                await sendFeedback({
                    analysis_id: currentAnalysis.analysis_id,
                    target_type: "event",
                    event_index: index,
                    event_timestamp: event.timestamp,
                    event_category: event.category,
                    rating,
                    categories: [event.category],
                    comment: ""
                });

                up.classList.remove("selected");
                down.classList.remove("selected");
                selectedButton.classList.add("selected");
                msg.textContent = "저장됨";
            } catch (e) {
                msg.textContent = e.message;
            }
        }

        up.onclick = () => submit("up", up);
        down.onclick = () => submit("down", down);

        vote.append(label, up, down, msg);
        box.append(head, observation, feedback, vote);
        root.appendChild(box);
    });
}

function renderResult(data) {
    currentAnalysis = data;

    document.getElementById("overallScore").textContent = data.overall_score;
    document.getElementById("summary").textContent = data.summary;

    renderScores(data.scores);
    renderEvents(data.events || []);

    const priorities = document.getElementById("priorities");
    priorities.innerHTML = "";
    for (const p of data.top_priorities || []) {
        const li = document.createElement("li");
        li.textContent = p;
        priorities.appendChild(li);
    }

    const limitations = document.getElementById("limitations");
    limitations.innerHTML = "";
    for (const p of data.limitations || []) {
        const li = document.createElement("li");
        li.textContent = p;
        limitations.appendChild(li);
    }

    results.classList.remove("hidden");
}

analyzeBtn.onclick = async () => {
    if (!selectedFile) return;

    analyzeBtn.disabled = true;
    statusBox.textContent = "영상 업로드 및 AI 분석 중...";

    const form = new FormData();
    form.append("file", selectedFile);

    try {
        const r = await fetch("/analyze", {method: "POST", body: form});
        const data = await r.json();

        if (!r.ok) throw new Error(data.detail || "분석 실패");

        renderResult(data);
        statusBox.textContent = `분석 완료 · ${data.model_used || "Gemini"}`;
    } catch (e) {
        statusBox.textContent = `오류: ${e.message}`;
    } finally {
        analyzeBtn.disabled = false;
    }
};

document.querySelectorAll(".feedback-choice").forEach(button => {
    button.onclick = () => {
        selectedOverallRating = button.dataset.rating;

        document.querySelectorAll(".feedback-choice")
            .forEach(b => b.classList.remove("selected"));

        button.classList.add("selected");
        document.getElementById("submitOverallFeedback").disabled = false;
    };
});

document.getElementById("submitOverallFeedback").onclick = async () => {
    const checked = Array.from(
        document.querySelectorAll(".categories input:checked")
    ).map(x => x.value);

    const status = document.getElementById("overallFeedbackStatus");

    try {
        await sendFeedback({
            analysis_id: currentAnalysis.analysis_id,
            target_type: "overall",
            event_index: null,
            event_timestamp: null,
            event_category: null,
            rating: selectedOverallRating,
            categories: checked,
            comment: document.getElementById("overallComment").value.trim()
        });

        status.textContent = "피드백이 저장되었습니다.";
    } catch (e) {
        status.textContent = `오류: ${e.message}`;
    }
};
