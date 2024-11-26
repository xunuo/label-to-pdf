from flask import Flask, render_template_string
from espn_api.football import League
from datetime import datetime
import pandas as pd
import json

app = Flask(__name__)

# ESPN API credentials
SWID = "{16238C1C-2AE5-48B5-97D3-D83DE6A81883}"
ESPN_S2 = 'AEAYUFenNewPLUPryzYnqWva4yKbBYc6jaayOw0dZVK3%2B2XDeUPYZifj6lV%2FuieoH6u4sVyJOO%2F%2F30h4bEmtJU1ypE%2B3%2FvhO775jAIre5BOi6YTauugdCKil3cpbImsy3S8BBKAU5%2F595uTeDZuLOoLdrHNfEN5N6RFHqhZ1oOAfkSwygG3hGMogTOoYFiRdZVHC1PTexG63brkThblhOxTqlAGWxhZboHxhHfL2dxlccfe6EXafpDzSnJ5cGJr7DVxISFty5QMM8VBUuUsX%2FJKLSYAiDFl6HyPN6YqIn6rSTQ%3D%3D'
LEAGUE_ID = 286725


def get_league_data(year):
    return League(league_id=LEAGUE_ID, year=year, espn_s2=ESPN_S2, swid=SWID)



def get_all_years_data():
    data = {}
    current_year = datetime.now().year
    for year in range(2020, current_year + 1):
        try:
            data[year] = get_league_data(year)
        except:
            continue
    return data


