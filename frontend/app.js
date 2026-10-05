document.addEventListener("DOMContentLoaded", () => {
  // PWA Service Worker Registration
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").then(
        (reg) => console.log("TrustShop ServiceWorker registered:", reg.scope),
        (err) => console.log("ServiceWorker registration failed:", err)
      );
    });
  }

  // UI Localized Strings
  const UI_TEXT = {
    en: {
      tagline: "Check before you pay",
      heroTitle: "Is this seller legitimate?",
      heroDesc: "Paste the phone number, WhatsApp chat, link, or payment details a seller gave you. We check whether it really belongs to the brand they claim to be.",
      brandLabel: "Brand they claim to be (optional)",
      brandPlaceholder: "e.g. Flipkart, Amazon India, Myntra, Tata CLiQ",
      brandHelp: "Leave blank to let us auto-detect it from the chat or link.",
      phoneLabel: "Phone / WhatsApp Number",
      phonePlaceholder: "e.g. +91 98765 43210 or 09876543210",
      chatLabel: "Chat message text",
      chatPlaceholder: "Paste the message or chat snippet here...",
      urlLabel: "Website link (URL)",
      urlPlaceholder: "e.g. https://flipkart.com/deal or discount-outlet.shop",
      upiLabel: "UPI ID / VPA",
      upiPlaceholder: "e.g. merchant@okhdfcbank or 9876543210@ybl",
      payeeLabel: "Payee name shown in UPI app",
      payeePlaceholder: "e.g. Rakesh K or Flipkart Internet",
      payeeHelpBtn: "ℹ️ Where to find?",
      payeeHelpText: "When you enter a UPI ID or scan a QR in Google Pay, PhonePe, or Paytm, the app shows the verified recipient name before you enter your UPI PIN. Copy or type that exact name here.",
      verifyBtn: "Verify Seller Details",
      verifyingBtn: "Analyzing Seller Details...",
      whyVerdict: "Why this verdict:",
      whatToDo: "What you should do:",
      openOfficial: "Open Official Website",
      reportBtn: "Report This Seller",
      checkAnother: "Check Another Seller",
      disclaimer: "⚠️ Automated estimate, not legal proof. Always verify through the brand's official website or app before transferring money."
    },
    ml: {
      tagline: "പണം നൽകുന്നതിന് മുൻപ് പരിശോധിക്കുക",
      heroTitle: "ഈ വ്യാപാരി യഥാർത്ഥമാണോ?",
      heroDesc: "വാട്ട്‌സ്ആപ്പ് സന്ദേശമോ, ഫോൺ നമ്പറോ, ലിങ്കോ, യുപിഐ പേയ്മെന്റ് വിവരങ്ങളോ നൽകി പരിശോധിക്കുക. ഇത് ഔദ്യോഗിക ബ്രാൻഡിന്റേതാണോ എന്ന് ഞങ്ങൾ ഒത്തുനോക്കുന്നു.",
      brandLabel: "അവകാശപ്പെടുന്ന ബ്രാൻഡ് (നിർബന്ധമില്ല)",
      brandPlaceholder: "ഉദാ: Flipkart, Amazon India, Myntra, Tata CLiQ",
      brandHelp: "ഒഴിവാക്കിയിട്ടാൽ ലിങ്കിൽ നിന്നോ സന്ദേശത്തിൽ നിന്നോ ഞങ്ങൾ കണ്ടെത്താം.",
      phoneLabel: "ഫോൺ / വാട്ട്‌സ്ആപ്പ് നമ്പർ",
      phonePlaceholder: "ഉദാ: +91 98765 43210 അല്ലെങ്കിൽ 09876543210",
      chatLabel: "ചാറ്റ് സന്ദേശം",
      chatPlaceholder: "വ്യാപാരി അയച്ച സന്ദേശം ഇവിടെ പേസ്റ്റ് ചെയ്യുക...",
      urlLabel: "വെബ്സൈറ്റ് ലിങ്ക് (URL)",
      urlPlaceholder: "ഉദാ: https://flipkart.com/deal അല്ലെങ്കിൽ discount-outlet.shop",
      upiLabel: "യുപിഐ (UPI) ഐഡി",
      upiPlaceholder: "ഉദാ: merchant@okhdfcbank അല്ലെങ്കിൽ 9876543210@ybl",
      payeeLabel: "യുപിഐ ആപ്പിൽ കാണിക്കുന്ന സ്വീകർത്താവിന്റെ പേര്",
      payeePlaceholder: "ഉദാ: Rakesh K അല്ലെങ്കിൽ Flipkart Internet",
      payeeHelpBtn: "ℹ️ ഇത് എവിടെ കാണാം?",
      payeeHelpText: "Google Pay, PhonePe അല്ലെങ്കിൽ Paytm-ൽ യുപിഐ ഐഡി നൽകുമ്പോഴോ ക്യുആർ കോഡ് സ്കാൻ ചെയ്യുമ്പോഴോ പിൻ നൽകുന്നതിന് മുൻപ് അക്കൗണ്ട് ഉടമയുടെ ഔദ്യോഗിക പേര് കാണിക്കും. ആ പേര് ഇവിടെ നൽകുക.",
      verifyBtn: "വിവരങ്ങൾ പരിശോധിക്കുക",
      verifyingBtn: "പരിശോധിച്ചുകൊണ്ടിരിക്കുന്നു...",
      whyVerdict: "ഈ തീരുമാനത്തിന് കാരണം:",
      whatToDo: "നിങ്ങൾ ചെയ്യേണ്ടത്:",
      openOfficial: "ഔദ്യോഗിക വെബ്സൈറ്റ് തുറക്കുക",
      reportBtn: "പരാതിപ്പെടുക",
      checkAnother: "മറ്റൊരു വ്യാപാരിയെ പരിശോധിക്കുക",
      disclaimer: "⚠️ ഇതൊരു ഓട്ടോമേറ്റഡ് അനുമാനം മാത്രമാണ്, നിയമപരമായ തെളിവല്ല. പണം നൽകുന്നതിന് മുൻപ് ബ്രാൻഡിന്റെ ഔദ്യോഗിക വെബ്സൈറ്റ് വഴിയോ ആപ്പ് വഴിയോ ഉറപ്പുവരുത്തുക."
    },
    hi: {
      tagline: "भुगतान करने से पहले जांचें",
      heroTitle: "क्या यह विक्रेता असली है?",
      heroDesc: "विक्रेता द्वारा दिया गया फ़ोन नंबर, व्हाट्सएप चैट, लिंक या यूपीआई विवरण दर्ज करें। हम जांचते हैं कि क्या यह वास्तव में उस ब्रांड का है जिसका वे दावा कर रहे हैं।",
      brandLabel: "कथित ब्रांड का नाम (वैकल्पिक)",
      brandPlaceholder: "उदा. Flipkart, Amazon India, Myntra, Tata CLiQ",
      brandHelp: "खाली छोड़ें यदि आप चाहते हैं कि हम चैट या लिंक से इसका पता लगाएं।",
      phoneLabel: "फ़ोन / व्हाट्सएप नंबर",
      phonePlaceholder: "उदा. +91 98765 43210 या 09876543210",
      chatLabel: "चैट संदेश",
      chatPlaceholder: "संदेश या चैट यहां पेस्ट करें...",
      urlLabel: "वेबसाइट लिंक (URL)",
      urlPlaceholder: "उदा. https://flipkart.com/deal या discount-outlet.shop",
      upiLabel: "यूपीआई आईडी (UPI ID)",
      upiPlaceholder: "उदा. merchant@okhdfcbank या 9876543210@ybl",
      payeeLabel: "यूपीआई ऐप में दिखने वाला प्राप्तकर्ता का नाम",
      payeePlaceholder: "उदा. Rakesh K या Flipkart Internet",
      payeeHelpBtn: "ℹ️ यह नाम कहाँ मिलता है?",
      payeeHelpText: "Google Pay, PhonePe या Paytm में UPI ID डालने या QR स्कैन करने पर UPI पिन दर्ज करने से पहले असली प्राप्तकर्ता का नाम दिखता है। वही नाम यहां दर्ज करें।",
      verifyBtn: "सत्यापित करें",
      verifyingBtn: "सत्यापन किया जा रहा है...",
      whyVerdict: "इस निर्णय का कारण:",
      whatToDo: "आपको क्या करना चाहिए:",
      openOfficial: "आधिकारिक वेबसाइट खोलें",
      reportBtn: "इसकी शिकायत करें",
      checkAnother: "अन्य विक्रेता की जांच करें",
      disclaimer: "⚠️ यह एक स्वचालित अनुमान है, कानूनी प्रमाण नहीं। पैसे भेजने से पहले हमेशा ब्रांड की आधिकारिक वेबसाइट या ऐप से पुष्टि करें।"
    }
  };

  let currentLang = "en";

  // Elements
  const langSelect = document.getElementById("langSelect");
  const form = document.getElementById("checkForm");
  const submitBtn = document.getElementById("submitBtn");
  const submitBtnText = document.getElementById("submitBtnText");
  const errorAlert = document.getElementById("errorAlert");
  const resultCard = document.getElementById("resultCard");
  const resetBtn = document.getElementById("resetBtn");

  const payeeHelpBtn = document.getElementById("payeeHelpBtn");
  const payeeHelpBox = document.getElementById("payeeHelpBox");

  const verdictBadge = document.getElementById("verdictBadge");
  const riskScoreValue = document.getElementById("riskScoreValue");
  const resultSummary = document.getElementById("resultSummary");
  const brandStatusText = document.getElementById("brandStatusText");
  const reasonsList = document.getElementById("reasonsList");
  const adviceList = document.getElementById("adviceList");
  const officialSiteAction = document.getElementById("officialSiteAction");
  const officialSiteLink = document.getElementById("officialSiteLink");
  const officialSiteBtnText = document.getElementById("officialSiteBtnText");
  const disclaimerText = document.getElementById("disclaimerText");

  // Report Modal Elements
  const openReportModalBtn = document.getElementById("openReportModalBtn");
  const reportModal = document.getElementById("reportModal");
  const closeReportModalBtn = document.getElementById("closeReportModalBtn");
  const reportForm = document.getElementById("reportForm");
  const reportIdentifier = document.getElementById("reportIdentifier");
  const reportType = document.getElementById("reportType");
  const reportAlert = document.getElementById("reportAlert");
  const submitReportBtn = document.getElementById("submitReportBtn");

  let lastCheckedData = null;

  // Language Change Handler
  function updateLanguage(lang) {
    currentLang = lang;
    const t = UI_TEXT[lang] || UI_TEXT.en;

    document.getElementById("taglineText").textContent = t.tagline;
    document.getElementById("heroTitle").textContent = t.heroTitle;
    document.getElementById("heroDesc").textContent = t.heroDesc;
    document.getElementById("brandLabel").textContent = t.brandLabel;
    document.getElementById("claimedBrand").placeholder = t.brandPlaceholder;
    document.getElementById("brandHelp").textContent = t.brandHelp;
    document.getElementById("phoneLabel").textContent = t.phoneLabel;
    document.getElementById("phoneNumber").placeholder = t.phonePlaceholder;
    document.getElementById("chatLabel").textContent = t.chatLabel;
    document.getElementById("messageText").placeholder = t.chatPlaceholder;
    document.getElementById("urlLabel").textContent = t.urlLabel;
    document.getElementById("url").placeholder = t.urlPlaceholder;
    document.getElementById("upiLabel").textContent = t.upiLabel;
    document.getElementById("upiId").placeholder = t.upiPlaceholder;
    document.getElementById("payeeLabel").textContent = t.payeeLabel;
    document.getElementById("displayName").placeholder = t.payeePlaceholder;
    document.getElementById("payeeHelpBtn").textContent = t.payeeHelpBtn;
    document.getElementById("payeeHelpText").textContent = t.payeeHelpText;
    submitBtnText.textContent = t.verifyBtn;
    document.getElementById("whyVerdictTitle").textContent = t.whyVerdict;
    document.getElementById("whatToDoTitle").textContent = t.whatToDo;
    document.getElementById("reportBtnText").textContent = t.reportBtn;
    resetBtn.textContent = t.checkAnother;
    disclaimerText.textContent = t.disclaimer;
  }

  langSelect.addEventListener("change", (e) => {
    updateLanguage(e.target.value);
  });

  // Toggle Payee Name Help Box
  payeeHelpBtn.addEventListener("click", () => {
    payeeHelpBox.classList.toggle("hidden");
  });

  // Form Submit Handler
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
      language: currentLang
    };

    submitBtn.disabled = true;
    submitBtnText.textContent = (UI_TEXT[currentLang] || UI_TEXT.en).verifyingBtn;

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

      lastCheckedData = {
        data: data,
        submitted: { phone, url, upi, brand }
      };

      displayResult(data);
    } catch (err) {
      errorAlert.textContent = err.message || "An error occurred while checking. Please try again.";
      errorAlert.classList.remove("hidden");
    } finally {
      submitBtn.disabled = false;
      submitBtnText.textContent = (UI_TEXT[currentLang] || UI_TEXT.en).verifyBtn;
    }
  });

  // Display Result Card
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
        brandStatusText.textContent = `Claimed '${data.brand.claimed}' (Found in verified official registry)`;
      } else {
        brandStatusText.textContent = `Claimed '${data.brand.claimed}' (NOT in official registry)`;
      }
    } else {
      brandStatusText.textContent = "No specific brand claimed or detected.";
    }

    // Action CTA: Open official website first if brand/domain is verified
    officialSiteAction.classList.add("hidden");
    if (data.brand && data.brand.in_registry && data.scores && data.scores.brand_identity) {
      const ev = data.scores.brand_identity.evidence || {};
      const officialDomains = ev.official_domains || [];
      if (officialDomains.length > 0) {
        const primaryDomain = officialDomains[0];
        officialSiteLink.href = `https://${primaryDomain}`;
        officialSiteBtnText.textContent = `${(UI_TEXT[currentLang] || UI_TEXT.en).openOfficial} (${primaryDomain})`;
        officialSiteAction.classList.remove("hidden");
      }
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
      li.textContent = "No specific red flags identified.";
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

    if (data.disclaimer) {
      disclaimerText.textContent = data.disclaimer;
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // Reset
  resetBtn.addEventListener("click", () => {
    resultCard.classList.add("hidden");
    form.classList.remove("hidden");
    form.reset();
  });

  // Report Modal Open / Close
  openReportModalBtn.addEventListener("click", () => {
    reportAlert.classList.add("hidden");
    reportAlert.textContent = "";

    // Pre-fill identifier from last checked input
    if (lastCheckedData && lastCheckedData.submitted) {
      const s = lastCheckedData.submitted;
      if (s.phone) {
        reportIdentifier.value = s.phone;
        reportType.value = "phone";
      } else if (s.url) {
        reportIdentifier.value = s.url;
        reportType.value = "domain";
      } else if (s.upi) {
        reportIdentifier.value = s.upi;
        reportType.value = "upi";
      }
    }

    reportModal.classList.remove("hidden");
  });

  closeReportModalBtn.addEventListener("click", () => {
    reportModal.classList.add("hidden");
  });

  // Report Submission
  reportForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const idVal = reportIdentifier.value.trim();
    const typeVal = reportType.value;
    const catVal = document.getElementById("reportCategory").value;
    const notesVal = document.getElementById("reportNotes").value.trim();

    if (!idVal) return;

    submitReportBtn.disabled = true;
    submitReportBtn.textContent = "Submitting...";

    try {
      const res = await fetch("/v1/reports", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          identifier: idVal,
          identifier_type: typeVal,
          category: catVal,
          notes: notesVal || null
        })
      });

      const repData = await res.json();
      if (!res.ok) {
        throw new Error(repData.detail || "Failed to submit report.");
      }

      reportAlert.className = "alert alert-success";
      reportAlert.textContent = `✅ ${repData.message || "Report registered successfully."}`;
      reportAlert.classList.remove("hidden");
      setTimeout(() => {
        reportModal.classList.add("hidden");
      }, 2500);
    } catch (err) {
      reportAlert.className = "alert alert-error";
      reportAlert.textContent = err.message || "Error submitting report.";
      reportAlert.classList.remove("hidden");
    } finally {
      submitReportBtn.disabled = false;
      submitReportBtn.textContent = "Submit Report";
    }
  });
});
