from flask import Flask, jsonify, render_template_string
from .database import Database

app = Flask(__name__)
db = Database()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>MailAgent Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body { font-family: sans-serif; margin: 40px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }
        tr:hover { background-color: #f5f5f5; }
        .stats-container { margin-top: 20px; }
    </style>
</head>
<body>
    <h1>MailAgent Autonomous AI Dashboard</h1>
    <p>Monitoring <strong>{{ accounts_count }}</strong> accounts.</p>
    <div class="stats-container">
        <h2>Action Statistics</h2>
        <table>
            <tr>
                <th>Account</th>
                <th>Action</th>
                <th>Category</th>
                <th>Count</th>
            </tr>
            {% for stat in stats %}
            <tr>
                <td>{{ stat[0] }}</td>
                <td>{{ stat[1] }}</td>
                <td>{{ stat[2] }}</td>
                <td>{{ stat[3] }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    """
    Render the dashboard HTML page with action statistics and account count.
    
    Fetches statistics from the global database client, computes the number of unique accounts, and renders the in-module HTML template with `stats` and `accounts_count` provided to the template.
    
    Returns:
        str: The rendered HTML page for the dashboard.
    """
    stats = db.get_stats()
    accounts_count = len(set(s[0] for s in stats))
    return render_template_string(HTML_TEMPLATE, stats=stats, accounts_count=accounts_count)

@app.route('/api/stats')
def api_stats():
    """
    Provide action statistics as JSON by fetching current statistics from the database.
    
    Returns:
        json: The raw `stats` value returned by `db.get_stats()` serialized to JSON (typically a list of statistic rows).
    """
    stats = db.get_stats()
    return jsonify(stats)

def run_dashboard(port=5000):
    """
    Start the Flask dashboard server bound to all network interfaces.
    
    Parameters:
        port (int): TCP port to bind the server to (default: 5000). The server runs with debug mode disabled and the reloader turned off.
    """
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
