from flask import Flask, request, jsonify
import requests
import json
import os
from dotenv import load_dotenv
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "NOT_SET")

def generate_motivational_prompt(days_left, total_target):
    """Generate a dynamic prompt based on the startup journey progress"""
    
    days_completed = total_target - days_left
    progress_percentage = (days_completed / total_target) * 100
    
    # Determine the phase of the journey
    if progress_percentage < 25:
        phase = "beginning"
        tone = "energetic and encouraging"
    elif progress_percentage < 50:
        phase = "early progress"
        tone = "motivating and momentum-building"
    elif progress_percentage < 75:
        phase = "middle journey"
        tone = "resilient and persistent"
    else:
        phase = "final sprint"
        tone = "determined and finish-strong"
    
    prompt = f"""
    You are a motivational coach for entrepreneurs and startup builders. 

    Generate a short, powerful motivational quote for someone who is on day {days_completed} of their {total_target}-day startup building journey.

    Context:
    - They have {days_left} days remaining
    - They are {progress_percentage:.1f}% through their journey
    - They are in the {phase} phase of their startup journey

    Requirements:
    - Keep the quote under 20 words
    - Make it {tone}
    - Focus on the entrepreneurial mindset
    - Include subtle reference to their progress without being too specific about numbers
    - Make it inspiring and actionable
    - Avoid clichés like "Rome wasn't built in a day"
    - Make it feel personal and relevant to startup builders
    - Use less jargon and more relatable language, like a mentor speaking directly to a founder
    - Use a tone that resonates with the struggles and triumphs of building a startup
    - Avoid generic phrases like "keep going" or "stay strong"
    - Focus on the unique challenges and victories of the startup journey
    - Don't use any special case formatting or unnecessary punctuation

    Return only the motivational quote, nothing else.
    """
    
    return prompt

def get_quote_from_llm(days_left, total_target):
    """Generate motivational quote using OpenRouter API"""
    
    print(f"Generating quote for {days_left} days left out of {total_target}")
    
    try:
        prompt = generate_motivational_prompt(days_left, total_target)
        
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            data=json.dumps({
                "model": "anthropic/claude-3.5-haiku:beta",
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are a concise motivational quote generator for entrepreneurs. Respond with only the quote, nothing else."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 150,
                "temperature": 0.7
            }),
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"Successfully received response from OpenRouter API")
            response_data = response.json()
            
            # Handle DeepSeek R1 model which puts content in reasoning field
            message = response_data['choices'][0]['message']
            quote = message.get('content', '').strip()
            
            # If content is empty, try reasoning field (DeepSeek R1 behavior)
            if not quote and 'reasoning' in message:
                reasoning = message['reasoning']
                # Extract the actual quote from reasoning if present
                if 'quote' in reasoning.lower():
                    # Try to extract quote from reasoning text
                    lines = reasoning.split('\n')
                    for line in lines:
                        if any(keyword in line.lower() for keyword in ['quote:', 'response:', 'answer:']):
                            quote = line.split(':', 1)[-1].strip()
                            break
                    
                    # If no structured quote found, use last sentence as quote
                    if not quote:
                        sentences = reasoning.split('. ')
                        quote = sentences[-1].strip()
                        if quote.endswith('.'):
                            quote = quote[:-1]
            
            # Remove any extra quotes or formatting
            if quote:
                quote = quote.strip('"').strip("'").strip()
                # Limit to reasonable length
                if len(quote) > 200:
                    quote = quote[:200] + "..."
                return quote, None
            else:
                return None, "No quote generated in response"
        else:
            print(f"Error from API: {response.status_code} - {response.text}")
            return None, f"API Error: {response.status_code}"
            
    except Exception as e:
        print(f"Exception occurred: {e}")
        return None, str(e)

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'message': 'Startup Motivational Quote API',
        'usage': '/quote?daysLeft=<number>&totalTarget=<number>',
        'example': '/quote?daysLeft=23&totalTarget=100'
    })

@app.route('/quote', methods=['GET'])
def get_motivational_quote():
    try:
        # Get query parameters
        days_left = request.args.get('daysLeft')
        total_target = request.args.get('totalTarget')
        
        # Validate parameters
        if not days_left or not total_target:
            return jsonify({
                'error': 'Both daysLeft and totalTarget parameters are required',
                'usage': '/quote?daysLeft=<number>&totalTarget=<number>'
            }), 400
        
        # Convert to integers and validate
        try:
            days_left = int(days_left)
            total_target = int(total_target)
        except ValueError:
            return jsonify({
                'error': 'daysLeft and totalTarget must be valid numbers'
            }), 400
        
        # Validate ranges
        if days_left < 0 or total_target <= 0:
            return jsonify({
                'error': 'daysLeft cannot be negative and totalTarget must be positive'
            }), 400
            
        if days_left > total_target:
            return jsonify({
                'error': 'daysLeft cannot be greater than totalTarget'
            }), 400
        
        print(f"Processing request: {days_left} days left out of {total_target}")
        
        # Generate quote
        quote, error = get_quote_from_llm(days_left, total_target)
        
        if error:
            # Fallback quotes based on progress
            days_completed = total_target - days_left
            progress_percentage = (days_completed / total_target) * 100
            
            fallback_quotes = [
                "Every day forward is a step closer to your vision becoming reality.",
                "The entrepreneur's path isn't easy, but it's worth every challenge.",
                "Your startup is built one decision, one day, one breakthrough at a time.",
                "Progress isn't always visible, but persistence always pays off.",
                "Today's small wins compound into tomorrow's big victories."
            ]
            
            import random
            quote = random.choice(fallback_quotes)
            
            return jsonify({
                'quote': quote,
                'daysLeft': days_left,
                'totalTarget': total_target,
                'progressPercentage': round(progress_percentage, 1),
                'warning': 'Used fallback quote due to API issues'
            })
        
        # Calculate additional stats
        days_completed = total_target - days_left
        progress_percentage = (days_completed / total_target) * 100
        
        return jsonify({
            'quote': quote,
            'daysLeft': days_left,
            'totalTarget': total_target,
            'daysCompleted': days_completed,
            'progressPercentage': round(progress_percentage, 1)
        })
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'openrouter_key_configured': OPENROUTER_API_KEY != "NOT_SET"
    })

if __name__ == '__main__':
    # Check if API key is configured
    if OPENROUTER_API_KEY == "NOT_SET":
        print("⚠️  Warning: OPENROUTER_API_KEY not configured in environment variables")
        print("💡 Create a .env file with: OPENROUTER_API_KEY=your_api_key_here")
    else:
        print("✅ OpenRouter API key configured successfully")
    
    app.run(debug=True, port=5000)