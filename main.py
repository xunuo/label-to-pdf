import requests
import json
from collections import defaultdict
from flask import Flask, jsonify

app = Flask(__name__)

# Constants
LEAGUE_ID = 1078309
TOTAL_MANAGERS = 70
GAMEWEEK = 2
BASE_URL = "https://fantasy.premierleague.com/api"

def get_league_entries(league_id, page):
  """Fetch league entries for a given page."""
  url = f"{BASE_URL}/leagues-classic/{league_id}/standings/?page_standings={page}"
  response = requests.get(url)
  return response.json()['standings']['results']

def get_player_pick(entry_id, gameweek):
  """Fetch player picks for a given entry and gameweek."""
  url = f"{BASE_URL}/entry/{entry_id}/event/{gameweek}/picks/"
  response = requests.get(url)
  return response.json()['picks']

def get_player_data():
  """Fetch all player data."""
  url = f"{BASE_URL}/bootstrap-static/"
  response = requests.get(url)
  return response.json()['elements']

def get_top_players():
  # Fetch all league entries
  all_entries = []
  for page in range(1, 3):  # Fetch both pages
      all_entries.extend(get_league_entries(LEAGUE_ID, page))
  
  # Get all player picks
  all_picks = defaultdict(int)
  for entry in all_entries:
      picks = get_player_pick(entry['entry'], GAMEWEEK)
      for pick in picks:
          all_picks[pick['element']] += 1
  
  # Get player data
  player_data = {player['id']: player for player in get_player_data()}
  
  # Get team names
  team_data = requests.get(f"{BASE_URL}/bootstrap-static/").json()['teams']
  team_names = {team['id']: team['name'] for team in team_data}
  
  # Process player data
  processed_players = []
  for player_id, count in all_picks.items():
      player = player_data[player_id]
      processed_players.append({
          'id': player['id'],
          'name': f"{player['first_name']} {player['second_name']}",
          'team': team_names[player['team']],
          'points': player['event_points'],
          'ownership': (count / TOTAL_MANAGERS) * 100
      })
  
  # Sort players by points and get top 5
  top_players = sorted(processed_players, key=lambda x: x['points'], reverse=True)[:5]
  
  # Format output
  formatted_players = []
  for player in top_players:
      formatted_players.append({
          'Player Name': player['name'],
          'Player\'s Team Name': player['team'],
          'Player\'s Points in this GW': player['points'],
          'Percentage Ownership of the Player in the league': f"{player['ownership']:.2f}%"
      })
  
  return formatted_players

@app.route('/top_players')
def top_players():
  result = {
      "data": get_top_players()
  }
  return jsonify(result)

if __name__ == '__main__':
  app.run(debug=True)
