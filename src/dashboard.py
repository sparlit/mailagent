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
        body { font-family: sans-serif; margin: 40px; background-color: #f9f9f9; }
        .container { max-width: 1200px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        table { border-collapse: collapse; width: 100%; margin-bottom: 30px; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #eee; }
        th { background-color: #f2f2f2; }
        tr:hover { background-color: #f5f5f5; }
        .summary { font-size: 1.2em; margin-bottom: 20px; color: #333; }
        .charts { display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 30px; }
        .chart-container { flex: 1; min-width: 300px; max-width: 500px; }
        h1, h2 { color: #2c3e50; }
    </style>
</head>
<body>
    <div class="container">
        <h1>MailAgent Autonomous AI Dashboard</h1>
        <div class="summary">
            Monitoring <strong>{{ accounts_count }}</strong> unique Gmail accounts.
        </div>

        <div class="charts">
            <div class="chart-container">
                <h2>Actions Distribution</h2>
                <canvas id="actionsChart"></canvas>
            </div>
            <div class="chart-container">
                <h2>Categories Distribution</h2>
                <canvas id="categoriesChart"></canvas>
            </div>
        </div>

        <div class="stats-container">
            <h2>Detailed Action Statistics</h2>
            <table>
                <thead>
                    <tr>
                        <th>Account</th>
                        <th>Action</th>
                        <th>Category</th>
                        <th>Count</th>
                    </tr>
                </thead>
                <tbody>
                    {% for stat in stats %}
                    <tr>
                        <td>{{ stat[0] }}</td>
                        <td>{{ stat[1] }}</td>
                        <td>{{ stat[2] }}</td>
                        <td>{{ stat[3] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            <h2>Category Summary</h2>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Total Processed</th>
                    </tr>
                </thead>
                <tbody>
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
                </tbody>
            </table>
        </div>
    </div>

    <script>
        {% set actions_data = {} %}
        {% for stat in stats %}
            {% if stat[1] in actions_data %}
                {% if actions_data.update({stat[1]: actions_data[stat[1]] + stat[3]}) %}{% endif %}
            {% else %}
                {% if actions_data.update({stat[1]: stat[3]}) %}{% endif %}
            {% endif %}
        {% endfor %}

        const actionLabels = {{ actions_data.keys() | list | tojson }};
        const actionCounts = {{ actions_data.values() | list | tojson }};

        new Chart(document.getElementById('actionsChart'), {
            type: 'bar',
            data: {
                labels: actionLabels,
                datasets: [{
                    label: 'Number of Actions',
                    data: actionCounts,
                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: { scales: { y: { beginAtZero: true } } }
        });

        const categoryLabels = {{ categories.keys() | list | tojson }};
        const categoryCounts = {{ categories.values() | list | tojson }};

        new Chart(document.getElementById('categoriesChart'), {
            type: 'pie',
            data: {
                labels: categoryLabels,
                datasets: [{
                    data: categoryCounts,
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.5)',
                        'rgba(75, 192, 192, 0.5)',
                        'rgba(255, 206, 86, 0.5)',
                        'rgba(153, 102, 255, 0.5)',
                        'rgba(255, 159, 64, 0.5)'
                    ]
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
    
    Fetches current stats from the shared database, computes the count of unique accounts from the first element of each stats row, and returns the rendered HTML template populated with `stats` and `accounts_count`.
    
    Returns:
        str: Rendered HTML for the dashboard page containing the stats table and `accounts_count`.
    """
    stats = db.get_stats()
    unique_accounts = set(stat[0] for stat in stats)
    return render_template_string(HTML_TEMPLATE, stats=stats, accounts_count=len(unique_accounts))

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
    Simple health check endpoint.

    Returns:
        tuple: JSON response with status "OK" and HTTP 200.
    """
    return jsonify({"status": "OK"}), 200

def run_dashboard(port=5000):
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
