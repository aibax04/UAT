from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from workflows.graph import workflow
from db import get_db
import os
import threading
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Store active runs
active_runs = {}

def run_test_async(run_id, app_name, start_url, username=None, password=None):
    """Run the test in a background thread"""
    try:
        active_runs[run_id]['status'] = 'running'
        active_runs[run_id]['progress'] = 'Initializing...'
        
        # Add credentials to database if provided
        if username and password:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM credentials WHERE app_name = ?", (app_name,))
            cursor.execute("""
                INSERT INTO credentials (app_name, login_url, username, password)
                VALUES (?, ?, ?, ?)
            """, (app_name, start_url, username, password))
            conn.commit()
            conn.close()
        
        # Run the workflow
        result = workflow.invoke({
            "app_name": app_name,
            "start_url": start_url
        })
        
        active_runs[run_id]['status'] = 'completed'
        active_runs[run_id]['progress'] = 'Analysis complete!'
        active_runs[run_id]['report'] = result.get('report', 'No report generated')
        active_runs[run_id]['run_db_id'] = result.get('run_id')
        
    except Exception as e:
        active_runs[run_id]['status'] = 'failed'
        active_runs[run_id]['progress'] = f'Error: {str(e)}'
        active_runs[run_id]['error'] = str(e)

@app.route('/api/start-test', methods=['POST'])
def start_test():
    """Start a new UX/QA test"""
    data = request.json
    
    url = data.get('url')
    username = data.get('username')
    password = data.get('password')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    # Generate app name from URL
    app_name = url.split('//')[1].split('/')[0].replace('.', '_')
    
    # Create run ID
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Initialize run tracking
    active_runs[run_id] = {
        'status': 'starting',
        'progress': 'Starting test...',
        'url': url,
        'app_name': app_name,
        'started_at': datetime.now().isoformat()
    }
    
    # Start test in background thread
    thread = threading.Thread(
        target=run_test_async,
        args=(run_id, app_name, url, username, password)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'run_id': run_id,
        'message': 'Test started successfully'
    })

@app.route('/api/test-status/<run_id>', methods=['GET'])
def get_test_status(run_id):
    """Get the status of a running test"""
    if run_id not in active_runs:
        return jsonify({'error': 'Run not found'}), 404
    
    return jsonify(active_runs[run_id])

@app.route('/api/test-report/<run_id>', methods=['GET'])
def get_test_report(run_id):
    """Get the full report for a completed test"""
    if run_id not in active_runs:
        return jsonify({'error': 'Run not found'}), 404
    
    run_data = active_runs[run_id]
    
    if run_data['status'] != 'completed':
        return jsonify({'error': 'Test not completed yet'}), 400
    
    # Get additional data from database
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT total_pages, total_clicks, started_at, finished_at
        FROM test_runs WHERE id = ?
    """, (run_data.get('run_db_id'),))
    
    test_data = cursor.fetchone()
    
    # Get screenshots
    cursor.execute("""
        SELECT screenshot_path FROM crawl_logs 
        WHERE run_id = ?
        ORDER BY id
    """, (run_data.get('run_db_id'),))
    
    screenshots = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'run_id': run_id,
        'status': run_data['status'],
        'report': run_data.get('report', ''),
        'url': run_data['url'],
        'total_pages': test_data[0] if test_data else 0,
        'total_clicks': test_data[1] if test_data else 0,
        'started_at': test_data[2] if test_data else None,
        'finished_at': test_data[3] if test_data else None,
        'screenshots': screenshots[:10]  # Limit to first 10
    })

@app.route('/api/screenshot/<path:filename>', methods=['GET'])
def get_screenshot(filename):
    """Serve a screenshot file"""
    try:
        return send_file(filename, mimetype='image/png')
    except:
        return jsonify({'error': 'Screenshot not found'}), 404

@app.route('/api/test-history', methods=['GET'])
def get_test_history():
    """Get list of all previous tests"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, app_name, started_at, finished_at, status, total_pages, total_clicks
        FROM test_runs
        ORDER BY id DESC
        LIMIT 20
    """)
    
    tests = []
    for row in cursor.fetchall():
        tests.append({
            'id': row[0],
            'app_name': row[1],
            'started_at': row[2],
            'finished_at': row[3],
            'status': row[4],
            'total_pages': row[5],
            'total_clicks': row[6]
        })
    
    conn.close()
    
    return jsonify(tests)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    
    os.makedirs("screenshots", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    
    print(" UX/QA Automation Agent API Starting...")
    print(" Access the API at: http://localhost:5000")
    print(" Frontend should connect to: http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)