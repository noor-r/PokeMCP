# PokeMCP
PokeMCP: Pokémon Battle Simulation System
A comprehensive Pokémon data provider and battle simulator built using Python's Model Context Protocol (MCP) framework.

Features
Pokémon Data Resource

Fetch detailed Pokémon information from the PokeAPI
Access stats, types, abilities, moves, and evolution chains
Available through the pokemon://{name} resource
Battle Simulation Tool

Simulate turn-based battles between any two Pokémon
Implements core battle mechanics:
Type effectiveness calculations (super effective/not very effective)
STAB (Same Type Attack Bonus)
Status effects (paralysis, burn, poison, sleep, freeze)
Critical hits
Stat modifications
Move-specific effects
Detailed battle logs with emoji indicators
Installation & Setup
Prerequisites
Python 3.8 or higher
Internet connection (to access the PokeAPI)
Setup Instructions
For Windows
# Create a virtual environment
python -m venv .venv
or
uv venv .venv

# Activate the virtual environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
or
uv pip install -r requirements.txt


For macOS/Linux
# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
Running the Application
The client example script will start the server automatically and demonstrate the functionality:

# Windows
python client_example.py

# macOS/Linux
python3 client_example.py
System Architecture
The system consists of two main components:

MCP Server (pokemcp_server/)

mcp_instance.py: Creates the FastMCP server instance
server.py: Initializes the server and registers resources/tools
pokemon_data.py: Implements the Pokémon data resource
battle_simulator.py: Implements the battle simulation tool
Client Example (client_example.py)

Connects to the MCP server
Fetches Pokémon data
Initiates battles between random Pokémon
Displays formatted Pokémon information and battle logs
Battle Mechanics
The battle simulator implements the following mechanics:

Type Effectiveness: Damage is multiplied based on type matchups (2x for super effective, 0.5x for not very effective)
STAB Bonus: Moves matching the Pokémon's type get a 1.5x damage boost
Critical Hits: Random chance for 1.5x damage
Status Effects:
Paralysis: 25% chance to skip turn, reduces speed
Burn: Reduces attack, deals damage over time
Poison: Deals damage over time
Sleep: Cannot attack, chance to wake up each turn
Freeze: Cannot attack, chance to thaw each turn
Stat Changes: Moves can boost or lower stats with scaling effects
Recovery Moves: Healing and HP restoration
Multi-hit Moves: Some moves hit multiple times
Known Issues
When using the battle simulator tool, there may sometimes be an error reading the Pokémon resource through MCP. The system automatically falls back to direct API calls when this occurs.
Example Battle Output
==== BATTLE START ====
🔴 WEEPINBELL vs 🔵 JOLTEON

🔴 WEEPINBELL STATS:
  Types: GRASS, POISON
  HP: 65
  Attack: 90
  Defense: 50
  Special Attack: 85
  Special Defense: 45
  Speed: 55
  Abilities: CHLOROPHYLL, GLUTTONY

🔵 JOLTEON STATS:
  Types: ELECTRIC
  HP: 65
  Attack: 65
  Defense: 60
  Special Attack: 110
  Special Defense: 95
  Speed: 130
  Abilities: VOLT-ABSORB, QUICK-FEET

🔵 JOLTEON goes first due to higher speed (130 vs 55).

===== TURN 1 =====
🔵 JOLTEON HP: 65, Status: None
🔴 WEEPINBELL HP: 65, Status: None

JOLTEON uses NATURAL-GIFT!
Move Type: NORMAL, Category: PHYSICAL, Power: 40
Effect: Power and type depend on the held berry.
💥 WEEPINBELL took 23 damage. Remaining HP: 42

===== TURN 2 =====
🔴 WEEPINBELL HP: 42, Status: None
🔵 JOLTEON HP: 65, Status: None

WEEPINBELL uses POWER-WHIP!
Move Type: GRASS, Category: PHYSICAL, Power: 120
💥 A critical hit! x1.5 damage!
💥 Same Type Attack Bonus for WEEPINBELL! (x1.5)
💥 JOLTEON took 175 damage. Remaining HP: 0
☠️ JOLTEON fainted!

🏆 WEEPINBELL wins the battle! 🏆
Cross-Platform Compatibility
This project is designed to work on Windows, macOS, and Linux by:

Using platform-independent paths
Properly handling module imports
Ensuring all file paths use the appropriate directory separators
For Developers
To extend this project:

Add new battle mechanics in battle_simulator.py
Expand Pokémon data retrieval in pokemon_data.py
Create additional tools or resources by registering them with the MCP server
