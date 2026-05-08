// m3 demo frontend: submit a job, poll status, render the markdown payload.
//
// Intentionally vanilla — no build step, no framework. Clara owns visual /
// copy polish post-launch; this file's job is to exercise the API end to end.

(() => {
  const POLL_INTERVAL_MS = 2500;
  // Hard ceiling on how long the page will keep polling. The OBRA-74 plan
  // budgets ~10 minutes for a 30-min episode end-to-end; 12 minutes gives
  // us a small safety margin before we stop and tell the user.
  const POLL_BUDGET_MS = 12 * 60 * 1000;

  const TERMINAL_STATUSES = new Set(["complete", "failed"]);

  const form = document.getElementById("demo-form");
  const submitButton = document.getElementById("submit");
  const statusBox = document.getElementById("status");
  const resultBox = document.getElementById("result");
  const resultMeta = document.getElementById("result-meta");
  const resultFiles = document.getElementById("result-files");

  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showStatus("Submitting…", { error: false });
    hideResult();
    submitButton.disabled = true;

    const formData = new FormData(form);
    let response;
    try {
      response = await fetch("/jobs", { method: "POST", body: formData });
    } catch (err) {
      showStatus("Network error. Please try again.", { error: true });
      submitButton.disabled = false;
      return;
    }

    let body;
    try {
      body = await response.json();
    } catch (_err) {
      body = null;
    }

    if (response.status === 503) {
      showStatus(
        body?.detail ||
          "The demo is paused for maintenance. We saved your email.",
        { error: true },
      );
      submitButton.disabled = false;
      return;
    }

    if (!response.ok) {
      const detail = body?.detail;
      const message =
        (detail && (detail.message || detail)) ||
        "Submission failed. Please check the URL and try again.";
      showStatus(typeof message === "string" ? message : JSON.stringify(message), {
        error: true,
      });
      submitButton.disabled = false;
      return;
    }

    if (!body?.job_id) {
      showStatus("Server didn't return a job id. Please refresh and retry.", {
        error: true,
      });
      submitButton.disabled = false;
      return;
    }

    showStatus("Queued. Working on it — this can take several minutes.", {
      error: false,
    });
    pollJob(body.job_id);
  });

  async function pollJob(jobId) {
    const start = Date.now();

    while (Date.now() - start < POLL_BUDGET_MS) {
      let response;
      try {
        response = await fetch(`/jobs/${encodeURIComponent(jobId)}`);
      } catch (_err) {
        await sleep(POLL_INTERVAL_MS);
        continue;
      }

      if (!response.ok) {
        showStatus("Lost track of that job. Please retry.", { error: true });
        submitButton.disabled = false;
        return;
      }

      const data = await response.json();
      updateStatusFromJob(data);

      if (TERMINAL_STATUSES.has(data.status)) {
        if (data.status === "complete") {
          renderPayload(data.payload);
        } else {
          showStatus(
            data.error_message || "Job failed. Please try a different URL.",
            { error: true },
          );
        }
        submitButton.disabled = false;
        return;
      }

      await sleep(POLL_INTERVAL_MS);
    }

    showStatus(
      "Still working… you can refresh this page later or try the CLI for now.",
      { error: false },
    );
    submitButton.disabled = false;
  }

  function updateStatusFromJob(job) {
    const messages = {
      queued: "Queued.",
      running: "Working on it — this can take several minutes.",
    };
    const text = messages[job.status] || `Status: ${job.status}`;
    showStatus(text, { error: false });
  }

  function renderPayload(payload) {
    if (!payload || !payload.files?.length) {
      showStatus("Job finished but no notes came back.", { error: true });
      return;
    }

    statusBox.hidden = true;
    statusBox.textContent = "";

    resultMeta.innerHTML = "";
    const heading = document.createElement("h2");
    heading.textContent = payload.episode_title || "Generated notes";
    resultMeta.appendChild(heading);

    if (payload.podcast_name) {
      const sub = document.createElement("p");
      sub.className = "fineprint";
      sub.textContent = payload.podcast_name;
      resultMeta.appendChild(sub);
    }

    resultFiles.innerHTML = "";
    for (const file of payload.files) {
      const wrapper = document.createElement("section");
      wrapper.className = "note";

      const title = document.createElement("h3");
      title.textContent = file.title || file.template;
      wrapper.appendChild(title);

      const pre = document.createElement("pre");
      pre.textContent = file.markdown;
      wrapper.appendChild(pre);

      resultFiles.appendChild(wrapper);
    }

    resultBox.hidden = false;
  }

  function showStatus(text, { error }) {
    statusBox.hidden = false;
    statusBox.textContent = text;
    statusBox.classList.toggle("error", !!error);
  }

  function hideResult() {
    resultBox.hidden = true;
    resultMeta.innerHTML = "";
    resultFiles.innerHTML = "";
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
})();
