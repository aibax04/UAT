from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from workflows.graph import workflow
from db import get_db
import os
import threading
import json
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)


active_runs = {}

def run_test_async(run_id, app_name, start_url, username=None, password=None):
    """Run the test in a background thread"""
    try:
        active_runs[run_id]['status'] = 'running'
        active_runs[run_id]['progress'] = 'Initializing...'
        
        
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
    
    
    app_name = url.split('//')[1].split('/')[0].replace('.', '_')
    
    
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    
    active_runs[run_id] = {
        'status': 'starting',
        'progress': 'Starting test...',
        'url': url,
        'app_name': app_name,
        'started_at': datetime.now().isoformat()
    }
    
    
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
    
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT total_pages, total_clicks, started_at, finished_at
        FROM test_runs WHERE id = ?
    """, (run_data.get('run_db_id'),))
    
    test_data = cursor.fetchone()
    
    
    cursor.execute("""
        SELECT screenshot_path FROM crawl_logs 
        WHERE run_id = ?
        ORDER BY id
    """, (run_data.get('run_db_id'),))
    
    screenshots = [row[0] for row in cursor.fetchall()]
    
    # Get crawl data with click counts per page
    cursor.execute("""
        SELECT url, buttons, screenshot_path, id
        FROM crawl_logs 
        WHERE run_id = ?
        ORDER BY id
    """, (run_data.get('run_db_id'),))
    
    crawl_logs = cursor.fetchall()
    
    # Get transitions count per page
    pages_data = []
    for log in crawl_logs:
        page_url = log[0]
        # Count transitions from this page
        cursor.execute("""
            SELECT COUNT(*) FROM transitions 
            WHERE run_id = ? AND from_url = ?
        """, (run_data.get('run_db_id'), page_url))
        transitions_count = cursor.fetchone()[0]
        
        pages_data.append({
            'url': page_url,
            'buttons': json.loads(log[1]) if log[1] else [],
            'screenshot': log[2],
            'transitions_count': transitions_count,
            'click_count': transitions_count  # Use transitions as click count
        })
    
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
        'screenshots': screenshots[:10],
        'pages_data': pages_data  # Add pages data with click counts
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

@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    """Chatbot endpoint using Gemini API"""
    try:
        data = request.json
        user_message = data.get('message', '')
        context = data.get('context', None)
        history = data.get('history', [])

        if not user_message:
            return jsonify({'error': 'Message is required'}), 400

        # Get Gemini API key
        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        
        if not gemini_api_key:
            return jsonify({
                'error': 'Gemini API key not configured. Please add GEMINI_API_KEY to your .env file.'
            }), 500

        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        # Build system prompt
        system_prompt = """You are a helpful AI assistant for CRAWL AI, a website analysis and UX research platform. 
Your role is to help users understand their website analysis reports and provide actionable recommendations for improving their website's user experience.

When a website analysis report is available, you should:
- Reference specific findings from the report
- Provide clear, actionable recommendations
- Explain UX/UI concepts in simple terms
- Focus on user experience improvements
- Be professional but friendly

If no report is available, you can still help with general questions about website UX/UI best practices."""

        # Build conversation context
        conversation_parts = [system_prompt]

        # Add report context if available
        if context and context.get('report'):
            report_context = f"""
Website Analysis Report Context:
- URL: {context.get('url', 'N/A')}
- Total Pages Crawled: {context.get('total_pages', 0)}
- Total Interactions: {context.get('total_clicks', 0)}
- Analysis Report:
{context.get('report', '')[:5000]}  # Limit to 5000 chars to avoid token limits

Please use this report to answer the user's questions about their website analysis.
"""
            conversation_parts.append(report_context)

        # Add chat history (last few messages for context)
        for msg in history[-6:]:  # Last 6 messages
            role = "user" if msg.get('role') == 'user' else "model"
            content = msg.get('content', '')
            if content:
                conversation_parts.append(f"{role}: {content}")

        # Add current user message
        conversation_parts.append(f"user: {user_message}")
        conversation_parts.append("model:")

        # Generate response
        full_prompt = "\n\n".join(conversation_parts)
        
        response = model.generate_content(
            full_prompt,
            generation_config={
                'temperature': 0.7,
                'top_p': 0.95,
                'top_k': 40,
                'max_output_tokens': 1024,
            }
        )

        bot_response = response.text.strip()

        return jsonify({
            'response': bot_response,
            'success': True
        })

    except Exception as e:
        print(f"Chatbot error: {str(e)}")
        return jsonify({
            'error': f'Error generating response: {str(e)}',
            'response': 'I apologize, but I encountered an error. Please try again or check if your Gemini API key is correctly configured.'
        }), 500

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