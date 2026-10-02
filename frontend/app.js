document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("checkForm");
  const submitBtn = document.getElementById("submitBtn");
  const errorAlert = document.getElementById("errorAlert");
  const resultCard = document.getElementById("resultCard");
  const resetBtn = document.getElementById("resetBtn");

  const verdictBadge = document.getElementById("verdictBadge");
  const riskScoreValue = document.getElementById("riskScoreValue");
  const resultSummary = document.getElementById("resultSummary");
  const brandStatusText = document.getElementById("brandStatusText");
  const reasonsList = document.getElementById("reasonsList");
  const adviceList = document.getElementById("adviceList");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorAlert.classList.add("hidden");
    errorAlert.textContent = "";

    const brand = document.getElementById("claimedBrand").value.trim();
    const phone = document.getElementById("phoneNumber").value.trim();
    const message = document.getElementById("messageText").value.trim();
    const url = document.getElementById("url").value.trim();
    const upi = document.getElementById("upiId").value.trim();
    const displayName = document.getElementById("displayName").value.trim();

    if (!phone && !message && !url && !upi) {
      errorAlert.textContent = "Please provide at least one input: Phone number, Message text, Link, or UPI ID.";
      errorAlert.classList.remove("hidden");
      return;
    }

    const payload = {
      claimed_brand: brand || null,
      phone_number: phone || null,
      message_text: message || null,
      urls: url ? [url] : [],
      payment: (upi || displayName) ? {
        upi_id: upi || null,
        display_name: displayName || null
      } : null,
      language: "en"
    };

    submitBtn.disabled = true;
    submitBtn.innerHTML = "<span>Analyzing Seller Details...</span>";

    try {
      const res = await fetch("/v1/checks", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Verification request failed.");
      }

      displayResult(data);
    } catch (err) {
      errorAlert.textContent = err.message || "An error occurred while checking. Please try again.";
      errorAlert.classList.remove("hidden");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = "<span>Verify Seller Details</span>";
    }
  });

  function displayResult(data) {
    form.classList.add("hidden");
    resultCard.classList.remove("hidden");

    // Verdict Badge styling
    verdictBadge.className = "verdict-badge";
    let icon = "🛡️";
    let verdictLabel = data.verdict;

    if (data.verdict === "MATCHES_OFFICIAL") {
      verdictBadge.classList.add("verdict-matches-official");
      icon = "✅";
      verdictLabel = "MATCHES OFFICIAL";
    } else if (data.verdict === "LIKELY_SCAM") {
      verdictBadge.classList.add("verdict-likely-scam");
      icon = "🚨";
      verdictLabel = "LIKELY SCAM";
    } else if (data.verdict === "SUSPICIOUS") {
      verdictBadge.classList.add("verdict-suspicious");
      icon = "⚠️";
      verdictLabel = "SUSPICIOUS";
    } else {
      verdictBadge.classList.add("verdict-unverified");
      icon = "❓";
      verdictLabel = "UNVERIFIED";
    }

    verdictBadge.textContent = `${icon} ${verdictLabel}`;
    riskScoreValue.textContent = data.risk_score !== null ? `${Math.round(data.risk_score * 100)}%` : "N/A";
    resultSummary.textContent = data.summary;

    // Brand Status
    if (data.brand && data.brand.claimed) {
      if (data.brand.in_registry) {
        brandStatusText.textContent = `Claimed '${data.brand.claimed}' (Found in official registry)`;
      } else {
        brandStatusText.textContent = `Claimed '${data.brand.claimed}' (NOT in official registry)`;
      }
    } else {
      brandStatusText.textContent = "No specific brand claimed or detected.";
    }

    // Reasons list
    reasonsList.innerHTML = "";
    if (data.reasons && data.reasons.length > 0) {
      data.reasons.forEach(r => {
        const li = document.createElement("li");
        li.textContent = r.text;
        reasonsList.appendChild(li);
      });
    } else {
      const li = document.createElement("li");
      li.textContent = "No specific red flags or channel matches identified.";
      reasonsList.appendChild(li);
    }

    // Advice list
    adviceList.innerHTML = "";
    if (data.advice && data.advice.length > 0) {
      data.advice.forEach(a => {
        const li = document.createElement("li");
        li.textContent = a;
        adviceList.appendChild(li);
      });
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  resetBtn.addEventListener("click", () => {
    resultCard.classList.add("hidden");
    form.classList.remove("hidden");
    form.reset();
  });
});
