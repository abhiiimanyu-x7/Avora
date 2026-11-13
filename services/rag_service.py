"""
RAG Service for Ask Avora Knowledge Assistant.
Comprehensive Query Understanding, Grounded Hybrid Semantic Retrieval, Multi-turn Context Resolution,
Multi-part Query Reasoning, Scoped Web Fallback, and Zero-Hallucination Guardrails.
"""

import os
import re
import time
import threading
import logging
import requests as _requests

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_DIR = os.path.join(BASE_DIR, 'knowledge_base', 'Avora-rag')

logger = logging.getLogger('avora.rag')

# ─────────────────────────────────────────────────────────────
# 1. HINGLISH, TYPO & SYNONYM PRE-PROCESSING
# ─────────────────────────────────────────────────────────────

HINGLISH_MAP = [
    # NSS / NCC / Clubs
    (r'\bnss\s+(kaise|kese)\s+(join|jude|register|le)\b', 'how to join nss'),
    (r'\bnss\s+(me|mein)\s+(kaise|kese)\b', 'how to join nss'),
    (r'\bnss\s+join\s+karna\s+hai\b', 'how to join nss'),
    (r'\bncc\s+(kaise|kese)\s+(join|jude|register|le)\b', 'how to join ncc'),
    (r'\bkaun\s+kaun\s+se\s+club\b', 'what clubs can i join'),
    (r'\bkaun\s+se\s+club\b', 'what clubs can i join'),

    # Fees & Tuition
    (r'\b(kitni|kitna|kitne)\s+(fees|fee|paisa|charges)\b', 'fees tuition cost'),
    (r'\b(fees|fee)\s+(kitni|kitna|kitne)\s+hai\b', 'fees tuition cost'),
    (r'\b(fees|fee)\s+batao\b', 'fees structure'),
    (r'\bpadhai\s+ka\s+kharcha\b', 'tuition fees'),

    # Timings & Hours
    (r'\b(kab|kitne\s+baje)\s+(khulta|band|open|close)\b', 'timings hours'),
    (r'\b(timing|samay)\s+kya\s+hai\b', 'timings hours'),
    (r'\buniversity\s+kab\s+(khulti|khulta|open)\b', 'university timings'),
    (r'\blibrary\s+kab\s+(khulti|khulta|open)\b', 'library timings'),

    # Locations
    (r'\b(kaha|kidhar|kahan)\s+(hai|pe\s+hai|milega)\b', 'where is location'),
    (r'\blibrary\s+(kaha|kidhar)\b', 'where is library'),

    # Leadership & Faculty
    (r'\b(kon|koun|kaun)\s+hai\b', 'who is'),
    (r'\b(vc|proctor|dean|hod|registrar)\s+(kon|koun|kaun)\s+hai\b', 'who is'),
    (r'\b(kisse|kisko)\s+contact\s+kare\b', 'who to contact'),
    (r'\bbaat\s+kaise\s+kare\b', 'how to contact'),

    # Grievances & Discipline
    (r'\bshikayat\s+(kaha|kidhar|kaise)\s+kare\b', 'student grievances redressal'),
    (r'\bragging\s+ki\s+shikayat\b', 'anti ragging proctor'),
    (r'\bladaai|jhagda\b', 'student discipline proctorial board'),

    # Scholarships & Welfare
    (r'\bchhatravritti|wazifa|scholarship\s+kaise\b', 'scholarship application'),
]

TYPO_MAP = {
    'procter': 'proctor',
    'proctorial': 'proctorial',
    'ragging': 'ragging',
    'antiragging': 'anti-ragging',
    'hostal': 'hostel',
    'registar': 'registrar',
    'regstrar': 'registrar',
    'libary': 'library',
    'librery': 'library',
    'adminssion': 'admission',
    'addmission': 'admission',
    'addmision': 'admission',
    'elgibility': 'eligibility',
    'sgrc': 'sgrc',
    'tpo': 'tpo',
    'placements': 'placement',
    'bismil': 'bismil',
    'counselling': 'counseling',
    'fees': 'fees',
    'fee': 'fees',
    'timeing': 'timing',
    'timeings': 'timings',
    'shcedule': 'schedule',
    'creche': 'day care',
    'childcare': 'day care',
}

STOP_WORDS = {
    'what', 'is', 'the', 'for', 'in', 'at', 'of', 'and', 'a', 'an', 'to', 'how',
    'can', 'i', 'tell', 'me', 'about', 'who', 'does', 'when', 'are', 'there',
    'any', 'do', 'you', 'have', 'give', 'please', 'details', 'regarding'
}

def clean_no_em_dash(text):
    """Ensure zero em dash or en dash characters in text."""
    if not text:
        return ""
    return text.replace('\u2014', ', ').replace('\u2013', '-').replace('—', ', ').replace('–', '-')

def clean_tokens(text):
    """Extract lowercase alphanumeric tokens."""
    return set(re.findall(r'[a-z0-9]+', text.lower()))

def normalize_query(query_text):
    """Normalize user query by expanding Hinglish, fixing typos, and normalizing degree abbreviations."""
    q = query_text.strip().lower()
    q = re.sub(r'[?!.,;:\'"]+', ' ', q)
    q = re.sub(r'\s+', ' ', q).strip()

    # Apply Hinglish mappings
    for pattern, replacement in HINGLISH_MAP:
        q = re.sub(pattern, replacement, q)

    # Word-level typo correction
    tokens = q.split()
    corrected_tokens = [TYPO_MAP.get(token, token) for token in tokens]
    q = ' '.join(corrected_tokens)

    # Degree normalization
    q = re.sub(r'\bb\.?\s*tech\.?\b', 'btech', q)
    q = re.sub(r'\bb\.?\s*com\.?\b', 'bcom', q)
    q = re.sub(r'\bm\.?\s*com\.?\b', 'mcom', q)
    q = re.sub(r'\bb\.?\s*b\.?\s*a\.?\b', 'bba', q)
    q = re.sub(r'\bm\.?\s*b\.?\s*a\.?\b', 'mba', q)
    q = re.sub(r'\bb\.?\s*c\.?\s*a\.?\b', 'bca', q)
    q = re.sub(r'\bm\.?\s*c\.?\s*a\.?\b', 'mca', q)
    q = re.sub(r'\bb\.?\s*a\.?\b', 'ba', q)
    q = re.sub(r'\bm\.?\s*a\.?\b', 'ma', q)
    q = re.sub(r'\bb\.?\s*sc\.?\b', 'bsc', q)
    q = re.sub(r'\bm\.?\s*sc\.?\b', 'msc', q)
    q = re.sub(r'\bph\.?\s*d\.?\b', 'phd', q)

    return q


# ─────────────────────────────────────────────────────────────
# 2. PRONOUN & CONVERSATION CONTEXT RESOLUTION
# ─────────────────────────────────────────────────────────────

PRONOUN_PATTERNS = [
    r'\b(them|him|her|their|his|they)\b',
    r'\bcontact\s+(them|him|her)\b',
    r'\bhow\s+can\s+i\s+contact\s+(them|him|her)\b',
    r'\b(their|his|her)\s+(phone|contact|number|email|office)\b',
    r'\bcall\s+(them|him|her)\b',
    r'\breach\s+(them|him|her)\b',
    r'\bwhere\s+is\s+(it|that)\b',
    r'\bwhat\s+about\s+it\b',
]

