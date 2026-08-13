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
        var label = WMO[data.current.weather_code] || "";
        document.querySelectorAll(".js-weather").forEach(function (el) {
          el.textContent = "Calamba " + temp + "°C" + (label ? " · " + label : "");
        });
      })
      .catch(function () {
        document.querySelectorAll(".js-weather").forEach(function (el) {
          el.textContent = "Calamba";
        });
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
