
@app.route('/api/settings/math-solver', methods=['GET'])
def get_math_solver_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    
    status = get_math_solver_status(session['user_id'])
    return jsonify({'enabled': status})

@app.route('/api/settings/math-solver', methods=['POST'])
def set_math_solver_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    
    data = request.get_json()
    enabled = data.get('enabled', False)
    
    if set_math_solver_status(session['user_id'], enabled):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Fehler beim Speichern'}), 500