def calculate_custom_power_rankings(league):
    print('hi')
    """
    Calculate custom power rankings based on points scored, winning percentage,
    and performance vs median scores.
    """
    teams_data = {team.team_name: {
        'total_points': 0,
        'weeks_above_median': 0,
        'total_weeks': 0,
        'wins': 0,
        'games': 0
    } for team in league.teams}

    # Get the current week
    current_week = 1
    while True:
        try:
            box_scores = league.box_scores(current_week)
            if current_week != 1:
                if lwhs == box_scores[0].home_score and box_scores[0].away_score == lwas:
                    break
            lwhs = box_scores[0].home_score
            lwas = box_scores[0].away_score


            # Collect all scores for the week to calculate median
            week_scores = []
            for game in box_scores:
                if game.home_score and game.away_score:  # Ensure we have valid scores
                    week_scores.extend([game.home_score, game.away_score])

            if not week_scores:  # If no valid scores, we've hit the end of the season
                break

            median_score = sorted(week_scores)[len(week_scores) // 2]

            # Process each game
            for game in box_scores:
                if not (game.home_score and game.away_score):  # Skip games without scores
                    continue

                # Process home team
                teams_data[game.home_team.team_name]['total_points'] += game.home_score
                teams_data[game.home_team.team_name]['total_weeks'] += 1
                teams_data[game.home_team.team_name]['games'] += 1
                if game.home_score > median_score:
                    teams_data[game.home_team.team_name]['weeks_above_median'] += 1
                if game.home_score > game.away_score:
                    teams_data[game.home_team.team_name]['wins'] += 1

                # Process away team
                teams_data[game.away_team.team_name]['total_points'] += game.away_score
                teams_data[game.away_team.team_name]['total_weeks'] += 1
                teams_data[game.away_team.team_name]['games'] += 1
                if game.away_score > median_score:
                    teams_data[game.away_team.team_name]['weeks_above_median'] += 1
                if game.away_score > game.home_score:
                    teams_data[game.away_team.team_name]['wins'] += 1

            current_week += 1
            print(current_week)
        except Exception as e:
            break

    # Calculate power rankings
    print('calculate power rankings')
    power_rankings = []
    for team_name, data in teams_data.items():
        if data['games'] == 0:  # Skip teams with no games
            continue

        points_scored = data['total_points']
        winning_percentage = data['wins'] / data['games'] if data['games'] > 0 else 0
        median_percentage = data['weeks_above_median'] / data['total_weeks'] if data['total_weeks'] > 0 else 0

        # Calculate power ranking score using the provided formula:
        # (points_scored ** 2) + (points_scored * winning_percentage) + (points_scored * median_percentage)
        power_score = (points_scored ** 2) + (points_scored * winning_percentage) + (points_scored * median_percentage)

        power_rankings.append({
            'team': team_name,
            'score': power_score,
            'points': points_scored,
            'win_pct': winning_percentage,
            'median_pct': median_percentage
        })

    # Sort by power score in descending order
    power_rankings.sort(key=lambda x: x['score'], reverse=True)
    return power_rankings


@app.route('/')
def home():
    leagues_data = get_all_years_data()

    # Compile data for all years
    all_years_data = {}

    for year, league in leagues_data.items():
        year_data = {
            'standings': [],
            'power_rankings': [],
            'top_scorer': None,
            'least_scorer': None,
            'most_points_against': None,
            'top_scored_week': None,
            'least_scored_week': None,
            'recent_activity': [],
            'teams': []
        }

        # Get standings
        try:
            standings = league.standings()
            for team in standings:
                year_data['standings'].append({
                    'name': team.team_name,
                    'wins': team.wins,
                    'losses': team.losses,
                    'points_for': round(team.points_for, 2),
                    'points_against': round(team.points_against, 2)
                })
        except:
            pass

        # Calculate custom power rankings
        try:
            power_rankings = calculate_custom_power_rankings(league)
            year_data['power_rankings'] = power_rankings
            print(year)
        except:
            pass
        '''
        # Get power rankings
        try:
            power_rankings = league.power_rankings()
            for score, team in power_rankings:
                year_data['power_rankings'].append({
                    'score': score,
                    'team': team.team_name
                })
        except:
            pass
        '''
        # Get top/least scorers
        try:
            top_scorer = league.top_scorer()
            year_data['top_scorer'] = {
                'team': top_scorer.team_name,
                'points': round(top_scorer.points_for, 2)
            }
        except:
            pass

        try:
            least_scorer = league.least_scorer()
            year_data['least_scorer'] = {
                'team': least_scorer.team_name,
                'points': round(least_scorer.points_for, 2)
            }
        except:
            pass

        # Get most points against
        try:
            points_against = league.most_points_against()
            year_data['most_points_against'] = {
                'team': points_against.team_name,
                'points': round(points_against.points_against, 2)
            }
        except:
            pass

        # Get top/least scored weeks
        try:
            top_week_team, top_week_score = league.top_scored_week()
            year_data['top_scored_week'] = {
                'team': top_week_team.team_name,
                'score': round(top_week_score, 2)
            }
        except:
            pass

        try:
            least_week_team, least_week_score = league.least_scored_week()
            year_data['least_scored_week'] = {
                'team': least_week_team.team_name,
                'score': round(least_week_score, 2)
            }
        except:
            pass

        # Get recent activity
        try:
            activities = league.recent_activity(size=10)
            for activity in activities:
                activity_data = []
                for team, action, player in activity.actions:
                    activity_data.append({
                        'team': team.team_name,
                        'action': action,
                        'player': player
                    })
                year_data['recent_activity'].append(activity_data)
        except:
            pass

        # Get detailed team data
        try:
            for team in league.teams:
                team_data = {
                    'name': team.team_name,
                    'roster': [],
                    'wins': team.wins,
                    'losses': team.losses,
                    'final_standing': team.final_standing if hasattr(team, 'final_standing') else None
                }

                for player in team.roster:
                    team_data['roster'].append({
                        'name': player.name,
                        'position': player.position,
                        'pro_team': player.proTeam if hasattr(player, 'proTeam') else None,
                        'pos_rank': player.posRank if hasattr(player, 'posRank') else None
                    })

                year_data['teams'].append(team_data)
        except:
            pass

        all_years_data[year] = year_data

    return render_template_string(HTML_TEMPLATE, data=all_years_data)


# HTML Template with embedded CSS and JavaScript
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Fantasy Football League Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.7.0/chart.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .year-selector {
            margin-bottom: 20px;
        }
        .year-btn {
            padding: 10px 20px;
            margin: 0 5px;
            border: none;
            border-radius: 4px;
            background-color: #007bff;
            color: white;
            cursor: pointer;
        }
        .year-btn:hover {
            background-color: #0056b3;
        }
        .year-btn.active {
            background-color: #0056b3;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f8f9fa;
        }
        .chart-container {
            height: 400px;
            margin-bottom: 20px;
        }
        .tab-container {
            margin-bottom: 20px;
        }
        .tab-button {
            padding: 10px 20px;
            margin-right: 5px;
            border: none;
            background-color: #e9ecef;
            cursor: pointer;
        }
        .tab-button.active {
            background-color: #007bff;
            color: white;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Fantasy Football League Dashboard</h1>

        <div class="year-selector">
            {% for year in data.keys()|sort(reverse=true) %}
                <button class="year-btn" onclick="showYear({{ year }})">{{ year }}</button>
            {% endfor %}
        </div>

        {% for year, year_data in data.items() %}
        <div id="year-{{ year }}" class="year-content" style="display: none;">
            <h2>{{ year }} Season</h2>

            <div class="tab-container">
                <button class="tab-button active" onclick="showTab('standings-{{ year }}')">Standings</button>
                <button class="tab-button" onclick="showTab('teams-{{ year }}')">Teams</button>
                <button class="tab-button" onclick="showTab('activity-{{ year }}')">Recent Activity</button>
                <button class="tab-button" onclick="showTab('stats-{{ year }}')">Statistics</button>
            </div>

            <div id="standings-{{ year }}" class="tab-content card active">
                <h3>League Standings</h3>
                <div class="chart-container">
                    <canvas id="standings-chart-{{ year }}"></canvas>
                </div>
                <table>
                    <tr>
                        <th>Team</th>
                        <th>Wins</th>
                        <th>Losses</th>
                        <th>Points For</th>
                        <th>Points Against</th>
                    </tr>
                    {% for team in year_data.standings %}
                    <tr>
                        <td>{{ team.name }}</td>
                        <td>{{ team.wins }}</td>
                        <td>{{ team.losses }}</td>
                        <td>{{ team.points_for }}</td>
                        <td>{{ team.points_against }}</td>
                    </tr>
                    {% endfor %}
                </table>
            </div>

            <div id="teams-{{ year }}" class="tab-content card">
                <h3>Team Rosters</h3>
                {% for team in year_data.teams %}
                <div class="card">
                    <h4>{{ team.name }} ({{ team.wins }}-{{ team.losses }})</h4>
                    <table>
                        <tr>
                            <th>Player</th>
                            <th>Position</th>
                            <th>Team</th>
                            <th>Position Rank</th>
                        </tr>
                        {% for player in team.roster %}
                        <tr>
                            <td>{{ player.name }}</td>
                            <td>{{ player.position }}</td>
                            <td>{{ player.pro_team }}</td>
                            <td>{{ player.pos_rank }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                </div>
                {% endfor %}
            </div>

            <div id="activity-{{ year }}" class="tab-content card">
                <h3>Recent Activity</h3>
                {% for activity in year_data.recent_activity %}
                <div class="card">
                    {% for action in activity %}
                    <p>{{ action.team }} {{ action.action }} {{ action.player }}</p>
                    {% endfor %}
                </div>
                {% endfor %}
            </div>

            <div id="stats-{{ year }}" class="tab-content card">
                <h3>Season Statistics</h3>
                <div class="grid">
                    <div class="card">
                        <h4>Top Scorer</h4>
                        {% if year_data.top_scorer %}
                        <p>{{ year_data.top_scorer.team }} ({{ year_data.top_scorer.points }} points)</p>
                        {% endif %}
                    </div>
                    <div class="card">
                        <h4>Least Scorer</h4>
                        {% if year_data.least_scorer %}
                        <p>{{ year_data.least_scorer.team }} ({{ year_data.least_scorer.points }} points)</p>
                        {% endif %}
                    </div>
                    <div class="card">
                        <h4>Most Points Against</h4>
                        {% if year_data.most_points_against %}
                        <p>{{ year_data.most_points_against.team }} ({{ year_data.most_points_against.points }} points)</p>
                        {% endif %}
                    </div>
                    <div class="card">
                        <h4>Highest Scoring Week</h4>
                        {% if year_data.top_scored_week %}
                        <p>{{ year_data.top_scored_week.team }} ({{ year_data.top_scored_week.score }} points)</p>
                        {% endif %}
                    </div>
                    <div class="card">
                        <h4>Lowest Scoring Week</h4>
                        {% if year_data.least_scored_week %}
                        <p>{{ year_data.least_scored_week.team }} ({{ year_data.least_scored_week.score }} points)</p>
                        {% endif %}
                    </div>
                </div>

                <h4>Power Rankings</h4>
                <div class="chart-container">
                    <canvas id="power-rankings-chart-{{ year }}"></canvas>
                </div>
                <table>
                    <tr>
                        <th>Rank</th>
                        <th>Team</th>
                        <th>Power Score</th>
                        <th>Points Scored</th>
                        <th>Win %</th>
                        <th>Above Median %</th>
                    </tr>
                    {% for rank in year_data.power_rankings %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td>{{ rank.team }}</td>
                        <td>{{ "%.2f"|format(rank.score) }}</td>
                        <td>{{ "%.2f"|format(rank.points) }}</td>
                        <td>{{ "%.1f"|format(rank.win_pct * 100) }}%</td>
                        <td>{{ "%.1f"|format(rank.median_pct * 100) }}%</td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        function showYear(year) {
            document.querySelectorAll('.year-content').forEach(content => {
                content.style.display = 'none';
            });
            document.querySelectorAll('.year-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.getElementById(`year-${year}`).style.display = 'block';
            event.target.classList.add('active');

            // Initialize charts for the selected year
            initializeCharts(year);
        }

        function showTab(tabId) {
            const yearContent = document.getElementById(tabId).parentElement;
            yearContent.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            yearContent.querySelectorAll('.tab-button').forEach(button => {
                button.classList.remove('active');
            });
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
        }

        function initializeCharts(year) {
            const data = {{ data|tojson }};
            const yearData = data[year];

            // Destroy existing charts if they exist
            const existingStandingsChart = Chart.getChart(`standings-chart-${year}`);
            const existingPowerRankingsChart = Chart.getChart(`power-rankings-chart-${year}`);
            if (existingStandingsChart) existingStandingsChart.destroy();
            if (existingPowerRankingsChart) existingPowerRankingsChart.destroy();

            // Standings Chart
            const standingsCtx = document.getElementById(`standings-chart-${year}`).getContext('2d');
            new Chart(standingsCtx, {
                type: 'bar',
                data: {
                    labels: yearData.standings.map(team => team.name),
                    datasets: [
                        {
                            label: 'Points For',
                            data: yearData.standings.map(team => team.points_for),
                            backgroundColor: 'rgba(0, 123, 255, 0.5)',
                            borderColor: 'rgba(0, 123, 255, 1)',
                            borderWidth: 1
                        },
                        {
                            label: 'Points Against',
                            data: yearData.standings.map(team => team.points_against),
                            backgroundColor: 'rgba(220, 53, 69, 0.5)',
                            borderColor: 'rgba(220, 53, 69, 1)',
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top'
                        },
                        title: {
                            display: true,
                            text: 'Points For vs Points Against'
                        }
                    }
                }
            });

            // Power Rankings Chart
            const powerRankingsCtx = document.getElementById(`power-rankings-chart-${year}`).getContext('2d');
            new Chart(powerRankingsCtx, {
                type: 'bar',
                data: {
                    labels: yearData.power_rankings.map(rank => rank.team),
                    datasets: [{
                        label: 'Power Ranking Score',
                        data: yearData.power_rankings.map(rank => rank.score),
                        backgroundColor: 'rgba(40, 167, 69, 0.5)',
                        borderColor: 'rgba(40, 167, 69, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top'
                        },
                        title: {
                            display: true,
                            text: 'Power Rankings'
                        }
                    }
                }
            });
        }

        // Show the most recent year by default
        const mostRecentYear = Math.max(...Object.keys({{ data|tojson }}).map(Number));
        showYear(mostRecentYear);
    </script>
</body>
</html>
'''


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
