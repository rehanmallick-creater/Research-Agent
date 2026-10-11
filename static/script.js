// script.js - makes the page work.
// Flow: user clicks Research -> we call the backend -> backend sends progress
//       messages -> we update the agent cards -> finally we show the report.


// ---------- 1. Grab the page elements we need ----------
const form           = document.getElementById("search-form");
const topicInput     = document.getElementById("topic-input");
const searchButton   = document.getElementById("search-button");
const agentsSection  = document.getElementById("agents");
const errorBox       = document.getElementById("error-box");
const resultsSection = document.getElementById("results");
const resultContent  = document.getElementById("result-content");

// Here we remember the text of each tab
const results = { report: "", feedback: "", search: "", scraped: "" };
let currentTab = "report";


// ---------- 2. Example chips: clicking one fills the search box ----------
document.querySelectorAll(".chip").forEach(function (chip) {
  chip.addEventListener("click", function () {
    topicInput.value = chip.textContent;
    topicInput.focus();
  });
});


// ---------- 3. Update one agent card ("waiting", "working" or "done") ----------
function setAgent(number, state) {
  const card   = document.getElementById("agent-" + number);
  const status = card.querySelector(".agent-status");

  card.classList.remove("working", "done");

  if (state === "working") {
    card.classList.add("working");
    status.textContent = "Working...";
  } else if (state === "done") {
    card.classList.add("done");
    status.textContent = "Done ✓";
  } else {
    status.textContent = "Waiting";
  }
}


// ---------- 4. Show the text of the selected tab ----------
function showTab() {
  const text = results[currentTab] || "Nothing here yet.";

  if (currentTab === "report" || currentTab === "feedback") {
    // Report and feedback are markdown: convert to HTML, then clean it for safety
    resultContent.innerHTML = DOMPurify.sanitize(marked.parse(text));
    // Make every link open in a new tab
    resultContent.querySelectorAll("a").forEach(function (link) {
      link.target = "_blank";
    });
  } else {
    // Raw agent output is shown as plain text
    resultContent.innerHTML = "<pre></pre>";
    resultContent.querySelector("pre").textContent = text;
  }
}

// Tab buttons
document.querySelectorAll(".tab").forEach(function (button) {
  button.addEventListener("click", function () {
    document.querySelectorAll(".tab").forEach(function (b) { b.classList.remove("active"); });
    button.classList.add("active");
    currentTab = button.dataset.tab;
    showTab();
  });
});


// ---------- 5. Handle one message from the backend ----------
function handleMessage(msg) {
  if (msg.event === "step") {
    // Example: { event: "step", step: 1, status: "running" }
    setAgent(msg.step, msg.status === "running" ? "working" : "done");

    if (msg.status === "done") {
      if (msg.step === 1) results.search   = msg.output;
      if (msg.step === 2) results.scraped  = msg.output;
      if (msg.step === 3) {
        results.report = msg.output;       // show the report as soon as it is written
        resultsSection.classList.remove("hidden");
        showTab();
      }
      if (msg.step === 4) results.feedback = msg.output;
    }
  }

  if (msg.event === "finished") {
    results.report   = msg.report;
    results.feedback = msg.feedback;
    showTab();
  }

  if (msg.event === "error") {
    showError(msg.message);
  }
  // "ping" messages are ignored: they only keep the connection alive
}

function showError(text) {
  errorBox.textContent = "Something went wrong: " + text;
  errorBox.classList.remove("hidden");
}


// ---------- 6. When the user clicks "Research" ----------
form.addEventListener("submit", async function (event) {
  event.preventDefault();                 // stop the page from reloading

  // Reset the screen
  errorBox.classList.add("hidden");
  resultsSection.classList.add("hidden");
  agentsSection.classList.remove("hidden");
  for (let i = 1; i <= 4; i++) setAgent(i, "waiting");
  searchButton.disabled = true;
  searchButton.textContent = "Working...";

  try {
    // Ask the backend to start
    const response = await fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic: topicInput.value.trim() }),
    });

    if (!response.ok) throw new Error("Server error " + response.status);

    // Read the answer piece by piece while it arrives.
    // Each message is one line of JSON, so we split on "\n".
    const reader  = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();               // last piece may be half-received: keep it

      lines.forEach(function (line) {
        if (line.trim()) handleMessage(JSON.parse(line));
      });
    }
  } catch (error) {
    showError(error.message);
  }

  searchButton.disabled = false;
  searchButton.textContent = "Research";
});


// ---------- 7. Copy and Download buttons ----------
document.getElementById("copy-button").addEventListener("click", async function () {
  await navigator.clipboard.writeText(results[currentTab]);
  this.textContent = "Copied ✓";
  setTimeout(() => { this.textContent = "Copy"; }, 1200);
});

document.getElementById("download-button").addEventListener("click", function () {
  const file = new Blob([results[currentTab]], { type: "text/markdown" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(file);
  link.download = currentTab + ".md";
  link.click();
});