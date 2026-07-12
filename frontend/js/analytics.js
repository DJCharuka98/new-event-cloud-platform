function generateFallbackId() {
  return "user-" + Date.now() + "-" + Math.random().toString(36).substring(2, 15);
}

function getAnonymousUserId() {
  let userId = localStorage.getItem("anonymous_user_id");

  if (!userId) {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      userId = "user-" + window.crypto.randomUUID();
    } else {
      userId = generateFallbackId();
    }

    localStorage.setItem("anonymous_user_id", userId);
  }

  return userId;
}

function sendAnalytics(eventData) {
  const payload = {
    anonymous_user_id: getAnonymousUserId(),
    page: "new-event-homepage",
    ...eventData,
    metadata: {
      user_agent: navigator.userAgent,
      screen_width: window.innerWidth,
      screen_height: window.innerHeight,
      ...eventData.metadata
    }
  };

  console.log("Sending analytics event:", payload);

  fetch("/analytics/events", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  })
    .then(function (response) {
      console.log("Analytics response status:", response.status);
      return response.text();
    })
    .then(function (data) {
      console.log("Analytics response:", data);
    })
    .catch(function (error) {
      console.log("Analytics failed:", error);
    });
}

window.addEventListener("load", function () {
  sendAnalytics({
    event_type: "page_visit",
    section: "home"
  });
});

function trackSectionView(sectionId, eventType) {
  const section = document.getElementById(sectionId);

  if (!section) {
    console.log("Section not found:", sectionId);
    return;
  }

  const observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        sendAnalytics({
          event_type: eventType,
          section: sectionId
        });

        observer.unobserve(section);
      }
    });
  }, {
    threshold: 0.5
  });

  observer.observe(section);
}

trackSectionView("program", "program_section_view");
trackSectionView("speakers", "speaker_section_view");
trackSectionView("register", "registration_section_view");

document.addEventListener("click", function (event) {
  const clickedElement = event.target.closest("a, button, input[type='submit']");

  if (!clickedElement) {
    return;
  }

  const text = clickedElement.innerText || clickedElement.value || "";
  const href = clickedElement.getAttribute("href") || "";

  if (
    text.toLowerCase().includes("register") ||
    href.toLowerCase().includes("register")
  ) {
    sendAnalytics({
      event_type: "register_button_click",
      section: "register",
      metadata: {
        button_text: text,
        href: href
      }
    });
  }
});