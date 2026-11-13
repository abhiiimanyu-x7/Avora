# AVORA

### Unified University Platform

A multi-service campus platform built with Flask, MongoDB Atlas, HTML5, CSS3, and Vanilla JavaScript.

---

## Service Modules

- 🗳️ **Elections** - Scheduled campus elections with automated status transitions, candidate manifestos, and one-vote enforcement.
- 🔍 **Lost & Found** - Admin-verified reporting and claim resolution with verification questions and duplicate checks.
- 📢 **Notices & Deadlines** - Official announcements with attached deadlines, auto-expiration, and priority alerts.
- 🧘 **Digital Wellbeing** - Private daily mood check-ins, personal trend tracking, and verified campus counseling resources.
- 📇 **Campus Contacts** - Directory of departments, emergency contacts, administrative offices, and faculties.
- 🗺️ **Campus Map** - Interactive labeled guide to campus zones, academic blocks, and student facilities.

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your MongoDB Atlas URI and secret key
```

### 3. Seed Admin Account

```bash
flask seed-admin
```

### 4. Run the Application

```bash
python app.py
```

The app will be available at `http://localhost:5000`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, Modern Institutional CSS, Vanilla JavaScript |
| Backend | Python Flask (Modular Monolith) |
| Database | MongoDB Atlas |
| Auth & Audit | Session auth, Scoped Admin RBAC, Audit Logging |

---

## License

MIT
