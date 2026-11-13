# Avora knowledge base - index
_Last updated: 2026-09-27._

This folder is the knowledge source for the "Ask Avora" assistant's university-info intent.
Each file is one topic, small enough to hand to an LLM whole once matched. Retrieval should
be simple keyword matching against the headings/filenames below: no embeddings needed at
this size.

## Files and what they cover
| File | Covers | Match on keywords like |
|---|---|---|
| 01-university-overview.md | History, accreditation, vision/mission, faculties list | "about", "history", "NAAC", "when was", "faculties" |
| 02-leadership-and-central-admin.md | Chancellor, VC, Registrar, Finance Officer, COE, DSW, Proctor | "chancellor", "vice chancellor", "registrar", "finance officer", "exam controller" |
| 03-committees-and-student-support.md | Proctorial board, scholarships, grievance/anti-ragging, NCC, NSS, Rovers & Rangers, hostels | "hostel", "warden", "scholarship", "ragging", "grievance", "NCC", "NSS" |
| 04-placement-cell.md | TPC team, department placement reps | "placement", "TPO", "internship", "job", "recruiter" |
| 05-departments-and-deans.md | HOD per department, faculty deans | "HOD", "head of department", "dean", any department name |
| 06-infrastructure-and-facilities.md | Library, labs, health centre, gym, AIF, sustainability | "library", "lab", "health centre", "gym", "incubation", "AIF" |
| 07-guest-house.md | Guest house booking rules and rates | "guest house", "parents stay", "booking" |
| 08-admissions-process-2026-27.md | Dates, fees, documents, reservation policy | "admission", "apply", "deadline", "reservation", "documents required" |
| 09-programmes-by-faculty-2026-27.md | Every UG/PG/Diploma programme, seats, fees, mode | any programme name (e.g. "B.Tech CSE", "B.A. English", "MBA fee") |
| 10-academic-calendar-2026-27.md | Semester dates, exams, breaks, result dates | "semester dates", "when does college start", "exam dates", "winter break", "summer break" |
| 11-library-membership-and-rules.md | Borrowing limits, fines, timings, general rules | "library", "fine", "borrow", "library timing", "no dues" |
| 12-community-outreach-pathshala.md | NSS-run Pathshala programme for local children | "pathshala", "community", "outreach", "NSS teaching" |
| 13-sgrc-committee-members.md | SGRC member list | "SGRC", "grievance committee members", "lokpal" |
| 14-student-facility-center-detail.md | IKS office, canteen, bank, art gallery, museum (SFC) | "IKS", "canteen", "art gallery", "student facility center" |
| 15-media-studio-detail.md | Media Studio equipment and use (JMC dept.) | "media studio", "camera", "editing lab", "green screen" |
| 16-day-care-centre.md | Staff day care centre | "day care", "creche", "childcare" |
| 17-university-timings.md | Office/academic hours, hostel timings+capacity+fees, library hours | "timing", "hours", "open", "close", "hostel fee", "capacity" |

## Retrieval approach for the hackathon build
1. On a query, lowercase it and check for filename/heading keywords above.
2. Pull the matched file's content (or the matched section if the file is long).
3. Pass just that section + the original question to the LLM, plus a short system
   instruction: "Answer only from the provided context. If the answer isn't in the context,
   say you don't have that information and suggest checking kmclu.ac.in."
4. Show a small source chip in the UI naming the matched file, e.g. "From: Admissions".

## Maintenance notes
- Files carry a "last updated" date: recheck before a new admission cycle, since dates,
  fees and contact numbers change every session.
- Two figures appear inconsistently in official sources (NAAC grade, total student count):
  flagged inline in 01-university-overview.md. Don't state either with false confidence.
- If a phone number or email bounces, prefer directing the student to reg@kmclu.ac.in or
  admission@kmclu.ac.in over guessing a replacement contact.