def extract_last_entity(history):
    """
    Look back through previous conversation turns to find the most recent
    active entity (e.g. proctor, library, vc, dsw, registrar, nss).
    """
    if not history:
        return None

    for turn in reversed(history):
        if isinstance(turn, dict):
            if turn.get('entity'):
                return turn.get('entity')

            combined = (turn.get('query', '') + ' ' + turn.get('content', '') + ' ' + turn.get('answer', '')).lower()
            if any(k in combined for k in ['proctor', 'neeraj shukla', 'proctorial']):
                return 'proctor'
            if any(k in combined for k in ['vice chancellor', 'vc', 'ajay taneja']):
                return 'vice_chancellor'
            if any(k in combined for k in ['registrar', 'vikas']):
                return 'registrar'
            if any(k in combined for k in ['dsw', 'masood alam', 'dean students welfare']):
                return 'dsw'
            if any(k in combined for k in ['nss', 'nalini mishra']):
                return 'nss'
            if any(k in combined for k in ['ncc', 'bushra alvera']):
                return 'ncc'
            if any(k in combined for k in ['sgrc', 'grievance', 'lokpal', 'ombudsperson']):
                return 'sgrc'
            if any(k in combined for k in ['library', 'ram prasad bismil']):
                return 'library'
            if any(k in combined for k in ['btech', 'b.tech', 'cse']):
                return 'btech'
            if any(k in combined for k in ['hostel', 'warden']):
                return 'hostel'
    return None

def resolve_contextual_query(raw_query, history):
    """
    If the query has pronouns like 'them', 'their contact', resolve to the active entity.
    """
    q_norm = normalize_query(raw_query)
    has_pronoun = any(re.search(pat, q_norm) for pat in PRONOUN_PATTERNS)

    if not has_pronoun:
        if q_norm in ['contact details', 'contact', 'how to contact', 'phone number', 'email', 'office location', 'where']:
            has_pronoun = True

    if has_pronoun and history:
        entity = extract_last_entity(history)
        if entity == 'proctor':
            return 'contact proctor dr neeraj shukla phone email', 'proctor'
        elif entity == 'vice_chancellor':
            return 'contact vice chancellor prof ajay taneja vc office email', 'vice_chancellor'
        elif entity == 'registrar':
            return 'contact registrar vikas phone email', 'registrar'
        elif entity == 'dsw':
            return 'contact dean students welfare prof masood alam phone email', 'dsw'
        elif entity == 'nss':
            return 'contact nss coordinator dr nalini mishra phone email', 'nss'
        elif entity == 'ncc':
            return 'contact ncc coordinator dr bushra alvera phone email', 'ncc'
        elif entity == 'sgrc':
            return 'contact students grievance redressal committee sgrc prof masood alam', 'sgrc'
        elif entity == 'library':
            return 'library timings rules contact', 'library'
        elif entity == 'btech':
            return 'btech cse fees eligibility duration', 'btech'
        elif entity == 'hostel':
            return 'hostel warden timings fees', 'hostel'

    return q_norm, None


def _get_database():
    """Get database reference from current_app or direct pymongo client fallback."""
    try:
        from flask import current_app
        if current_app and hasattr(current_app, 'db') and current_app.db is not None:
            return current_app.db
    except Exception:
        pass
    try:
        import pymongo
        uri = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/avora')
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=1500)
        try:
            return client.get_default_database()
        except Exception:
            db_name = uri.split('/')[-1].split('?')[0] or 'avora'
            return client[db_name]
    except Exception:
        return None

def search_live_data(q_norm):
    """Check MongoDB collections for dynamic elections, notices, and lost property."""
    try:
        db = _get_database()
        if db is None:
            return None

        # Elections
        if any(w in q_norm for w in ['election', 'vote', 'candidate', 'polling', 'ballot', 'voter', 'voting']):
            active_count = db.elections.count_documents({'status': 'active'})
            upcoming_count = db.elections.count_documents({'status': 'upcoming'})
            active_elections = list(db.elections.find({'status': 'active'}, {'title': 1, 'post_name': 1}))
            if active_elections:
                titles = ', '.join([f"{e.get('title')} ({e.get('post_name')})" for e in active_elections])
                return {
                    'answer': f"There are currently {active_count} active election(s) open for voting: {titles}.\n\nYou can review candidate manifestos and cast your secure ballot in the Elections section.",
                    'source': 'Live Elections System',
                    'action_link': {'label': 'View Active Elections', 'url': '/student/elections'},
                    'entity': 'elections'
                }
            elif upcoming_count > 0:
                return {
                    'answer': f"There are currently no active ballots open for voting, but {upcoming_count} upcoming student council election(s) are scheduled on the platform.",
                    'source': 'Live Elections System',
                    'action_link': {'label': 'Check Scheduled Elections', 'url': '/student/elections'},
                    'entity': 'elections'
                }
            else:
                return {
                    'answer': "There are currently no active or upcoming student elections scheduled in the system.",
                    'source': 'Live Elections System',
                    'action_link': {'label': 'Go to Elections', 'url': '/student/elections'},
                    'entity': 'elections'
                }

        # Notices & Deadlines
        if any(w in q_norm for w in ['notice', 'announcement', 'circular', 'deadline', 'bulletin', 'latest order']):
            active_notices = list(db.notices.find().sort('created_at', -1).limit(3))
            if active_notices:
                bullets = []
                for n in active_notices:
                    title = n.get('title', 'Notice')
                    dept = n.get('department', 'General')
                    deadline = n.get('deadline_date')
                    item_str = f"• {title} ({dept})"
                    if deadline:
                        item_str += f" - Deadline: {deadline}"
                    bullets.append(item_str)
                bullet_text = '\n'.join(bullets)
                return {
                    'answer': f"Here are the latest campus notices:\n\n{bullet_text}\n\nVisit the Notices & Deadlines section to read complete circular documents and deadlines.",
                    'source': 'Live Campus Notices',
                    'action_link': {'label': 'View Notices & Deadlines', 'url': '/student/notices'},
                    'entity': 'notices'
                }

        # Lost and Found
        if any(w in q_norm for w in ['lost', 'found', 'claim', 'missing', 'belonging', 'lost item', 'wallet', 'calculator']):
            unclaimed = db.lost_found.count_documents({'status': 'unclaimed'})
            open_lost = db.lost_reports.count_documents({'status': 'open'})
            return {
                'answer': f"There are currently {unclaimed} unclaimed found item(s) and {open_lost} open lost report(s) logged in the campus Lost and Found portal.\n\nIf you have misplaced property or found an unattended item on campus, you can inspect items or log a report with private verification questions.",
                'source': 'Live Lost and Found',
                'action_link': {'label': 'Browse Lost & Found', 'url': '/lost-found'},
                'entity': 'lost_found'
            }

    except Exception as e:
        logger.debug('Live data retrieval error: %s', e)

    return None


# ─────────────────────────────────────────────────────────────
# 4. GROUNDED KNOWLEDGE BASE RETRIEVAL ENGINE (TF-IDF + HYBRID)
# ─────────────────────────────────────────────────────────────

