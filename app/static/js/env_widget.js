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
      "&longitude=" + LON + "&current=temperature_2m,weather_code" +
      "&daily=precipitation_probability_max&timezone=Asia%2FManila";
    fetch(url, { silentLoader: true })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.current) return;
        var temp = Math.round(data.current.temperature_2m);
        var code = data.current.weather_code;
        var label = WMO[code] || "";
        var rainChance = (data.daily && data.daily.precipitation_probability_max)
          ? data.daily.precipitation_probability_max[0] : null;
        document.querySelectorAll(".js-weather").forEach(function (el) {
          el.textContent = "Calamba " + temp + "°C" + (label ? " · " + label : "");
        });
        updateCheckinWeather(code, temp, rainChance);
      })
      .catch(function () {
        document.querySelectorAll(".js-weather").forEach(function (el) {
          el.textContent = "Calamba";
        });
      });
  }

  // ---- "Your check-in" banner — weather line + time-of-day care reminder ----
  function updateCheckinWeather(code, temp, rainChance) {
    var text;
    if (typeof rainChance === "number" && rainChance >= 40) {
      text = "Bring an umbrella — there's a " + rainChance + "% chance of rain today.";
    } else if ([95, 96, 99].indexOf(code) > -1) {
      text = "There's a thunderstorm nearby — stay safe indoors.";
    } else if ((code === 0 || code === 1) && typeof temp === "number" && temp >= 32) {
      text = "It's hot and sunny today — stay hydrated.";
    } else if (typeof rainChance === "number") {
      text = "Low chance of rain today (" + rainChance + "%) — " + (WMO[code] || "should be fine") + ".";
    } else {
      text = (WMO[code] || "Weather") + " in Calamba today.";
    }
    document.querySelectorAll(".js-checkin-weather").forEach(function (el) { el.textContent = text; });
  }

  function updateCheckinMeal() {
    var els = document.querySelectorAll(".js-checkin-meal");
    if (!els.length) return;
    var hour = parseInt(hourFmt.format(new Date()), 10) % 24;
    var text;
    if (hour >= 5 && hour < 10) {
      text = "Don't skip breakfast — start your day right.";
    } else if (hour >= 10 && hour < 13) {
      text = "Have you had lunch? Take a proper break to eat.";
    } else if (hour >= 13 && hour < 17) {
      text = "Remember to stay hydrated this afternoon.";
    } else if (hour >= 17 && hour < 21) {
      text = "Have you had dinner? Please don't skip it to finish something.";
    } else {
      text = "It's getting late — try to wrap up and rest soon.";
    }
    els.forEach(function (el) { el.textContent = text; });
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
    updateCheckinMeal();
    setInterval(updateCheckinMeal, 60000); // re-check each minute so it flips right at noon/evening
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
