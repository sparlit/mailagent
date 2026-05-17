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
    stats = db.get_stats()
    accounts_count = len(set(s[0] for s in stats))
    return render_template_string(HTML_TEMPLATE, stats=stats, accounts_count=accounts_count)

@app.route('/api/stats')
def api_stats():
    stats = db.get_stats()
    return jsonify(stats)

def run_dashboard(port=5000):
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