class _KBIndex:
    """Thread-safe index over markdown files in knowledge_base/Avora-rag."""
    def __init__(self, kb_dir):
        self.kb_dir = kb_dir
        self.chunks = []
        self.vectorizer = None
        self.tfidf_matrix = None
        self._lock = threading.Lock()
        self._build_index()

    def _build_index(self):
        if not os.path.exists(self.kb_dir):
            return

        chunks = []
        for fname in sorted(os.listdir(self.kb_dir)):
            if not fname.endswith('.md') or fname == '00-index.md':
                continue
            fpath = os.path.join(self.kb_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    text = f.read()
            except Exception:
                continue

            # Strip last updated line so dates don't match falsely
            text = re.sub(r'_Last updated:[^_]+_', '', text)

            doc_title_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
            doc_title = doc_title_match.group(1).strip() if doc_title_match else fname

            # Split sections by ## headings
            sections = re.split(r'\n(?=##\s+)', text)
            for sec in sections:
                sec = sec.strip()
                if not sec or len(sec) < 30:
                    continue
                heading_match = re.match(r'^#+\s+(.+)$', sec.split('\n')[0])
                sec_title = heading_match.group(1).strip() if heading_match else doc_title

                combined_search = f"{doc_title}\n{sec_title}\n{sec}".lower()
                tokens = clean_tokens(combined_search)

                chunks.append({
                    'file_name': fname,
                    'doc_title': doc_title,
                    'section_title': sec_title,
                    'content': sec,
                    'tokens': tokens,
                    'searchable_text': combined_search
                })

        if chunks:
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english', sublinear_tf=True)
            self.tfidf_matrix = self.vectorizer.fit_transform([c['searchable_text'] for c in chunks])
            self.chunks = chunks

    def retrieve(self, query, top_k=2):
        if not self.chunks or self.vectorizer is None or self.tfidf_matrix is None:
            return []

        q_norm = normalize_query(query)
        q_tokens = clean_tokens(q_norm) - STOP_WORDS
        if not q_tokens:
            return []

        expanded_tokens = set(q_tokens)
        if 'bcom' in q_tokens or 'commerce' in q_tokens:
            expanded_tokens.update(['bcom', 'commerce'])
        if 'bba' in q_tokens or 'business' in q_tokens:
            expanded_tokens.update(['bba', 'business', 'management'])
        if 'btech' in q_tokens or 'engineering' in q_tokens:
            expanded_tokens.update(['btech', 'engineering', 'cse'])
        if 'nss' in q_tokens:
            expanded_tokens.update(['nss', 'national', 'service', 'scheme'])
        # Course/programme synonyms — critical for broad queries
        if any(t in q_tokens for t in ['course', 'courses', 'programme', 'programmes', 'program', 'programs', 'offered', 'available']):
            expanded_tokens.update(['course', 'courses', 'programme', 'programmes', 'faculty', 'seats', 'btech', 'bcom', 'ba', 'ma', 'bca', 'mba', 'mca', 'bsc', 'llb', 'bpharm'])
        if any(t in q_tokens for t in ['department', 'departments', 'faculty', 'faculties', 'school']):
            expanded_tokens.update(['faculty', 'department', 'dean', 'arts', 'science', 'commerce', 'engineering', 'pharmacy', 'legal'])

        q_vec = self.vectorizer.transform([q_norm])
        tfidf_sims = cosine_similarity(q_vec, self.tfidf_matrix)[0]

        scored = []
        generic_words = {
            'kmclu', 'university', 'lucknow', 'college', 'campus', 'details', 'detail',
            'info', 'information', 'student', 'students', '2024', '2025', '2026', '2027', 'session', 'year'
        }
        content_tokens = q_tokens - generic_words
        if not content_tokens:
            content_tokens = q_tokens

        for i, chunk in enumerate(self.chunks):
            tfidf_score = tfidf_sims[i]

            # Token overlap with content tokens
            matched_content = content_tokens.intersection(chunk['tokens'])
            content_overlap = len(matched_content) / max(len(content_tokens), 1)

            # Check if any subject token appears in searchable text
            key_match = 0.0
            for tok in expanded_tokens:
                if tok in chunk['searchable_text']:
                    key_match += 0.2

            # Boost chunks from the programmes file for course-related queries
            programme_boost = 0.0
            if any(t in expanded_tokens for t in ['course', 'courses', 'programme', 'programmes', 'seats', 'offered']):
                if 'programme' in chunk['file_name'].lower() or 'faculty' in chunk.get('section_title', '').lower():
                    programme_boost = 0.15

            # Hybrid score
            hybrid_score = (0.5 * tfidf_score) + (0.3 * content_overlap) + (0.2 * min(key_match, 1.0)) + programme_boost

            # Disqualify if no content tokens match — but relax for short queries (1-2 content tokens)
            if len(content_tokens) >= 3 and content_overlap < 0.40:
                hybrid_score = 0.0
            elif len(content_tokens) == 2 and content_overlap < 0.30:
                # Slightly relaxed for 2-word queries
                if not any(t in chunk['searchable_text'] for t in content_tokens):
                    hybrid_score = 0.0
            elif not matched_content and not any(t in chunk['searchable_text'] for t in content_tokens):
                hybrid_score = 0.0

            scored.append((hybrid_score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        # For broad listing queries, return more chunks to cover multiple faculties
        effective_k = top_k
        if any(t in expanded_tokens for t in ['course', 'courses', 'programme', 'programmes']):
            effective_k = max(top_k, 4)
        return scored[:effective_k]


_kb_index_instance = None
_kb_lock = threading.Lock()

def get_kb_index():
    global _kb_index_instance
    if _kb_index_instance is None:
        with _kb_lock:
            if _kb_index_instance is None:
                _kb_index_instance = _KBIndex(KB_DIR)
    return _kb_index_instance


# ─────────────────────────────────────────────────────────────
# 5. PRECISION HANDLERS & CONFLICT HANDLING
# ─────────────────────────────────────────────────────────────

def get_answer_for_nss(q_norm):
    """Precision answer for National Service Scheme (NSS)."""
    return {
        'answer': (
            "To join the National Service Scheme (NSS) at KMCLU:\n\n"
            "• **Enrollment Drive**: Students enroll during the annual orientation and membership drive announced at the beginning of the academic semester.\n"
            "• **Active Units**: KMCLU operates 8 active NSS units engaging in community health drives, social awareness, environmental projects, and rural outreach.\n"
            "• **Pathshala Program**: Volunteers also teach underprivileged local children through the university's Pathshala initiative.\n"
            "• **NSS Coordinator**: Dr. Nalini Mishra (Phone: +91-7905062761, Email: nsscoordinator@kmclu.ac.in).\n"
            "• **Programme Officers**: You can register directly through your faculty unit officer (Units 1 to 8) at the Students' Facility Centre (SFC)."
        ),
        'source': 'Student Support and Committees',
        'entity': 'nss'
    }

def get_answer_for_proctor(q_norm):
    """Precision answer for Proctorial Board and Student Discipline."""
    is_contact_only = any(k in q_norm for k in ['contact', 'phone', 'email', 'number', 'reach', 'call', 'office'])
    if is_contact_only:
        return {
            'answer': (
                "You can contact the Proctorial Board at KMCLU through:\n\n"
                "• **Proctor**: Dr. Neeraj Shukla\n"
                "• **Phone**: +91-9451383900\n"
                "• **Email**: proctor@kmclu.ac.in\n"
                "• **Assistant Proctors**: Dr. Mamta Shukla (+91-9236073824), Dr. Ramjeet Singh Yadav (+91-6388942048), Dr. Mohammad Sharique (+91-9368017724).\n"
                "• **Office Location**: Acharya Narendra Deva Administrative Building, KMCLU Campus."
            ),
            'source': 'Leadership and Central Administration',
            'action_link': {'label': 'View Directory Contacts', 'url': '/student/contacts'},
            'entity': 'proctor'
        }

    return {
        'answer': (
            "The Proctorial Board at KMCLU is the statutory body entrusted with maintaining campus discipline and student safety:\n\n"
            "• **Discipline & Rules**: Enforces student code of conduct across academic faculties, campus grounds, and hostels.\n"
            "• **Anti-Ragging Supervision**: Conducts continuous inspections and orientations to ensure a zero-tolerance ragging-free campus.\n"
            "• **Dispute Resolution**: Investigates campus incidents and safeguards student safety and rights.\n"
            "• **Leadership**: Headed by the Proctor, Dr. Neeraj Shukla (+91-9451383900, proctor@kmclu.ac.in), supported by 15 Assistant Proctors across faculties."
        ),
        'source': 'Student Support and Committees',
        'action_link': {'label': 'View Campus Contacts', 'url': '/student/contacts'},
        'entity': 'proctor'
    }

def get_answer_for_sgrc(q_norm):
    """Precision answer for Student Grievance Redressal Committee and Ombudsperson."""
    return {
        'answer': (
            "Student grievances at KMCLU are formally handled by statutory bodies established per UGC regulations:\n\n"
            "• **Students' Grievance Redressal Committee (SGRC)**: Resolves student concerns regarding admissions, academic evaluations, facilities, and administration.\n"
            "• **Chairperson**: Prof. Masood Alam, Professor, Department of Arabic (Phone: +91-9559840136).\n"
            "• **Committee Members**: Includes Dean of Academic Affairs, Chief Proctor, Dean of Students' Welfare (DSW), and student representatives.\n"
            "• **Lokpal / Ombudsperson**: Provides independent institutional review if an issue remains unresolved.\n"
            "• **Women's Complaints**: Handled specifically by the Internal Complaints Committee (ICC) in compliance with NCW and Vishaka guidelines."
        ),
        'source': 'Students Grievance Redressal Committee (SGRC)',
        'action_link': {'label': 'Campus Directory', 'url': '/student/contacts'},
        'entity': 'sgrc'
    }

def get_answer_for_btech(q_norm):
    """Precision answer for B.Tech / CSE fees and course structure."""
    return {
        'answer': (
            "Annual tuition fee for all B.Tech programmes at KMCLU Faculty of Engineering & Technology is ₹87,650 per year (8 semesters, self-finance mode, admission via Written Test):\n\n"
            "• **B.Tech Computer Science and Engineering (CSE)**: 120 seats\n"
            "• **B.Tech CSE (Artificial Intelligence & Machine Learning)**: 60 seats\n"
            "• **B.Tech CSE (Artificial Intelligence & Data Science)**: 60 seats\n"
            "• **B.Tech CSE (Cyber Security)**: 60 seats\n"
            "• **Core Branches**: Automation & Robotics, Biotechnology, Civil Engineering, and Mechanical Engineering (60 seats each, all ₹87,650/year).\n\n"
            "Admission is conducted through the KMCLU entrance test / counseling process."
        ),
        'source': 'Academic Programmes and Fees 2026-27',
        'entity': 'btech'
    }

def get_answer_for_bca_mca(q_norm):
    """Precision answer for BCA / MCA fees and details."""
    if 'mca' in q_norm:
        return {
            'answer': (
                "**M.C.A. (Master of Computer Applications)** at KMCLU:\n\n"
                "• **Duration**: 4 semesters (self-finance)\n"
                "• **Seats**: 60\n"
                "• **Annual Fee**: ₹81,600\n"
                "• **Admission**: Via Written Test (CUET / NTA or other relevant exam)\n"
                "• **Faculty**: Faculty of Science"
            ),
            'source': 'Academic Programmes and Fees 2026-27',
            'entity': 'mca'
        }
    return {
        'answer': (
            "**B.C.A. (Bachelor of Computer Applications)** at KMCLU:\n\n"
            "• **Duration**: 6 semesters\n"
            "• **Seats**: 60\n"
            "• **Annual Fee**: ₹34,600 (self-finance: ₹45,600)\n"
            "• **Admission**: Via Written Test\n"
            "• **Faculty**: Faculty of Science"
        ),
        'source': 'Academic Programmes and Fees 2026-27',
        'entity': 'bca'
    }

def get_answer_for_bba_mba(q_norm):
    """Precision answer for BBA / MBA fees and details."""
    if 'mba' in q_norm:
        return {
            'answer': (
                "**M.B.A. (Master of Business Administration)** at KMCLU:\n\n"
                "• **Duration**: 4 semesters\n"
                "• **Seats**: 60\n"
                "• **Annual Fee**: ₹57,850 (self-finance: ₹81,600)\n"
                "• **Admission**: Via Written Test (CUET / CAT / NTA / CMAT / MAT or relevant exam)\n"
                "• **Faculty**: Faculty of Commerce"
            ),
            'source': 'Academic Programmes and Fees 2026-27',
            'entity': 'mba'
        }
    return {
        'answer': (
            "**B.B.A. (Bachelor of Business Administration)** at KMCLU:\n\n"
            "• **Duration**: 6 semesters (self-finance)\n"
            "• **Seats**: 120\n"
            "• **Annual Fee**: ₹43,600\n"
            "• **Admission**: Via Written Test\n"
            "• **Faculty**: Faculty of Commerce"
        ),
        'source': 'Academic Programmes and Fees 2026-27',
        'entity': 'bba'
    }

def get_answer_for_ba_ma(q_norm):
    """Precision answer for B.A. / M.A. fees and details."""
    if 'ma' in q_norm and 'ba' not in q_norm:
        return {
            'answer': (
                "**M.A. Programmes** at KMCLU (Faculty of Arts & Humanities):\n\n"
                "• M.A. Urdu, Arabic, Persian, English: 30-60 seats, ₹16,750/year\n"
                "• M.A. Hindi, Sanskrit (self-finance): 30 seats, ₹19,450/year\n\n"
                "**M.A. Programmes** (Faculty of Social Science):\n"
                "• M.A. Geography, Home Science, Education, History: 30-60 seats, ₹16,750/year\n"
                "• M.A. Political Science, Economics, Sociology, Fine Arts (self-finance): 30 seats, ₹19,450/year\n"
                "• M.A. JMC: 30 seats, ₹27,750/year\n\n"
                "Admission is based on Merit (qualifying exam marks)."
            ),
            'source': 'Academic Programmes and Fees 2026-27',
            'entity': 'ma'
        }
    return {
        'answer': (
            "**B.A. Programmes** at KMCLU:\n\n"
            "**Faculty of Arts and Humanities** (6/8 semesters, Merit-based):\n"
            "• B.A. Urdu, Arabic, Persian, English, Hindi, Japanese: 60 seats each, ₹12,700/year\n"
            "• B.A. Awadhi, Sanskrit, French, German, Chinese, Pali (self-finance): 30 seats each, ₹15,500/year\n\n"
            "**Faculty of Social Science**:\n"
            "• B.A. History, Economics, Political Science, Education, Geography, JMC: 60 seats, ₹12,700/year\n"
            "• B.A. Sociology, Psychology, Fine Arts, Music-Vocal, Physical Education (self-finance): 30-60 seats, ₹15,500/year\n"
            "• B.Ed.: 100 seats, ₹27,975/year (via UP B.Ed. JEE 2026)\n\n"
            "Admission is based on Merit (qualifying exam marks)."
        ),
        'source': 'Academic Programmes and Fees 2026-27',
        'entity': 'ba'
    }

def get_answer_for_bcom_mcom(q_norm):
    """Precision answer for B.Com / M.Com fees and details."""
    if 'mcom' in q_norm:
        return {
            'answer': (
                "**M.Com.** at KMCLU:\n\n"
                "• **Duration**: 4 semesters\n"
                "• **Seats**: 60\n"
                "• **Annual Fee**: ₹17,450 (self-finance: ₹37,000)\n"
                "• **Faculty**: Faculty of Commerce\n"
                "• **Admission**: Merit-based"
            ),
            'source': 'Academic Programmes and Fees 2026-27',
            'entity': 'mcom'
        }
    return {
        'answer': (
            "**B.Com.** at KMCLU:\n\n"
            "• **Duration**: 6 semesters\n"
            "• **Seats**: 60\n"
            "• **Annual Fee**: ₹14,700 (self-finance variant: ₹30,700)\n"
            "• **B.Com. Travel & Tourism Management** (self-finance): 30 seats, ₹30,700\n"
            "• **B.Com. Retail Operations Management** (degree-apprenticeship): 60 seats, ₹30,700\n"
            "• **Faculty**: Faculty of Commerce\n"
            "• **Admission**: Merit-based"
        ),
        'source': 'Academic Programmes and Fees 2026-27',
        'entity': 'bcom'
    }

def get_answer_for_law(q_norm):
    """Precision answer for Law programmes."""
    return {
        'answer': (
            "**Faculty of Legal Studies** at KMCLU:\n\n"
            "• **B.A. LL.B.** (self-finance): 10 semesters, 60 seats, ₹54,250/year, Merit-based\n"
            "• **LL.B.** (self-finance): 6 semesters, 60 seats, ₹30,700/year, Merit-based\n"
            "• **LL.M.** (self-finance): 4 semesters, 60 seats, ₹83,100/year, Merit-based"
        ),
        'source': 'Academic Programmes and Fees 2026-27',
        'entity': 'law'
    }

def get_answer_for_pharmacy(q_norm):
    """Precision answer for Pharmacy programmes."""
    return {
        'answer': (
            "**Faculty of Pharmacy** at KMCLU (established 2023 under PCI approval):\n\n"
            "• **B.Pharm**: 8 semesters (self-finance), 60 seats, ₹87,600/year, Written Test\n"
            "• **D.Pharm**: 2 years (self-finance), 60 seats, ₹74,800/year, Written Test\n"
            "• **B.Pharm Lateral Entry** (2nd year, for D.Pharm holders): 6 seats, Written Test\n\n"
            "Entrance exams: CUET / JEECUP or other relevant exam."
        ),
        'source': 'Academic Programmes and Fees 2026-27',
        'entity': 'pharmacy'
    }



def get_answer_for_library_timings():
    """Precision answer for Library timings."""
    return {
        'answer': (
            "Pt. Ram Prasad Bismil Central Library timings:\n\n"
            "• **Library & Reading Room Hours**: 8:00 AM - 8:00 PM (Monday through Saturday; closed on Sundays and university holidays).\n"
            "• **Circulation Counter (Borrow / Return)**: 10:30 AM - 3:30 PM on working days.\n"
            "• **Staff Lunch Break**: 2:00 PM - 3:00 PM.\n"
            "• **Borrowing Privileges**: Enrolled students can borrow up to 3 books for 14 days."
        ),
        'source': 'Library Rules and Membership',
        'entity': 'library'
    }

def get_answer_for_library_location():
    """Precision answer for Library location and facilities."""
    return {
        'answer': (
            "The Pt. Ram Prasad Bismil Central Library is situated in the main academic complex adjacent to the Abul Kalam Azad Academic Block.\n\n"
            "• **Resources**: Houses over 28,700 volumes, print periodicals, and subscriptions to digital databases.\n"
            "• **Facilities**: Multi-floor air-conditioned reading halls, dedicated study cubicles, high-speed Wi-Fi, and e-library access via Knimbus.\n"
            "• **Timings**: 8:00 AM - 8:00 PM on working days."
        ),
        'source': '06-infrastructure-and-facilities.md',
        'action_link': {'label': 'View Campus Map', 'url': '/student/map'},
        'entity': 'library'
    }

def get_answer_for_university_timings():
    """Precision answer for University office and academic timings."""
    return {
        'answer': (
            "KMCLU general university and academic timings:\n\n"
            "• **Academic & Administrative Offices**: 10:00 AM - 5:00 PM (Monday through Saturday on working days).\n"
            "• **Central Library**: 8:00 AM - 8:00 PM (Circulation counter: 10:30 AM - 3:30 PM).\n"
            "• **Hostel Hours**: Gates open at 6:00 AM; last entry for resident students is 10:00 PM.\n"
            "• **Community Health Centre**: 24-hour OPD with round-the-clock nursing care."
        ),
        'source': 'University Timings and Schedule',
        'entity': 'university'
    }

def get_answer_for_naac():
    """Precision answer for NAAC grade explaining conflicting figures without hallucination."""
    return {
        'answer': (
            "KMCLU's available university documentation contains different accreditation figures from different periods. "
            "The records available to me mention B++ with CGPA 2.86, while an earlier document mentions B. "
            "I cannot determine the current official grade from these records alone. "
            "Please verify with the Internal Quality Assurance Cell (IQAC) or Registrar office for the latest certificate."
        ),
        'source': 'University Overview (Accreditation Records)',
        'entity': 'naac'
    }

def get_answer_for_clubs():
    """Precision answer for extracurricular clubs and bodies."""
    return {
        'answer': (
            "KMCLU offers several active co-curricular and student organizations:\n\n"
            "• **National Service Scheme (NSS)**: 8 active units focused on community service, literacy (Pathshala), and health camps (Coordinator: Dr. Nalini Mishra).\n"
            "• **National Cadet Corps (NCC)**: Girls unit affiliated with 20 UP Girls Battalion NCC, 80 cadet capacity, drill and leadership training (Founder ANO: Dr. Bushra Alvera).\n"
            "• **Rovers & Rangers**: Scouting, outdoor survival skills, and civic service (Nodal Officer: Dr. Udham Singh).\n"
            "• **Cultural Committee**: Conducts inter-collegiate youth festivals, COSAC, Foundation Day, music, drama, and debating.\n"
            "• **Pathshala**: Student-run volunteer teaching school for underprivileged children from neighbouring localities."
        ),
        'source': 'Student Support and Committees',
        'entity': 'clubs'
    }

def get_answer_for_all_programmes(q_norm):
    """Precision answer for broad course/programme listing queries.
    Reads the actual programmes file and returns a structured faculty-wise summary."""
    return {
        'answer': (
            "KMCLU offers 98+ programmes across 7 faculties for the 2026-27 session. Here is a summary by faculty:\n\n"
            "**Faculty of Arts and Humanities**\n"
            "UG: B.A. in Urdu, Arabic, Persian, English, Hindi, Awadhi, Sanskrit, French, German, Chinese, Japanese, Pali (₹12,700-₹15,500/year)\n"
            "PG: M.A. in Urdu, Arabic, Persian, English, Hindi, Sanskrit (₹16,750-₹19,450/year)\n"
            "Diploma/Certificate: PG Diploma in JMC (Urdu), Arabic Translation, French Proficiency, and more\n\n"
            "**Faculty of Commerce**\n"
            "UG: B.Com. (₹14,700), B.Com. Travel & Tourism, B.B.A. (₹43,600, Written Test, 120 seats)\n"
            "PG: M.Com. (₹17,450), M.B.A. (₹57,850, Written Test)\n"
            "Diploma: GST, Capital Market, Financial Modeling, Entrepreneurship\n\n"
            "**Faculty of Social Science**\n"
            "UG: B.A. in History, Economics, Political Science, Education, Geography, Sociology, Psychology, Fine Arts, JMC, B.Ed. (₹12,700-₹27,975)\n"
            "PG: M.A. in Geography, Home Science, Education, History, Political Science, Economics, Sociology, JMC, Fine Arts\n\n"
            "**Faculty of Science**\n"
            "UG: B.C.A. (₹34,600, Written Test), B.Sc. in Chemistry, Computer Science, Zoology, Botany, Microbiology, Physics, Mathematics, Statistics, Biotechnology (₹36,300/year)\n"
            "PG: M.C.A. (₹81,600, Written Test), M.Sc. in Home Science, Microbiology, Biotechnology, Zoology\n\n"
            "**Faculty of Engineering & Technology** (all ₹87,650/year, Written Test)\n"
            "UG: B.Tech in CSE (120 seats), CSE-AI&DS, CSE-AI&ML, CSE-Cyber Security, Civil, Mechanical, Automation & Robotics, Biotechnology (60 seats each)\n"
            "PG: M.Tech CSE (AI/ML), Mechatronics, Biotechnology, Structural Engineering (₹89,850)\n\n"
            "**Faculty of Legal Studies**\n"
            "B.A. LL.B. (₹54,250, 10 semesters), LL.B. (₹30,700, 6 semesters), LL.M. (₹83,100)\n\n"
            "**Faculty of Pharmacy**\n"
            "B.Pharm (₹87,600, Written Test), D.Pharm (₹74,800, Written Test)\n\n"
            "For detailed seat counts and eligibility for a specific programme, ask me about that programme (e.g. 'BTech fees' or 'BCA eligibility')."
        ),
        'source': 'Academic Programmes and Fees 2026-27',
        'entity': 'programmes'
    }


def format_retrieved_chunk_answer(chunk):
    """Format a retrieved markdown chunk into a clean, student-friendly answer."""
    content = chunk['content']
    content = re.sub(r'_Last updated:[^_]+_', '', content)
    content = re.sub(r'^#+\s+[^\n]*\n?', '', content)
    content = clean_no_em_dash(content)
    content = re.sub(r'\n{3,}', '\n\n', content).strip()

    title = chunk.get('section_title') or chunk.get('doc_title')
    source_name = chunk.get('file_name', 'University Records')

    answer_text = f"**{title}**\n\n{content}"
    return {
        'answer': answer_text,
        'source': source_name,
        'entity': chunk.get('doc_title', '').lower()[:20]
    }


# ─────────────────────────────────────────────────────────────
# 6. SCOPED WEB FALLBACK (DUCKDUCKGO HTML)
# ─────────────────────────────────────────────────────────────

class _RateLimiter:
    """In-memory token bucket rate limiter."""
    def __init__(self, max_tokens=10, refill_rate=1.0):
        self._max = max_tokens
        self._tokens = float(max_tokens)
        self._rate = refill_rate
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def allow(self):
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._max, self._tokens + elapsed * self._rate)
            self._last = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

_web_limiter = _RateLimiter(max_tokens=10, refill_rate=1/6.0)

_UNIVERSITY_TOPICS = [
    'university', 'college', 'campus', 'academic', 'admission', 'semester',
    'examination', 'exam', 'syllabus', 'curriculum', 'degree', 'diploma',
    'naac', 'ugc', 'aicte', 'accreditation', 'scholarship', 'hostel',
    'library', 'faculty', 'professor', 'department', 'convocation',
    'kmclu', 'placement', 'internship', 'research', 'phd', 'thesis',
    'education', 'student', 'teacher', 'lecture', 'course', 'programme',
    'eligibility', 'enrollment', 'registration', 'fee', 'fees', 'tuition',
    'nep', 'iqac', 'registrar', 'proctor', 'warden', 'dean', 'khwaja',
]

def _is_university_related(q_norm):
    """Check if the normalised query is plausibly university/education-related."""
    return any(topic in q_norm for topic in _UNIVERSITY_TOPICS)

def _web_search_fallback(q_norm, raw_query):
    """
    Perform a scoped web search via DuckDuckGo for university-related queries.
    Returns a dict with 'answer' and 'source' or None if nothing useful found.
    Clearly labeled with web search disclaimer.
    """
    if not _is_university_related(q_norm):
        return None

    if not _web_limiter.allow():
        logger.warning('Web fallback rate limit exceeded')
        return None

    try:
        search_query = f"KMCLU Lucknow {raw_query}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        }

        resp = _requests.post(
            'https://html.duckduckgo.com/html/',
            data={'q': search_query},
            headers=headers,
            timeout=7
        )

        if resp.status_code != 200:
            resp = _requests.post(
                'https://lite.duckduckgo.com/lite/',
                data={'q': search_query},
                headers=headers,
                timeout=7
            )

        if resp.status_code != 200:
            return None

        html_text = resp.text
        snippets = []

        GENERIC_WEB_TERMS = {
            'kmclu', 'lucknow', 'university', 'college', 'campus', 'syllabus', 'exam',
            'examination', 'programme', 'programmes', 'course', 'courses', 'admission',
            'admissions', 'fee', 'fees', 'hostel', 'library', 'department', 'faculty',
            'student', 'students', 'what', 'is', 'the', 'for', 'in', 'at', 'of', 'and',
            'a', 'an', 'to', 'research', 'study', 'education', 'learning', 'academic'
        }
        raw_tokens = set(re.findall(r'[a-z0-9]+', raw_query.lower()))
        distinctive_query_words = raw_tokens - GENERIC_WEB_TERMS

        # Match snippets
        matches = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html_text, re.DOTALL | re.IGNORECASE)
        if not matches:
            matches = re.findall(r'class=[\'"]result-snippet[\'"][^>]*>(.*?)</td>', html_text, re.DOTALL | re.IGNORECASE)

        for match in matches[:5]:
            clean_text = re.sub(r'<[^>]+>', '', match).strip()
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            clean_text = clean_no_em_dash(clean_text)
            if len(clean_text) > 25:
                if distinctive_query_words:
                    snippet_tokens = set(re.findall(r'[a-z0-9]+', clean_text.lower()))
                    if not distinctive_query_words.intersection(snippet_tokens):
                        continue
                snippets.append(clean_text)

        if not snippets:
            return None

        answer_parts = ["Based on publicly available web sources, here is what I found:\n"]
        for snippet in snippets[:3]:
            answer_parts.append(f"• {snippet}")

        answer_parts.append(
            "\n**Note**: (Found via external web search - not from verified local university records. "
            "Please verify with the relevant university office for authoritative confirmation.)"
        )

        return {
            'answer': '\n'.join(answer_parts),
            'source': 'External Web Search (unverified)',
            'web_sourced': True,
            'entity': None,
        }

    except Exception as e:
        logger.debug('Web fallback error: %s', e)
        return None


# ─────────────────────────────────────────────────────────────
# 7. SINGLE QUERY ROUTING (INTERNAL PIPELINE)
# ─────────────────────────────────────────────────────────────

def _internal_answer_single_query(query, history=None):
    """
    Route and retrieve answer for a single atomic query.
    1. Check conversational context / pronouns
    2. Check greetings, identity, builder
    3. Check out-of-scope guard
    4. Check ambiguity
    5. Check live MongoDB data
    6. Check precision rules (NSS, BTech, Proctor, Library, SGRC, NAAC)
    7. Query grounded KB chunk index
    8. Returns answer dict or None
    """
    if not query or not query.strip():
        return None

    raw_query = query.strip()
    history = history or []

    # 1. Pronoun and Context Resolution
    resolved_query, context_entity = resolve_contextual_query(raw_query, history)
    q_norm = resolved_query

    # 2. Builder / Creator Intent
    if any(k in q_norm for k in ['who built you', 'who created you', 'who made you', 'who made avora', 'who built avora', 'creator of avora', 'builder', 'developer of avora', 'who are the developers']):
        return {
            'answer': "Avora was designed and built by Abhimanyu Singh and Prakhar Srivastava for Khwaja Moinuddin Chishti Language University (KMCLU). You can connect with Abhimanyu Singh on LinkedIn: https://www.linkedin.com/in/abhimanyusingh0111/",
            'source': 'Avora Platform Builders',
            'clarification_options': None,
            'entity': 'builders'
        }

    # 3. Casual Conversation & Polite Greetings
    greetings = ['hi', 'hello', 'hey', 'good morning', 'good evening', 'good afternoon', 'namaste', 'salam']
    if q_norm in greetings or (len(q_norm.split()) <= 2 and any(q_norm.startswith(g) for g in greetings)):
        return {
            'answer': "Hello! I am Avora, your campus knowledge assistant. How can I assist you today with KMCLU academics, admissions, library rules, or campus facilities?",
            'source': None,
            'clarification_options': ['How to join NSS', 'BTech fees', 'Library timings', 'Active campus elections'],
            'entity': 'greeting'
        }

    thanks = ['thanks', 'thank you', 'thank u', 'thx', 'dhanyawad', 'shukriya', 'ok thanks', 'okay thanks']
    if q_norm in thanks or any(q_norm == t for t in thanks):
        return {
            'answer': "You are welcome! Feel free to ask if you need any other information regarding KMCLU academics, facilities, or campus services.",
            'source': None,
            'clarification_options': None,
            'entity': 'thanks'
        }

    acknowledgements = ['ok', 'okay', 'alright', 'got it', 'fine', 'sure', 'understood', 'theek hai']
    if q_norm in acknowledgements:
        return {
            'answer': "Glad to help! Let me know whenever you have another question.",
            'source': None,
            'clarification_options': None,
            'entity': 'ack'
        }

    identity = ['who are you', 'what are you', 'what is avora', 'introduce yourself', 'your name']
    if any(k in q_norm for k in identity):
        return {
            'answer': "I am Avora, the digital knowledge assistant for Khwaja Moinuddin Chishti Language University (KMCLU), Lucknow. I can help you with factual university information such as admissions, programmes, fees, library rules, committees, campus contacts, and live platform elections.",
            'source': 'Avora Campus Platform',
            'clarification_options': ['Library timings', 'BTech fees', 'How to join NSS', 'Campus contacts'],
            'entity': 'identity'
        }

    # 4. Out-of-Scope / Unsupported Guard (Zero Hallucination)
    unrelated_topics = [
        'recipe', 'cake', 'pasta', 'crypto', 'bitcoin', 'ethereum', 'stock market', 'cricket score',
        'ipl score', 'football score', 'movie review', 'hollywood', 'bollywood movie',
        'minecraft', 'gta', 'weather forecast in london', 'jokes', 'tell me a joke', 'dating'
    ]
    if any(topic in q_norm for topic in unrelated_topics):
        return {
            'answer': "That's outside what I can help with. I can help with KMCLU academics, campus services, facilities, notices, elections, contacts, and other university information.",
            'source': None,
            'clarification_options': None,
            'entity': None
        }

    # 5. Ambiguity Handling
    tokens = q_norm.split()

    # Vague Timings
    if q_norm in ['timings', 'timing', 'time', 'hours', 'schedule', 'college timing', 'university timing'] or (len(tokens) <= 2 and 'timing' in tokens and not any(k in q_norm for k in ['library', 'hostel', 'office', 'exam', 'class'])):
        if 'university' in q_norm:
            return get_answer_for_university_timings()
        return {
            'answer': "Which timings do you need? Please select an option below:",
            'source': None,
            'clarification_options': ['Library Timings', 'University Office & Academic Hours', 'Hostel Timings & Curfew'],
            'entity': 'timings_clarification'
        }

    # Vague Fees
    if q_norm in ['fees', 'fee', 'fees structure', 'fee structure', 'tuition', 'kitni fees'] or (len(tokens) == 1 and tokens[0] in ['fee', 'fees', 'tuition']):
        return {
            'answer': "Which programme's fee structure are you looking for? Please select an option below or specify your course:",
            'source': None,
            'clarification_options': ['BTech Fees', 'BCA / MCA Fees', 'BBA / MBA Fees', 'Hostel Fees', 'B.A. / M.A. Fees'],
            'entity': 'fees_clarification'
        }

    # Vague Contact
    if q_norm in ['contact', 'contacts', 'phone number', 'email', 'helpline', 'whom to contact', 'directory']:
        return {
            'answer': "Which office or service do you want to contact? Please select from the primary departments below:",
            'source': None,
            'clarification_options': ['Proctorial Board Contact', 'Student Grievances (SGRC)', 'Admissions Office', 'Dean Students Welfare (DSW)', 'Placement Cell'],
            'entity': 'contact_clarification'
        }

    # Vague Admissions
    if q_norm in ['admission', 'admissions', 'apply', 'how to apply', 'admission form']:
        return {
            'answer': "What information regarding admissions would you like to know?",
            'source': None,
            'clarification_options': ['Admissions Process 2026-27', 'Eligibility and Reservation', 'BTech Programmes and Intake', 'Samarth Portal Incharge'],
            'entity': 'admission_clarification'
        }

    # Vague Hostel
    if q_norm in ['hostel', 'hostels', 'hostel admission', 'hostel facility']:
        return {
            'answer': "What information regarding university hostels do you need?",
            'source': None,
            'clarification_options': ['Hostel Fees and Capacity', 'Hostel Timings and Rules', 'Girls Hostel (Rani Laxmi Bai)'],
            'entity': 'hostel_clarification'
        }

    # 6. Live MongoDB Checks (Elections, Notices, Lost & Found)
    live_result = search_live_data(q_norm)
    if live_result:
        return live_result

    # 7. Precision Fast-Path Rules
    if any(k in q_norm for k in ['nss', 'national service scheme', 'community service']) and not any(k in q_norm for k in ['sgrc', 'proctor']):
        return get_answer_for_nss(q_norm)

    if any(k in q_norm for k in ['btech', 'cse fee', 'cse fees', 'computer science fee', 'engineering fee', 'engineering fees', 'btech fee', 'btech fees']):
        return get_answer_for_btech(q_norm)

    if any(k in q_norm for k in ['bca', 'mca', 'computer application']):
        return get_answer_for_bca_mca(q_norm)

    if any(k in q_norm for k in ['bba', 'mba', 'business administration']):
        return get_answer_for_bba_mba(q_norm)

    if any(k in q_norm for k in ['bcom', 'mcom', 'bcom fee', 'mcom fee']):
        return get_answer_for_bcom_mcom(q_norm)

    # BA/MA — only trigger when explicitly asking about BA or MA programmes
    if any(k in q_norm for k in ['ba fee', 'ba fees', 'ba programme', 'ba course', 'ma fee', 'ma fees', 'ma programme', 'ma course', 'ba admission', 'ma admission']):
        return get_answer_for_ba_ma(q_norm)

    if any(k in q_norm for k in ['law', 'llb', 'llm', 'legal studies']):
        return get_answer_for_law(q_norm)

    if any(k in q_norm for k in ['pharmacy', 'bpharm', 'dpharm', 'pharm fee', 'pharm fees', 'pci']):
        return get_answer_for_pharmacy(q_norm)

    if 'library' in q_norm and any(k in q_norm for k in ['timing', 'timings', 'time', 'hours', 'open', 'close', 'schedule', 'when does']):
        return get_answer_for_library_timings()

    if 'library' in q_norm and any(k in q_norm for k in ['where', 'location', 'reach', 'find', 'block', 'building', 'located']):
        return get_answer_for_library_location()

    if any(k in q_norm for k in ['university timing', 'university timings', 'academic hours', 'office hours', 'college timing', 'office timing', 'working hours']):
        return get_answer_for_university_timings()

    if any(k in q_norm for k in ['naac', 'accreditation', 'naac grade', 'cgpa']):
        return get_answer_for_naac()

    if any(k in q_norm for k in ['proctor', 'proctorial', 'discipline', 'student discipline', 'anti ragging', 'anti-ragging', 'ragging', 'neeraj shukla']):
        return get_answer_for_proctor(q_norm)

    if any(k in q_norm for k in ['grievance', 'grievances', 'sgrc', 'lokpal', 'ombudsperson', 'icc']):
        return get_answer_for_sgrc(q_norm)

    if any(k in q_norm for k in ['club', 'clubs', 'extra curricular', 'extracurricular', 'activities', 'ncc', 'rovers', 'rangers', 'cultural committee']):
        return get_answer_for_clubs()

    # 7b. Precision handler for broad course/programme listing queries
    course_query_words = ['course', 'courses', 'programme', 'programmes', 'program', 'programs', 'offered', 'available courses', 'all courses', 'list of courses', 'what courses']
    if any(k in q_norm for k in course_query_words) and not any(k in q_norm for k in ['btech', 'bca', 'mca', 'bba', 'mba', 'bcom', 'mcom', 'ba ', 'ma ', 'bsc', 'msc', 'llb', 'pharm']):
        return get_answer_for_all_programmes(q_norm)

    # 8. Grounded Knowledge Base Semantic Retrieval
    kb = get_kb_index()
    results = kb.retrieve(q_norm, top_k=2)

    MIN_RELEVANCE_SCORE = 0.18
    if results:
        best_score, best_chunk = results[0]
        if best_score >= MIN_RELEVANCE_SCORE:
            return format_retrieved_chunk_answer(best_chunk)

    return None


# ─────────────────────────────────────────────────────────────
# 8. REASONING LAYER (COMPOUND QUERIES & SYNTHESIS)
# ─────────────────────────────────────────────────────────────

def _decompose_complex_query(raw_query, q_norm):
    """
    Decompose multi-part queries into atomic sub-questions.
    E.g. 'Can I join NSS and what is the fee for BTech CSE?' -> ['Can I join NSS', 'what is the fee for BTech CSE']
    """
    # 1. Check multiple question marks
    if '?' in raw_query:
        parts = [p.strip() for p in raw_query.split('?') if p.strip()]
        if len(parts) >= 2:
            return parts

    # 2. Check conjunction connectors
    conjunction_pattern = r'\s+(?:and\s+also|and|as\s+well\s+as|along\s+with|plus|aur|tatha)\s+'
    parts = re.split(conjunction_pattern, raw_query, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if len(p.strip().split()) >= 2]
    if len(parts) >= 2:
        return parts

    return []


# ─────────────────────────────────────────────────────────────
# 9. PUBLIC API INTERFACE (answer_query)
# ─────────────────────────────────────────────────────────────

def answer_query(query, history=None):
    """
    Main Ask Avora public interface.

    Execution Pipeline:
    1. Normalize query and resolve multi-turn pronouns.
    2. Check for multi-part compound queries (Reasoning Layer).
    3. If atomic: try local pipeline (Precision Handlers + Live MongoDB + Grounded KB Chunks).
    4. If compound: decompose, answer each sub-query, and synthesize structured response.
    5. If local retrieval yields no relevant results:
       a. Check if university-related -> execute scoped DuckDuckGo web fallback.
       b. Clearly label web-derived answers.
    6. If neither local nor web fallback has an answer:
       a. Return honest no-hallucination fallback with contact routing.
    7. Clean output of all em dashes and format nicely.
    """
    if not query or not query.strip():
        return {
            'answer': "Please enter a question regarding KMCLU courses, admissions, library guidelines, committees, or campus facilities.",
            'source': None,
            'clarification_options': None,
            'entity': None
        }

    raw_query = query.strip()
    history = history or []
    q_norm = normalize_query(raw_query)

    # Multi-part query decomposition
    sub_queries = _decompose_complex_query(raw_query, q_norm)
    if sub_queries and len(sub_queries) >= 2:
        sub_results = []
        for sq in sub_queries:
            res = _internal_answer_single_query(sq, history=history)
            if res and res.get('answer'):
                sub_results.append((sq, res))

        if len(sub_results) >= 2:
            # Multi-part synthesis
            sections = ["Here is the information for both of your questions:\n"]
            all_sources = []
            for i, (sq, res) in enumerate(sub_results, 1):
                clean_ans = res['answer'].strip()
                sections.append(f"**{i}. {sq.capitalize()}:**\n{clean_ans}\n")
                if res.get('source'):
                    all_sources.append(res['source'])

            combined_answer = '\n'.join(sections).strip()
            unique_sources = list(dict.fromkeys(all_sources))

            synthesized = {
                'answer': clean_no_em_dash(combined_answer),
                'source': clean_no_em_dash(', '.join(unique_sources)) if unique_sources else None,
                'clarification_options': None,
                'entity': sub_results[0][1].get('entity')
            }
            # Carry forward action link if present
            for _, r in sub_results:
                if r.get('action_link'):
                    synthesized['action_link'] = r['action_link']
                    break
            return synthesized

    # Single atomic query flow
    local_res = _internal_answer_single_query(raw_query, history=history)
    if local_res is not None:
        if isinstance(local_res, dict):
            if 'answer' in local_res and isinstance(local_res['answer'], str):
                local_res['answer'] = clean_no_em_dash(local_res['answer'])
            if 'source' in local_res and isinstance(local_res['source'], str):
                local_res['source'] = clean_no_em_dash(local_res['source'])
        return local_res

    # Scoped Web Fallback
    web_res = _web_search_fallback(q_norm, raw_query)
    if web_res:
        if 'answer' in web_res and isinstance(web_res['answer'], str):
            web_res['answer'] = clean_no_em_dash(web_res['answer'])
        return web_res

    # No-Hallucination Honest Fallback
    return {
        'answer': (
            "I couldn't find verified information on this topic in KMCLU's knowledge base or external sources. "
            "Please check with the respective department office (e.g. reg@kmclu.ac.in, admission@kmclu.ac.in) "
            "or visit kmclu.ac.in for the latest circulars."
        ),
        'source': None,
        'clarification_options': ['Campus Directory Contacts', 'Latest Notices & Circulars', 'Admissions Helpdesk'],
        'action_link': {'label': 'Open Campus Contacts', 'url': '/student/contacts'},
        'entity': None
    }
