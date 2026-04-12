from flask import Blueprint, request, jsonify
from app.api.v1.auth import token_required
from app.services.search_service import SearchService

search_bp = Blueprint('search', __name__, url_prefix='/api/v1/search')

@search_bp.route('/', methods=['GET'])
@token_required
def global_search(current_user):
    """
    Perform a global full-text search across clinical indices.
    ?q=...
    """
    if current_user.role not in ['doctor', 'admin']:
        return jsonify({"error": "Unauthorized. Only clinical staff can use global search."}), 403
        
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 20))
    
    if not query:
        return jsonify([]), 200
        
    try:
        results = SearchService.global_search(query=query, limit=limit)
        return jsonify(results), 200
    except Exception as e:
        return jsonify({"error": "Search engine error", "detail": str(e)}), 500
