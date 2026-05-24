from flask import Flask, jsonify, render_template_string
from .database import Database
from . import config

__all__ = ['run_dashboard']

app = Flask(__name__)
db = Database()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>MailAgent Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: sans-serif; margin: 40px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }
        tr:hover { background-color: #f5f5f5; }
        .stats-container { margin-top: 20px; }
        .summary { font-size: 1.2em; margin-bottom: 20px; }
    </style>
</head>
<body>
    <h1>MailAgent Autonomous AI Dashboard</h1>
    <div class="summary">
        Monitoring <strong>{{ accounts_count }}</strong> unique Gmail accounts. | Status: <span style="color: green;">Healthy</span>
    </div>

    <div style="display: flex; flex-wrap: wrap; gap: 20px;">
        <div style="flex: 1; min-width: 300px;">
            <canvas id="actionChart"></canvas>
        </div>
        <div style="flex: 1; min-width: 300px;">
            <canvas id="categoryChart"></canvas>
        </div>
    </div>
    <div class="stats-container">
        <h2>Recent Activity</h2>
        <table>
            <tr>
                <th>Account</th>
                <th>Message ID</th>
                <th>Action</th>
                <th>Category</th>
                <th>Timestamp</th>
            </tr>
            {% for activity in recent_activity %}
            <tr>
                <td>{{ activity[0] }}</td>
                <td>{{ activity[1] }}</td>
                <td>{{ activity[2] }}</td>
                <td>{{ activity[3] }}</td>
                <td>{{ activity[4] }}</td>
            </tr>
            {% endfor %}
        </table>

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

        <h2>Category Summary</h2>
        <table>
            <tr>
                <th>Category</th>
                <th>Total Processed</th>
            </tr>
            {% set categories = {} %}
            {% for stat in stats %}
                {% if stat[2] in categories %}
                    {% if categories.update({stat[2]: categories[stat[2]] + stat[3]}) %}{% endif %}
                {% else %}
                    {% if categories.update({stat[2]: stat[3]}) %}{% endif %}
                {% endif %}
            {% endfor %}
            {% for cat, count in categories.items() %}
            <tr>
                <td>{{ cat }}</td>
                <td>{{ count }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    <script>
        const stats = {{ stats | tojson }};

        // Process stats for charts
        const actions = {};
        const categories = {};

        stats.forEach(stat => {
            const action = stat[1];
            const category = stat[2];
            const count = stat[3];

            actions[action] = (actions[action] || 0) + count;
            categories[category] = (categories[category] || 0) + count;
        });

        const actionCtx = document.getElementById('actionChart').getContext('2d');
        new Chart(actionCtx, {
            type: 'bar',
            data: {
                labels: Object.keys(actions),
                datasets: [{
                    label: 'Actions Performed',
                    data: Object.values(actions),
                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: { scales: { y: { beginAtZero: true } } }
        });

        const categoryCtx = document.getElementById('categoryChart').getContext('2d');
        new Chart(categoryCtx, {
            type: 'pie',
            data: {
                labels: Object.keys(categories),
                datasets: [{
                    label: 'Categories Distribution',
                    data: Object.values(categories),
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.5)',
                        'rgba(75, 192, 192, 0.5)',
                        'rgba(255, 206, 86, 0.5)',
                        'rgba(153, 102, 255, 0.5)',
                        'rgba(255, 159, 64, 0.5)'
                    ],
                    borderWidth: 1
                }]
            }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """
    Render the dashboard page showing action statistics and the number of unique monitored accounts.
    
    Fetches current stats and recent activity from the shared database, computes the count of unique accounts from the first element of each stats row, and returns the rendered HTML template populated with `stats`, `recent_activity` and `accounts_count`.
    
    Returns:
        str: Rendered HTML for the dashboard page containing the stats table, recent activity table and `accounts_count`.
    """
    stats = db.get_stats()
    recent_activity = db.get_recent_activity(10)
    unique_accounts = set(stat[0] for stat in stats)
    return render_template_string(
        HTML_TEMPLATE,
        stats=stats,
        recent_activity=recent_activity,
        accounts_count=len(unique_accounts)
    )

@app.route('/api/stats')
def api_stats():
    """
    Return JSON-serialized action statistics retrieved from the shared database.
    
    Returns:
    	Flask Response: A JSON response containing the list of statistics as returned by `db.get_stats()`.
    """
    stats = db.get_stats()
    return jsonify(stats)

@app.route('/health')
def health():
    """
    Health check endpoint.

    Returns:
        JSON: status and basic stats.
    """
    return jsonify({
        "status": "healthy",
        "monitoring_accounts": len(set(stat[0] for stat in db.get_stats()))
    })

def run_dashboard(port=5000):
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
