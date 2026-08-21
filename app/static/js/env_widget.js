/* Live local time (Asia/Manila) + Calamba weather via Open-Meteo (no API key).
   Populates any .js-clock / .js-date / .js-weather elements on the page. */
(function () {
  "use strict";

  // Calamba City, Laguna
  var LAT = 14.2117, LON = 121.1653, TZ = "Asia/Manila";

  // WMO weather codes -> short label
  var WMO = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Fog", 51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Violent showers",
    85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm"
  };

  var timeFmt = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ, hour: "numeric", minute: "2-digit", second: "2-digit", hour12: true
  });
  var dateFmt = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ, weekday: "short", month: "short", day: "numeric"
  });

  function tickClock() {
    var now = new Date();
    var t = timeFmt.format(now), d = dateFmt.format(now);
    document.querySelectorAll(".js-clock").forEach(function (el) {
      el.textContent = t; el.setAttribute("title", d);
    });
    document.querySelectorAll(".js-date").forEach(function (el) { el.textContent = d; });
  }

  function loadWeather() {
    var url = "https://api.open-meteo.com/v1/forecast?latitude=" + LAT +
      "&longitude=" + LON + "&current=temperature_2m,weather_code&timezone=Asia%2FManila";
    fetch(url)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.current) return;
        var temp = Math.round(data.current.temperature_2m);
        var code = data.current.weather_code;
        var label = WMO[code] || "";
        document.querySelectorAll(".js-weather").forEach(function (el) {
          el.textContent = "Calamba " + temp + "°C" + (label ? " · " + label : "");
        });
        updateGreeting(code, temp);
      })
      .catch(function () {
        document.querySelectorAll(".js-weather").forEach(function (el) {
          el.textContent = "Calamba";
        });
      });
  }

  // ---- Time- and weather-aware greeting (dashboard banner) ----
  var MORNING_TIPS = [
    "a morning walk to start the day right",
    "a quick workout before the day gets busy",
    "a healthy breakfast",
    "a bit of stretching"
  ];
  var AFTERNOON_TIPS = [
    "staying hydrated through the afternoon",
    "taking a short breather",
    "a good lunch break"
  ];
  var EVENING_TIPS = [
    "winding down after a long day",
    "getting some rest soon",
    "a relaxing evening"
  ];

  function timeGreeting(hour) {
    if (hour >= 5 && hour < 12) return "Good morning";
    if (hour >= 12 && hour < 18) return "Good afternoon";
    return "Good evening";
  }

  function weatherMessage(code, temp) {
    if (code === null || code === undefined) return null;
    if ([95, 96, 99].indexOf(code) > -1) {
      return { icon: "⛈️", text: "There's a thunderstorm nearby — stay safe indoors." };
    }
    if ([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82].indexOf(code) > -1) {
      return { icon: "☔", text: "It's rainy in Calamba today — don't forget your umbrella." };
    }
    if ([45, 48].indexOf(code) > -1) {
      return { icon: "🌫️", text: "Foggy conditions today — drive safely if you're heading out." };
    }
    if ((code === 0 || code === 1) && typeof temp === "number" && temp >= 32) {
      return { icon: "☀️", text: "It's hot and sunny — stay hydrated and take care out there." };
    }
    if (code === 0 || code === 1) {
      return { icon: "☀️", text: "Clear skies today — a great day ahead." };
    }
    return null; // overcast / partly cloudy -> fall back to the time-based tip
  }

  function todayKey() {
    var d = new Date();
    return d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate();
  }

  function updateGreeting(weatherCode, weatherTemp) {
    var banners = document.querySelectorAll(".js-greeting");
    if (!banners.length) return;

    try {
      if (window.localStorage && localStorage.getItem("greetingDismissed") === todayKey()) {
        return; // dismissed for today — stay hidden
      }
    } catch (e) { /* localStorage unavailable — just show it */ }

    var now = new Date();
    var hour = parseInt(hourFmt.format(now), 10) % 24;
    var greeting = timeGreeting(hour);
    var tipList = hour < 12 ? MORNING_TIPS : (hour < 18 ? AFTERNOON_TIPS : EVENING_TIPS);
    var tip = tipList[now.getDate() % tipList.length];

    var w = weatherMessage(weatherCode, weatherTemp);
    var icon = w ? w.icon : (hour < 12 ? "🌅" : hour < 18 ? "🌤️" : "🌙");
    var message = w ? w.text : ("Maybe it's time for " + tip + ".");

    banners.forEach(function (el) {
      var firstName = el.getAttribute("data-first-name") || "";
      var titleEl = el.querySelector(".js-greeting-title");
      var msgEl = el.querySelector(".js-greeting-message");
      var iconEl = el.querySelector(".js-greeting-icon");
      if (titleEl) titleEl.textContent = greeting + (firstName ? ", " + firstName + "!" : "!");
      if (msgEl) msgEl.textContent = message;
      if (iconEl) iconEl.textContent = icon;
      el.hidden = false;
    });
  }

  function setupGreetingDismiss() {
    var closeBtn = document.getElementById("greetingBannerClose");
    var banner = document.getElementById("greetingBanner");
    if (!closeBtn || !banner) return;
    closeBtn.addEventListener("click", function () {
      banner.hidden = true;
      try {
        if (window.localStorage) localStorage.setItem("greetingDismissed", todayKey());
      } catch (e) { /* ignore */ }
    });
  }

  var hourFmt = new Intl.DateTimeFormat("en-US", { timeZone: TZ, hour: "numeric", hour12: false });
  function applyOwlMode() {
    var h = parseInt(hourFmt.format(new Date()), 10) % 24;
    var day = h >= 6 && h < 18; // 6am–6pm: owl asleep; else awake
    var root = document.documentElement;
    root.classList.toggle("is-day", day);
    root.classList.toggle("is-night", !day);
  }

  function start() {
    tickClock();
    setInterval(tickClock, 1000);
    updateGreeting(null, null); // show immediately with a time-based message; weather refines it below
    setupGreetingDismiss();
    loadWeather();
    setInterval(loadWeather, 600000); // refresh weather every 10 min
    applyOwlMode();
    setInterval(applyOwlMode, 60000); // re-check day/night each minute
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
