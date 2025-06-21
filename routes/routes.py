from flask import jsonify
from app import app

def list_routes():
    """List all registered routes with their endpoints and methods."""
    routes = []
    for rule in app.url_map.iter_rules():
        methods = ','.join(rule.methods.difference(['HEAD', 'OPTIONS']))
        routes.append({
            'endpoint': rule.endpoint,
            'methods': methods,
            'rule': str(rule)
        })
    return routes

# Test route to list all routes
@app.route('/routes')
def show_routes():
    return jsonify(list_routes())
