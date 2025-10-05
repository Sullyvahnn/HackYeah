Jasne! Oto angielska wersja Twojego README, dopasowana pod hackathon i kategorię **Travel / Safety**:

---

# ThreatLens 🌍🚨

**ThreatLens** is a web application that helps travelers and residents **navigate new places safely** by mapping threats in real time and visualizing them on an interactive heatmap.

---

## 📌 Project Description

ThreatLens combines data from multiple sources to show safety levels in different areas:

* Official threat data (e.g., KMZB)
* Local news articles (analyzed with AI for threat classification)
* User-reported incidents and safety observations

The app generates a **dynamic risk heatmap**, allowing users to:

* check the safety level of nearby areas,
* receive **notifications when entering potentially dangerous zones**,
* plan **safe travel routes**,
* use a family mode (alerts when a child enters a high-risk zone).

The goal of ThreatLens is to support travelers, families, and locals in moving through cities with increased awareness and safety.

---

## ⚡ Key Features

* Real-time threat mapping
* AI-powered article analysis and filtering of false/duplicate reports
* Dynamic **safety heatmap**
* Geofencing notifications
* Safe route planning
* Family mode – monitor children’s safety
* Community-driven threat reporting

---

## 💡 Future Enhancements

* **Traveler View** – highlights areas less safe for tourists
* Integration with Google Maps / OpenStreetMap for safe route optimization
* Contextual alerts (e.g., recent incidents in the area)
* Offline mode – access basic data without internet
* User reputation system – reliable reports increase trust

---

## 🛠️ Technology Stack

* **Frontend:** HTML5, CSS, JS
* **Backend:** Python (API, scraper, AI processing)
* **Database:** SQLite(user reports, heatmap, analytics)
* **AI/ML:** Groq and Gemini API, OLlama local
* **Geolocation:** HTML5 Geolocation & geofencing
* **Scraper:** Automated collection of data from KMZB and local news sources
