from flask import Flask, request, jsonify, send_file, render_template, make_response
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from workflows.graph import workflow
from db import get_db
from workspace.session_manager import workspace_manager
from scheduler_service import get_scheduler_service
import os
import threading
import json
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


def init_db_if_needed():
    """Initialize the database if uat.db doesn't exist or tables are missing"""
    if not os.path.exists('uat.db'):
        print("Database not found. Initializing...")
        try:
            with open('schema.sql', 'r') as f:
                schema = f.read()
            conn = get_db()
            cursor = conn.cursor()
            cursor.executescript(schema)
            conn.commit()
            conn.close()
            print("Database initialized successfully.")
        except Exception as e:
            print(f"Error initializing database: {e}")

# Initialize DB before starting scheduler
init_db_if_needed()

# Initialize scheduler service on app startup
scheduler_service = get_scheduler_service()
scheduler_service.start()
try:
    # Load existing schedules from database
    scheduler_service.load_existing_schedules()
except Exception as e:
    print(f"Warning: Failed to load schedules: {e}")


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


@app.route('/')
def index():
    """Serve the main application page"""
    return send_file('index.html')

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

When workspace task context is available, you should:
- Help users understand their task execution flow
- Explain what tasks are completed, running, or failed
- Provide insights about task workflow and execution patterns
- Help troubleshoot errors in task execution
- Answer questions about task status, workflow, and execution details

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
        
        # Add workspace task context if available
        if context and context.get('type') == 'workspace_tasks':
            task_context = context.get('task_context', {})
            task_details = context.get('task_details', [])
            
            task_context_str = f"""
Workspace Task Execution Context:
- Current Action: {task_context.get('current_action', 'N/A')}
- Total Tasks: {task_context.get('total_tasks', 0)}
- Completed: {task_context.get('completed_tasks', 0)}
- Failed: {task_context.get('failed_tasks', 0)}
- Running: {task_context.get('running_tasks', 0)}
- Pending: {task_context.get('pending_tasks', 0)}
- Session ID: {task_context.get('session_id', 'N/A')}

Task Details:
"""
            for task in task_details[:20]:  # Limit to 20 tasks
                task_str = f"- Task {task.get('id', 'N/A')}: {task.get('name', 'Unnamed')} [{task.get('status', 'unknown')}]"
                if task.get('description'):
                    task_str += f"\n  Description: {task.get('description')}"
                if task.get('error'):
                    task_str += f"\n  Error: {task.get('error')}"
                if task.get('execution_time'):
                    task_str += f"\n  Execution Time: {task.get('execution_time'):.2f}s"
                task_context_str += task_str + "\n"
            
            task_context_str += "\nPlease use this task context to answer questions about task execution, workflow, errors, and task status."
            conversation_parts.append(task_context_str)

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

# ==================== WORKSPACE ROUTES ====================

