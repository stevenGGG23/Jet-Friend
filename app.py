from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from openai import OpenAI
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for all routes

# Initialize the OpenAI client with OpenRouter
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    logger.warning("OPENROUTER_API_KEY not set. AI functionality will be limited.")
    client = None
else:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,  # Securely stored API key
    )

def get_ai_response(user_message, conversation_history=None):
    """
    Send a message to Microsoft MAI DS R1 and get a response
    """
    if not client:
        return "I'm sorry, but AI functionality is currently unavailable. Please set the OPENROUTER_API_KEY environment variable to enable AI responses."

    try:
        # Prepare messages with conversation history
        messages = []

        # Add system message for travel assistant context
        messages.append({
            "role": "system",
            "content": "You are JetFriend, an intelligent AI travel companion. You help users plan trips, find destinations, book flights, discover local attractions, and provide travel advice. Be helpful, friendly, and knowledgeable about travel. Provide practical and actionable travel recommendations."
        })

        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })

        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://stevenggg23.github.io/Jet-Friend/",
                "X-Title": "Jet Friend",
            },
            model="microsoft/mai-ds-r1:free",
            messages=messages,
            max_tokens=1000,
            temperature=0.7
        )

        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Error getting AI response: {str(e)}")
        return f"I'm sorry, I'm having trouble connecting right now. Please try again in a moment. Error: {str(e)}"

@app.route('/')
def serve_index():
    """Serve the main HTML file"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('.', filename)

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        conversation_history = data.get('history', [])
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Get AI response
        ai_response = get_ai_response(user_message, conversation_history)
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'timestamp': request.timestamp if hasattr(request, 'timestamp') else None
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'Sorry, I encountered an error processing your request.'
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'JetFriend API',
        'version': '1.0.0'
    })

@app.route('/api/test', methods=['GET'])
def test_ai():
    """Test AI connectivity"""
    if not client:
        return jsonify({
            'success': False,
            'error': 'OPENROUTER_API_KEY not configured',
            'ai_status': 'disconnected',
            'message': 'Please set the OPENROUTER_API_KEY environment variable to enable AI functionality.'
        }), 503

    try:
        test_response = get_ai_response("Hello! Can you tell me you're working correctly?")
        return jsonify({
            'success': True,
            'test_response': test_response,
            'ai_status': 'connected'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'ai_status': 'disconnected'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'

    print(f"🚀 JetFriend API starting on port {port}")
    print(f"🌐 Visit: http://localhost:{port}")

    app.run(host='0.0.0.0', port=port, debug=debug_mode)
