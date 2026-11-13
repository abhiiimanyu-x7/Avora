"""
Routes for Ask Avora AI Assistant.
"""

from flask import Blueprint, request, jsonify
from services.rag_service import answer_query

ask_avora_bp = Blueprint('ask_avora', __name__)

@ask_avora_bp.route('/ask-avora/query', methods=['POST'])
def handle_query():
    data = request.get_json(silent=True) or {}
    query = data.get('query', '')
    history = data.get('history', [])
    
    result = answer_query(query, history=history)
    return jsonify(result)