@app.route('/api/workspace/create', methods=['POST'])
def create_workspace_session():
    """Create a new workspace session"""
    data = request.json
    url = data.get('url')
    socket_id = data.get('socket_id')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        session_id = workspace_manager.create_session(url, socketio, socket_id)
        return jsonify({
            'session_id': session_id,
            'message': 'Workspace session created'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workspace/<session_id>/plan-tasks', methods=['POST'])
def plan_tasks(session_id):
    """Plan tasks from natural language instruction"""
    data = request.json
    instruction = data.get('instruction')
    auto_start = data.get('auto_start', False)  # Option to auto-start execution
    
    if not instruction:
        return jsonify({'error': 'Instruction is required'}), 400
    
    try:
        tasks = workspace_manager.plan_tasks(session_id, instruction, auto_start=auto_start)
        return jsonify({
            'tasks': tasks,
            'message': f'Planned {len(tasks)} tasks',
            'auto_started': auto_start
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workspace/<session_id>/start', methods=['POST'])
def start_execution(session_id):
    """Start task execution"""
    try:
        success = workspace_manager.start_execution(session_id)
        if success:
            return jsonify({'message': 'Execution started'})
        else:
            return jsonify({'error': 'Failed to start execution'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workspace/<session_id>/pause', methods=['POST'])
def pause_execution(session_id):
    """Pause task execution"""
    try:
        workspace_manager.pause_execution(session_id)
        return jsonify({'message': 'Execution paused'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workspace/<session_id>/resume', methods=['POST'])
def resume_execution(session_id):
    """Resume task execution"""
    try:
        workspace_manager.resume_execution(session_id)
        return jsonify({'message': 'Execution resumed'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workspace/<session_id>/stop', methods=['POST'])
def stop_execution(session_id):
    """Stop task execution"""
    try:
        workspace_manager.stop_execution(session_id)
        return jsonify({'message': 'Execution stopped'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workspace/<session_id>/input', methods=['POST'])
def provide_input(session_id):
    """Provide input for a waiting task"""
    data = request.json
    value = data.get('value')
    if not value:
        return jsonify({'error': 'Value is required'}), 400
    
    try:
        success = workspace_manager.provide_input(session_id, value)
        if success:
            return jsonify({'message': 'Input received'})
        else:
            return jsonify({'error': 'Failed to provide input or session not waiting'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workspace/<session_id>/status', methods=['GET'])
def get_session_status(session_id):
    """Get session status"""
    session = workspace_manager.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify({
        'session_id': session_id,
        'url': session['url'],
        'is_running': session['task_executor'].is_running,
        'is_paused': session['task_executor'].is_paused
    })

@app.route('/api/workspace/<session_id>/report', methods=['GET'])
def get_execution_report(session_id):
    """Get execution report with metrics and score"""
    try:
        report = workspace_manager.get_execution_report(session_id)
        if not report:
            return jsonify({'error': 'Session not found'}), 404
        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Report route removed - report is now shown inline in index.html
# Add handler for old report route to prevent WSGI errors
@app.route('/workspace/report/<session_id>')
def view_report_redirect(session_id):
    """Redirect old report route - report is now shown inline"""
    # Return a proper Flask response to prevent WSGI errors
    response = make_response("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Report - CRAWL AI</title>
        <meta http-equiv="refresh" content="0;url=/">
        <script>window.location.href = '/';</script>
    </head>
    <body style="background: #000; color: #fff; padding: 40px; text-align: center;">
        <p>Report is now shown inline. Redirecting...</p>
        <a href="/" style="color: #667eea;">Go to Home</a>
    </body>
    </html>
    """)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# ==================== WEBSOCKET EVENTS ====================

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    print(f'Client connected: {request.sid}')
    emit('connected', {'message': 'Connected to workspace server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print(f'Client disconnected: {request.sid}')

@socketio.on('join_session')
def handle_join_session(data):
    """Join a workspace session room"""
    session_id = data.get('session_id')
    if session_id:
        join_room(session_id)
        join_room(request.sid)
        emit('joined_session', {'session_id': session_id})

# ==================== Scheduled Testing API Routes ====================

@app.route('/api/scheduled-tests', methods=['GET'])
def get_scheduled_tests():
    """Get all scheduled tests"""
    try:
        schedules = scheduler_service.get_all_schedules()
        return jsonify({'schedules': schedules})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduled-tests', methods=['POST'])
def create_scheduled_test():
    """Create a new scheduled test"""
    try:
        data = request.json
        
        # Validate required fields
        if not data.get('site_url'):
            return jsonify({'error': 'site_url is required'}), 400
        if not data.get('frequency'):
            return jsonify({'error': 'frequency is required'}), 400
        
        # Extract app_name from URL for database storage
        try:
            app_name = data['site_url'].split('//')[1].split('/')[0].replace('.', '_')
        except:
            app_name = 'unknown_app'
        
        schedule_data = {
            'site_url': data['site_url'],
            'task_description': data.get('task_description', ''),
            'frequency': data['frequency'],
            'time': data.get('time'),
            'interval_hours': data.get('interval_hours'),
            'interval_minutes': data.get('interval_minutes'),
            'days_of_week': data.get('days_of_week', []),
            'date': data.get('date'),
            'enabled': data.get('enabled', True),
            'app_name': app_name,
            'notify_email': data.get('notify_email'),
            'notify_on_success': data.get('notify_on_success', False),
            'notify_on_failure': data.get('notify_on_failure', False)
        }
        
        schedule_id = scheduler_service.add_schedule(schedule_data)
        return jsonify({
            'schedule_id': schedule_id,
            'message': 'Scheduled test created successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduled-tests/<int:schedule_id>', methods=['PUT'])
def update_scheduled_test(schedule_id):
    """Update an existing scheduled test"""
    try:
        data = request.json
        
        # Validate required fields
        if not data.get('site_url'):
            return jsonify({'error': 'site_url is required'}), 400
        if not data.get('frequency'):
            return jsonify({'error': 'frequency is required'}), 400
        
        schedule_data = {
            'site_url': data['site_url'],
            'task_description': data.get('task_description', ''),
            'frequency': data['frequency'],
            'time': data.get('time'),
            'interval_hours': data.get('interval_hours'),
            'interval_minutes': data.get('interval_minutes'),
            'days_of_week': data.get('days_of_week', []),
            'date': data.get('date'),
            'enabled': data.get('enabled', True),
            'notify_email': data.get('notify_email'),
            'notify_on_success': data.get('notify_on_success', False),
            'notify_on_failure': data.get('notify_on_failure', False)
        }
        
        scheduler_service.update_schedule(schedule_id, schedule_data)
        return jsonify({'message': 'Scheduled test updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduled-tests/<int:schedule_id>', methods=['DELETE'])
def delete_scheduled_test(schedule_id):
    """Delete a scheduled test"""
    try:
        scheduler_service.delete_schedule(schedule_id)
        return jsonify({'message': 'Scheduled test deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduled-tests/<int:schedule_id>/toggle', methods=['POST'])
def toggle_scheduled_test(schedule_id):
    """Enable or disable a scheduled test"""
    try:
        data = request.json
        enabled = data.get('enabled', True)
        scheduler_service.toggle_schedule(schedule_id, enabled)
        return jsonify({
            'message': f'Scheduled test {"enabled" if enabled else "disabled"} successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduled-tests/test-email', methods=['POST'])
def test_email_notification():
    """Test email notification configuration"""
    try:
        from email_notifier import get_email_notifier
        
        data = request.json
        test_email = data.get('email')
        if not test_email:
            return jsonify({'error': 'email is required'}), 400
        
        notifier = get_email_notifier()
        
        if not notifier.is_configured:
            return jsonify({
                'success': False,
                'error': 'Email notifier not configured',
                'message': 'Please set SMTP_USER and SMTP_PASSWORD in .env file'
            }), 400
        
        # Send test email
        summary = {
            'site_url': 'https://example.com',
            'task_description': 'Test email notification',
            'status': 'success',
            'execution_time': datetime.utcnow().isoformat(),
            'duration': '1m 23s',
            'report': "This is a sample analysis report.\n\nKey Findings:\n1. Page load time is excellent (0.8s).\n2. Accessibility score is 95/100.\n3. Mobile responsiveness is verified.\n\nRecommendations:\n- Consider optimizing image sizes further."
        }
        
        success = notifier.send_test_notification(test_email, summary, 'success')
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Test email sent successfully to {test_email}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to send test email',
                'message': 'Check server logs for details'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Register shutdown handler for scheduler
import atexit

@atexit.register
def shutdown_scheduler():
    """Shutdown scheduler service on app exit"""
    try:
        scheduler_service.shutdown()
    except:
        pass

if __name__ == '__main__':
    os.makedirs("screenshots", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    
    print(" UX/QA Automation Agent API Starting...")
    print(" Access the API at: http://localhost:5000")
    print(" Frontend should connect to: http://localhost:5000")
    
    try:
        port = int(os.environ.get("PORT", 5000))
        socketio.run(app, debug=True, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
    finally:
        scheduler_service.shutdown()