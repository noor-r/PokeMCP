# Battle Simulator Logic will go here 

import random
import json
import httpx
import sys
import asyncio
from mcp.server.fastmcp import Context # For type hinting and context access
# Import the mcp instance directly from mcp_instance
from pokemcp_server.mcp_instance import mcp
# We might need access to the pokemon_data functions directly or rely on context.read_resource
# For now, let's assume we'll use context.read_resource primarily.

# Caches to avoid repeated API calls
MOVE_CACHE = {}
TYPE_CHART_CACHE = None
STATUS_EFFECTS_CACHE = None

# Add a helper function to fetch Pokemon data directly
async def fetch_pokemon_direct(name: str) -> dict:
    """Helper function to fetch Pokémon data directly from the PokeAPI."""
    base_url = "https://pokeapi.co/api/v2/pokemon"
    
    print(f"Direct fetching data for {name} from PokeAPI", file=sys.stderr)
    
    async with httpx.AsyncClient() as client:
        # Get basic pokemon data
        response = await client.get(f"{base_url}/{name.lower()}")
        response.raise_for_status()
        data = response.json()
        
        stats = {s['stat']['name']: s['base_stat'] for s in data['stats']}
        types = [t['type']['name'] for t in data['types']]
        abilities = [a['ability']['name'] for a in data['abilities']]
        moves = [m['move']['name'] for m in data['moves']]
        
        # Get species and evolution data if possible
        evolutions = []
        try:
            species_url = data['species']['url']
            species_response = await client.get(species_url)
            species_response.raise_for_status()
            species_data = species_response.json()
            
            # Try to get evolution chain
            if 'evolution_chain' in species_data:
                evolution_chain_url = species_data['evolution_chain']['url']
                evolution_response = await client.get(evolution_chain_url)
                evolution_response.raise_for_status()
                evolution_data = evolution_response.json()
                
                current_evolution = evolution_data['chain']
                while current_evolution:
                    evolutions.append(current_evolution['species']['name'])
                    if current_evolution['evolves_to']:
                        current_evolution = current_evolution['evolves_to'][0]
                    else:
                        current_evolution = None
        except Exception as e:
            print(f"Error fetching evolution data: {e}", file=sys.stderr)
            # If we can't get evolution data, just use the current Pokemon name
            evolutions = [name.lower()]
        
        return {
            "name": data['name'],
            "id": data['id'],
            "base_stats": stats,
            "types": types,
            "abilities": abilities,
            "moves": moves,
            "evolution_chain": evolutions
        }

async def get_type_chart() -> dict:
    """Fetch the complete type effectiveness chart from PokeAPI."""
    global TYPE_CHART_CACHE
    
    if TYPE_CHART_CACHE:
        return TYPE_CHART_CACHE
        
    print("Fetching complete type chart from PokeAPI", file=sys.stderr)
    
    async with httpx.AsyncClient() as client:
        type_chart = {}
        # Fetch all types and their effectiveness relationships
        types_response = await client.get("https://pokeapi.co/api/v2/type")
        types_data = types_response.json()
        
        # Process each type to build the complete chart
        for type_entry in types_data['results']:
            type_name = type_entry['name']
            type_detail_response = await client.get(type_entry['url'])
            type_detail = type_detail_response.json()
            
            # Initialize type in chart
            if type_name not in type_chart:
                type_chart[type_name] = {}
                
            # Process damage relations
            damage_relations = type_detail['damage_relations']
            
            # Double damage to (super effective)
            for target in damage_relations['double_damage_to']:
                type_chart[type_name][target['name']] = 2.0
                
            # Half damage to (not very effective)
            for target in damage_relations['half_damage_to']:
                type_chart[type_name][target['name']] = 0.5
                
            # No damage to (immune)
            for target in damage_relations['no_damage_to']:
                type_chart[type_name][target['name']] = 0
                
            # Normal damage to types not specified (neutral)
            # Will be handled by using .get(type, 1.0) when accessing the chart
    
    TYPE_CHART_CACHE = type_chart
    return type_chart

async def get_status_effects() -> list:
    """Get all possible status conditions."""
    global STATUS_EFFECTS_CACHE
    
    if STATUS_EFFECTS_CACHE:
        return STATUS_EFFECTS_CACHE
        
    print("Using standard Pokemon status conditions", file=sys.stderr)
    
    # Standard status conditions in Pokémon games
    status_conditions = ['paralysis', 'poison', 'burn', 'sleep', 'freeze']
    
    STATUS_EFFECTS_CACHE = status_conditions
    return status_conditions

async def get_move_data(move_name: str) -> dict:
    """Fetch complete move data from PokeAPI or return from cache if available."""
    if move_name in MOVE_CACHE:
        return MOVE_CACHE[move_name]
    
    try:
        print(f"Fetching move data for: {move_name}", file=sys.stderr)
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://pokeapi.co/api/v2/move/{move_name.lower()}")
            response.raise_for_status()
            move_data = response.json()
            
            # Extract all relevant information including effects
            result = {
                "id": move_data['id'],
                "name": move_data['name'],
                "type": move_data['type']['name'],
                "power": move_data.get('power'),
                "pp": move_data.get('pp'),
                "accuracy": move_data.get('accuracy'),
                "priority": move_data.get('priority', 0),
                "category": move_data['damage_class']['name'],
                "effect_chance": move_data.get('effect_chance'),
                "effect_entries": [],
                "meta": {},
                "stat_changes": []
            }
            
            # Extract effect text
            if 'effect_entries' in move_data and move_data['effect_entries']:
                for effect in move_data['effect_entries']:
                    result['effect_entries'].append({
                        'effect': effect['effect'],
                        'short_effect': effect['short_effect']
                    })
            
            # Extract meta data if available (critical rate, drain, etc.)
            if 'meta' in move_data and move_data['meta']:
                result['meta'] = {
                    'ailment': move_data['meta'].get('ailment', {}).get('name') if 'ailment' in move_data['meta'] else None,
                    'ailment_chance': move_data['meta'].get('ailment_chance'),
                    'category': move_data['meta'].get('category', {}).get('name') if 'category' in move_data['meta'] else None,
                    'crit_rate': move_data['meta'].get('crit_rate'),
                    'drain': move_data['meta'].get('drain'),
                    'flinch_chance': move_data['meta'].get('flinch_chance'),
                    'healing': move_data['meta'].get('healing'),
                    'stat_chance': move_data['meta'].get('stat_chance')
                }
            
            # Extract stat changes
            if 'stat_changes' in move_data and move_data['stat_changes']:
                for change in move_data['stat_changes']:
                    result['stat_changes'].append({
                        'stat': change['stat']['name'],
                        'change': change['change']
                    })
            
            # Set default power if it's an attacking move but has no power
            if result['category'] in ['physical', 'special'] and result['power'] is None:
                result['power'] = 40
            
            # Cache the result
            MOVE_CACHE[move_name] = result
            return result
    except Exception as e:
        print(f"Error fetching move data for {move_name}: {e}", file=sys.stderr)
        # Return a generic move data if API fails
        return {
            "id": 0,
            "name": move_name,
            "type": "normal",
            "power": 40,
            "category": "physical",
            "accuracy": 95,
            "pp": 15,
            "priority": 0,
            "effect_entries": [],
            "meta": {},
            "stat_changes": []
        }

@mcp.tool()
async def simulate_battle(pokemon1_name: str, pokemon2_name: str, ctx: Context) -> dict:
    """Simulates a battle between two Pokémon and returns the log and winner."""
    battle_log = []
    
    try:
        # Initialize the type chart
        await get_type_chart()
        
        # Initialize status effects
        status_effects = await get_status_effects()
        
        # Fetch data for both Pokémon using the resource
        try:
            # The read_resource function returns a ReadResourceResult object
            p1_result = await ctx.read_resource(f"pokemon://{pokemon1_name.lower()}")
            # Extract the binary data from the first content item
            p1_data_bytes = p1_result.contents[0].blob
            # Base64 decode if needed and convert to JSON
            import base64
            p1_data_bytes = base64.b64decode(p1_data_bytes)
            p1 = json.loads(p1_data_bytes.decode('utf-8'))
            battle_log.append(f"Fetched data for {p1['name']}.")

            p2_result = await ctx.read_resource(f"pokemon://{pokemon2_name.lower()}")
            p2_data_bytes = p2_result.contents[0].blob
            p2_data_bytes = base64.b64decode(p2_data_bytes)
            p2 = json.loads(p2_data_bytes.decode('utf-8'))
            battle_log.append(f"Fetched data for {p2['name']}.")
        except Exception as e:
            battle_log.append(f"Error reading Pokemon resource: {str(e)}")
            print(f"Error reading Pokemon resource: {str(e)}", file=sys.stderr)
            # Fallback: Try to fetch data directly using httpx
            p1 = await fetch_pokemon_direct(pokemon1_name)
            battle_log.append(f"Fetched data for {p1['name']} using direct API call.")
            
            p2 = await fetch_pokemon_direct(pokemon2_name)
            battle_log.append(f"Fetched data for {p2['name']} using direct API call.")

        # Fetch move data for a selection of each Pokémon's moves
        # In a real battle, Pokémon have 4 moves, so we'll select up to 4 random moves
        p1_moves = random.sample(p1['moves'], min(4, len(p1['moves'])))
        p2_moves = random.sample(p2['moves'], min(4, len(p2['moves'])))
        
        p1_move_data = []
        p2_move_data = []
        
        # Fetch detailed move data
        battle_log.append(f"Fetching move data for {p1['name']} and {p2['name']}...")
        
        for move in p1_moves:
            move_data = await get_move_data(move)
            p1_move_data.append(move_data)
            
        for move in p2_moves:
            move_data = await get_move_data(move)
            p2_move_data.append(move_data)

    except Exception as e:
        battle_log.append(f"Error fetching Pokémon data: {str(e)}")
        return {"battle_log": battle_log, "winner": None, "error": str(e)}

    # Initialize battle stats with all data from the API
    p1_battle_stats = {
        'name': p1['name'],
        'hp': p1['base_stats']['hp'],
        'attack': p1['base_stats']['attack'],
        'defense': p1['base_stats']['defense'],
        'sp_attack': p1['base_stats']['special-attack'],
        'sp_defense': p1['base_stats']['special-defense'],
        'speed': p1['base_stats']['speed'],
        'types': p1['types'],
        'abilities': p1['abilities'],
        'moves': p1_move_data,
        'status': None,
        'status_duration': 0,
        'stat_mods': {  # Stat modifiers (-6 to +6)
            'attack': 0, 
            'defense': 0,
            'sp_attack': 0,
            'sp_defense': 0,
            'speed': 0,
            'accuracy': 0,
            'evasion': 0
        }
    }
    p2_battle_stats = {
        'name': p2['name'],
        'hp': p2['base_stats']['hp'],
        'attack': p2['base_stats']['attack'],
        'defense': p2['base_stats']['defense'],
        'sp_attack': p2['base_stats']['special-attack'],
        'sp_defense': p2['base_stats']['special-defense'],
        'speed': p2['base_stats']['speed'],
        'types': p2['types'],
        'abilities': p2['abilities'],
        'moves': p2_move_data,
        'status': None,
        'status_duration': 0,
        'stat_mods': {
            'attack': 0,
            'defense': 0,
            'sp_attack': 0,
            'sp_defense': 0,
            'speed': 0, 
            'accuracy': 0,
            'evasion': 0
        }
    }

    # Display battle introduction with detailed information
    battle_log.append(f"\n==== BATTLE START ====")
    battle_log.append(f"🔴 {p1_battle_stats['name'].upper()} vs 🔵 {p2_battle_stats['name'].upper()}")
    
    # Display detailed stats for first Pokémon
    battle_log.append(f"\n🔴 {p1_battle_stats['name'].upper()} STATS:")
    battle_log.append(f"  Types: {', '.join(p1_battle_stats['types']).upper()}")
    battle_log.append(f"  HP: {p1_battle_stats['hp']}")
    battle_log.append(f"  Attack: {p1_battle_stats['attack']}")
    battle_log.append(f"  Defense: {p1_battle_stats['defense']}")
    battle_log.append(f"  Special Attack: {p1_battle_stats['sp_attack']}")
    battle_log.append(f"  Special Defense: {p1_battle_stats['sp_defense']}")
    battle_log.append(f"  Speed: {p1_battle_stats['speed']}")
    battle_log.append(f"  Abilities: {', '.join(p1_battle_stats['abilities']).upper()}")
    
    # Display detailed stats for second Pokémon
    battle_log.append(f"\n🔵 {p2_battle_stats['name'].upper()} STATS:")
    battle_log.append(f"  Types: {', '.join(p2_battle_stats['types']).upper()}")
    battle_log.append(f"  HP: {p2_battle_stats['hp']}")
    battle_log.append(f"  Attack: {p2_battle_stats['attack']}")
    battle_log.append(f"  Defense: {p2_battle_stats['defense']}")
    battle_log.append(f"  Special Attack: {p2_battle_stats['sp_attack']}")
    battle_log.append(f"  Special Defense: {p2_battle_stats['sp_defense']}")
    battle_log.append(f"  Speed: {p2_battle_stats['speed']}")
    battle_log.append(f"  Abilities: {', '.join(p2_battle_stats['abilities']).upper()}")
    
    # Show moves for each Pokémon
    battle_log.append(f"\n🔴 {p1_battle_stats['name'].upper()} MOVES:")
    for move in p1_battle_stats['moves']:
        battle_log.append(f"  • {move['name']} (Type: {move['type']}, Power: {move['power']}, Category: {move['category']})")
        # Add effect description if available
        if move.get('effect_entries') and len(move['effect_entries']) > 0:
            effect_text = move['effect_entries'][0].get('short_effect', '')
            if effect_text:
                # Replace effect_chance with actual value if present
                if move.get('effect_chance') is not None:
                    effect_text = effect_text.replace('$effect_chance', str(move['effect_chance']))
                battle_log.append(f"    Effect: {effect_text}")
    
    battle_log.append(f"\n🔵 {p2_battle_stats['name'].upper()} MOVES:")
    for move in p2_battle_stats['moves']:
        battle_log.append(f"  • {move['name']} (Type: {move['type']}, Power: {move['power']}, Category: {move['category']})")
        # Add effect description if available
        if move.get('effect_entries') and len(move['effect_entries']) > 0:
            effect_text = move['effect_entries'][0].get('short_effect', '')
            if effect_text:
                # Replace effect_chance with actual value if present
                if move.get('effect_chance') is not None:
                    effect_text = effect_text.replace('$effect_chance', str(move['effect_chance']))
                battle_log.append(f"    Effect: {effect_text}")

    # Determine which Pokémon goes first based on speed stat
    if p1_battle_stats['speed'] > p2_battle_stats['speed']:
        attacker, defender = p1_battle_stats, p2_battle_stats
        battle_log.append(f"\n🔴 {p1_battle_stats['name'].upper()} goes first due to higher speed ({p1_battle_stats['speed']} vs {p2_battle_stats['speed']}).")
    elif p2_battle_stats['speed'] > p1_battle_stats['speed']:
        attacker, defender = p2_battle_stats, p1_battle_stats
        battle_log.append(f"\n🔵 {p2_battle_stats['name'].upper()} goes first due to higher speed ({p2_battle_stats['speed']} vs {p1_battle_stats['speed']}).")
    else:
        # Speed tie, random decision
        if random.choice([True, False]):
            attacker, defender = p1_battle_stats, p2_battle_stats
            battle_log.append(f"\n🔴 {p1_battle_stats['name'].upper()} goes first (speed tie, decided randomly).")
        else:
            attacker, defender = p2_battle_stats, p1_battle_stats
            battle_log.append(f"\n🔵 {p2_battle_stats['name'].upper()} goes first (speed tie, decided randomly).")

    # Helper function to calculate actual stat value with modifiers
    def calculate_stat(pokemon, stat_name):
        base_value = pokemon[stat_name]
        modifier = pokemon['stat_mods'].get(stat_name, 0)
        
        # Pokémon stat modifier formula
        multiplier = 1.0
        if modifier > 0:
            multiplier = (2 + modifier) / 2
        elif modifier < 0:
            multiplier = 2 / (2 - modifier)
            
        return int(base_value * multiplier)

    # Battle loop
    turn = 0
    max_turns = 50  # Prevent infinite loops

    while p1_battle_stats['hp'] > 0 and p2_battle_stats['hp'] > 0 and turn < max_turns:
        turn += 1
        battle_log.append(f"\n===== TURN {turn} =====")
        
        # Display current stats
        if attacker == p1_battle_stats:
            battle_log.append(f"🔴 {attacker['name'].upper()} HP: {attacker['hp']}, Status: {attacker['status'] or 'None'}")
            battle_log.append(f"🔵 {defender['name'].upper()} HP: {defender['hp']}, Status: {defender['status'] or 'None'}")
        else:
            battle_log.append(f"🔵 {attacker['name'].upper()} HP: {attacker['hp']}, Status: {attacker['status'] or 'None'}")
            battle_log.append(f"🔴 {defender['name'].upper()} HP: {defender['hp']}, Status: {defender['status'] or 'None'}")

        # Handle status effects
        if attacker['status']:
            # Process status effects based on their type
            if attacker['status'] == 'paralysis':
                # Paralysis: 25% chance to fully paralyze
                if random.random() < 0.25:
                    battle_log.append(f"⚡ {attacker['name'].upper()} is fully paralyzed and cannot move!")
                    attacker, defender = defender, attacker  # Switch turns
                    continue
                # Paralysis also reduces speed
                if 'speed' in attacker and attacker['speed'] > 0:
                    speed_factor = 0.5  # Speed is halved with paralysis
                    battle_log.append(f"⚡ {attacker['name'].upper()}'s speed is reduced due to paralysis.")
            
            elif attacker['status'] == 'poison':
                # Poison: deals 1/8 of max HP as damage each turn
                poison_damage = max(1, attacker['hp'] // 8)
                attacker['hp'] -= poison_damage
                attacker['hp'] = max(0, attacker['hp'])  # Prevent negative HP
                battle_log.append(f"☠️ {attacker['name'].upper()} is hurt by poison! Lost {poison_damage} HP.")
            
            elif attacker['status'] == 'burn':
                # Burn: deals 1/16 of max HP as damage and halves physical attack
                burn_damage = max(1, attacker['hp'] // 16)
                attacker['hp'] -= burn_damage
                attacker['hp'] = max(0, attacker['hp'])
                battle_log.append(f"🔥 {attacker['name'].upper()} is hurt by its burn! Lost {burn_damage} HP.")
                battle_log.append(f"🔥 {attacker['name'].upper()}'s physical attack is halved due to burn.")
            
            elif attacker['status'] == 'sleep':
                # Sleep: Cannot move, has chance to wake up each turn
                if random.random() < 0.34:  # ~1/3 chance to wake up
                    attacker['status'] = None
                    battle_log.append(f"💤 {attacker['name'].upper()} woke up!")
                else:
                    battle_log.append(f"💤 {attacker['name'].upper()} is fast asleep.")
                    attacker, defender = defender, attacker  # Switch turns
                    continue
            
            elif attacker['status'] == 'freeze':
                # Freeze: Cannot move, has chance to thaw each turn
                if random.random() < 0.2:  # 20% chance to thaw
                    attacker['status'] = None
                    battle_log.append(f"❄️ {attacker['name'].upper()} thawed out!")
                else:
                    battle_log.append(f"❄️ {attacker['name'].upper()} is frozen solid!")
                    attacker, defender = defender, attacker  # Switch turns
                    continue
            
            # Status duration management
            if attacker['status_duration'] > 0:
                attacker['status_duration'] -= 1
                if attacker['status_duration'] <= 0 and attacker['status'] not in ['burn', 'poison']:  # Burn/poison are permanent
                    battle_log.append(f"{attacker['name'].upper()} is no longer {attacker['status']}.")
                    attacker['status'] = None
            
            # Check if fainted from status damage
            if attacker['hp'] <= 0:
                battle_log.append(f"☠️ {attacker['name'].upper()} fainted from status effects!")
                break

        # Select a move for the attacker
        if attacker['moves']:
            # Choose a random move that has PP left
            usable_moves = [move for move in attacker['moves'] if move.get('pp', 0) > 0]
            
            if not usable_moves:
                battle_log.append(f"⚠️ {attacker['name'].upper()} has no more usable moves! Using Struggle.")
                # Simulate Struggle (damages user as well)
                chosen_move = {
                    "name": "struggle",
                    "type": "normal",
                    "power": 50,
                    "category": "physical",
                    "accuracy": 100,
                    "pp": 1,
                    "effect_entries": [{"effect": "User takes 1/4 damage dealt as recoil."}]
                }
            else:
                chosen_move = random.choice(usable_moves)
                # Reduce PP
                chosen_move['pp'] = chosen_move.get('pp', 1) - 1
            
            # Display attack information with move details
            battle_log.append(f"\n{attacker['name'].upper()} uses {chosen_move['name'].upper()}!")
            battle_log.append(f"Move Type: {chosen_move['type'].upper()}, Category: {chosen_move['category'].upper()}, Power: {chosen_move['power']}")
            
            # Display move effect
            if chosen_move.get('effect_entries') and len(chosen_move['effect_entries']) > 0:
                effect_text = chosen_move['effect_entries'][0].get('short_effect', '')
                if effect_text:
                    # Replace effect_chance with actual value if present
                    if chosen_move.get('effect_chance') is not None:
                        effect_text = effect_text.replace('$effect_chance', str(chosen_move['effect_chance']))
                    battle_log.append(f"Effect: {effect_text}")
            
            # Check move accuracy
            accuracy = chosen_move.get('accuracy', 100)
            if accuracy is None:
                accuracy = 100  # Some moves always hit
                
            accuracy_check = random.randint(1, 100)
            if accuracy_check > accuracy:
                battle_log.append(f"❌ {attacker['name'].upper()}'s attack missed! (Accuracy check: {accuracy_check}/{accuracy})")
            else:
                # Process move based on category
                if chosen_move['category'] == 'status':
                    battle_log.append("⚙️ It's a status move!")
                    
                    # Apply status effects from move (if applicable)
                    if 'meta' in chosen_move and chosen_move['meta'].get('ailment'):
                        ailment = chosen_move['meta']['ailment']
                        ailment_chance = chosen_move['meta'].get('ailment_chance', 100)
                        
                        if ailment in status_effects and random.randint(1, 100) <= ailment_chance:
                            if not defender['status']:  # Only if not already affected
                                defender['status'] = ailment
                                defender['status_duration'] = random.randint(2, 5)
                                
                                # Display status effect icons
                                status_icon = "⚙️"
                                if ailment == 'paralysis':
                                    status_icon = "⚡"
                                elif ailment == 'poison':
                                    status_icon = "☠️"
                                elif ailment == 'burn':
                                    status_icon = "🔥"
                                elif ailment == 'sleep':
                                    status_icon = "💤"
                                elif ailment == 'freeze':
                                    status_icon = "❄️"
                                
                                battle_log.append(f"{status_icon} {defender['name'].upper()} was afflicted with {ailment}!")
                                battle_log.append(f"✨ Effect successfully applied from {chosen_move['name'].upper()}! ✨")
                            else:
                                battle_log.append(f"⚠️ {defender['name'].upper()} is already affected by {defender['status']}!")
                    
                    # Special handling for specific status moves
                    move_name = chosen_move['name'].lower()
                    
                    # Stat boosting moves
                    if move_name in ['swords-dance', 'dragon-dance', 'nasty-plot', 'calm-mind', 'quiver-dance']:
                        if move_name == 'swords-dance':
                            attacker['stat_mods']['attack'] = min(6, attacker['stat_mods']['attack'] + 2)
                            battle_log.append(f"⬆️⬆️ {attacker['name'].upper()}'s Attack sharply rose! (+2 stages)")
                        elif move_name == 'dragon-dance':
                            attacker['stat_mods']['attack'] = min(6, attacker['stat_mods']['attack'] + 1)
                            attacker['stat_mods']['speed'] = min(6, attacker['stat_mods']['speed'] + 1)
                            battle_log.append(f"⬆️ {attacker['name'].upper()}'s Attack rose! (+1 stage)")
                            battle_log.append(f"⬆️ {attacker['name'].upper()}'s Speed rose! (+1 stage)")
                        elif move_name == 'nasty-plot':
                            attacker['stat_mods']['sp_attack'] = min(6, attacker['stat_mods']['sp_attack'] + 2)
                            battle_log.append(f"⬆️⬆️ {attacker['name'].upper()}'s Special Attack sharply rose! (+2 stages)")
                        elif move_name == 'calm-mind':
                            attacker['stat_mods']['sp_attack'] = min(6, attacker['stat_mods']['sp_attack'] + 1)
                            attacker['stat_mods']['sp_defense'] = min(6, attacker['stat_mods']['sp_defense'] + 1)
                            battle_log.append(f"⬆️ {attacker['name'].upper()}'s Special Attack rose! (+1 stage)")
                            battle_log.append(f"⬆️ {attacker['name'].upper()}'s Special Defense rose! (+1 stage)")
                        elif move_name == 'quiver-dance':
                            attacker['stat_mods']['sp_attack'] = min(6, attacker['stat_mods']['sp_attack'] + 1)
                            attacker['stat_mods']['sp_defense'] = min(6, attacker['stat_mods']['sp_defense'] + 1)
                            attacker['stat_mods']['speed'] = min(6, attacker['stat_mods']['speed'] + 1)
                            battle_log.append(f"⬆️ {attacker['name'].upper()}'s Special Attack rose! (+1 stage)")
                            battle_log.append(f"⬆️ {attacker['name'].upper()}'s Special Defense rose! (+1 stage)")
                            battle_log.append(f"⬆️ {attacker['name'].upper()}'s Speed rose! (+1 stage)")
                        battle_log.append(f"✨ {chosen_move['name'].upper()} successfully boosted stats! ✨")

                    # Recovery moves
                    elif move_name in ['recover', 'rest', 'roost', 'synthesis', 'moonlight', 'morning-sun']:
                        max_hp = p1_battle_stats['hp'] if attacker == p1_battle_stats else p2_battle_stats['hp']
                        heal_amount = 0
                        
                        if move_name == 'rest':
                            # Rest: Heal to full HP but fall asleep for 2 turns
                            heal_amount = max_hp - attacker['hp']
                            attacker['status'] = 'sleep'
                            attacker['status_duration'] = 2
                            battle_log.append(f"💤 {attacker['name'].upper()} fell asleep and restored its health!")
                        else:
                            # Standard recovery moves: Recover 50% of max HP
                            heal_amount = max(1, max_hp // 2)
                        
                        old_hp = attacker['hp']
                        attacker['hp'] = min(max_hp, attacker['hp'] + heal_amount)
                        battle_log.append(f"💚 {attacker['name'].upper()} recovered {attacker['hp'] - old_hp} HP! ({old_hp} → {attacker['hp']})")
                        battle_log.append(f"✨ {chosen_move['name'].upper()} successfully restored health! ✨")
                    
                    # Special defensive moves
                    elif move_name in ['protect', 'detect', 'king\'s-shield', 'spiky-shield', 'baneful-bunker']:
                        attacker['protected'] = True
                        battle_log.append(f"🛡️ {attacker['name'].upper()} protected itself!")
                        battle_log.append(f"✨ {chosen_move['name'].upper()} successfully activated protection! ✨")
                    
                    # Apply stat changes (general case for other status moves)
                    if chosen_move.get('stat_changes'):
                        for change in chosen_move['stat_changes']:
                            stat = change['stat']
                            change_value = change['change']
                            
                            if stat in defender['stat_mods']:
                                old_mod = defender['stat_mods'][stat]
                                # Ensure stat mods stay within -6 to +6 range
                                defender['stat_mods'][stat] = max(-6, min(6, old_mod + change_value))
                                
                                if change_value > 0:
                                    symbols = "⬆️" * min(3, abs(change_value))
                                    battle_log.append(f"{symbols} {defender['name'].upper()}'s {stat} rose! (+{change_value} stages)")
                                else:
                                    symbols = "⬇️" * min(3, abs(change_value))
                                    battle_log.append(f"{symbols} {defender['name'].upper()}'s {stat} fell! ({change_value} stages)")
                                battle_log.append(f"✨ Stat change from {chosen_move['name'].upper()} was successful! ✨")
                
                elif chosen_move['category'] in ['physical', 'special']:
                    # Calculate damage
                    move_power = chosen_move.get('power', 40)
                    if move_power is None:  # Some moves have no power
                        move_power = 0
                    
                    # Use the appropriate attack/defense stats
                    if chosen_move['category'] == 'physical':
                        atk_stat = calculate_stat(attacker, 'attack')
                        def_stat = calculate_stat(defender, 'defense')
                        
                        # Apply burn attack reduction
                        if attacker['status'] == 'burn':
                            atk_stat = atk_stat // 2
                            battle_log.append(f"🔥 {attacker['name'].upper()}'s physical attack is halved due to burn!")
                    else:  # special
                        atk_stat = calculate_stat(attacker, 'sp_attack')
                        def_stat = calculate_stat(defender, 'sp_defense')
                    
                    # Base damage calculation (simplified)
                    level = 50  # Assume level 50 for battles
                    base_damage = (((2 * level / 5) + 2) * move_power * (atk_stat / def_stat)) / 50 + 2
                    
                    # Get the move type
                    move_type = chosen_move['type']
                    
                    # Calculate type effectiveness
                    effectiveness = 1.0
                    type_chart = TYPE_CHART_CACHE
                    
                    for def_type in defender['types']:
                        if move_type in type_chart and def_type in type_chart[move_type]:
                            type_modifier = type_chart[move_type][def_type]
                            effectiveness *= type_modifier
                    
                    # Check for protected status
                    if defender.get('protected', False):
                        battle_log.append(f"🛡️ {defender['name'].upper()} protected itself from the attack!")
                        battle_log.append(f"❌ {chosen_move['name'].upper()} was blocked completely!")
                        # Remove protection after this turn
                        defender['protected'] = False
                        effectiveness = 0
                    
                    # Same Type Attack Bonus (STAB)
                    stab = 1.5 if move_type in attacker['types'] else 1.0
                    
                    # Critical hit chance (base 6.25% or 1/16)
                    crit = 1.0
                    crit_chance = chosen_move.get('meta', {}).get('crit_rate', 0)
                    base_crit_chance = 6.25  # 6.25% base chance
                    adjusted_crit_chance = base_crit_chance * (1 + crit_chance)  # Each stage increases the chance
                    
                    if random.random() * 100 < adjusted_crit_chance:
                        crit = 1.5
                        battle_log.append(f"💥 A critical hit! x1.5 damage!")
                    
                    # Random factor (0.85 to 1.0)
                    random_factor = random.uniform(0.85, 1.0)
                    
                    # Calculate final damage
                    damage = int(base_damage * effectiveness * stab * crit * random_factor)
                    
                    # Display detailed damage calculation info
                    battle_log.append(f"Base damage: {int(base_damage)} (Attack: {atk_stat} / Defense: {def_stat})")
                    
                    # Display effectiveness messages
                    if effectiveness > 1.5:
                        battle_log.append(f"⭐⭐ It's super effective! (x{effectiveness}) ⭐⭐")
                    elif effectiveness > 1:
                        battle_log.append(f"⭐ It's super effective! (x{effectiveness}) ⭐")
                    elif effectiveness < 0.5 and effectiveness > 0:
                        battle_log.append(f"⚫⚫ It's not very effective... (x{effectiveness}) ⚫⚫")
                    elif effectiveness < 1:
                        battle_log.append(f"⚫ It's not very effective... (x{effectiveness}) ⚫")
                    elif effectiveness == 0:
                        battle_log.append(f"❌ It doesn't affect {defender['name'].upper()}... (x0)")
                        damage = 0
                    
                    # Apply STAB message
                    if stab > 1:
                        battle_log.append(f"💥 Same Type Attack Bonus for {attacker['name'].upper()}! (x1.5)")
                    
                    # Special handling for specific damaging moves
                    move_name = chosen_move['name'].lower()
                    
                    # High critical hit ratio moves
                    if move_name in ['slash', 'karate-chop', 'razor-leaf', 'crabhammer', 'cross-chop', 'air-cutter']:
                        if crit > 1.0:
                            battle_log.append(f"🎯 {chosen_move['name'].upper()} has a high critical hit ratio and landed a critical hit!")
                            
                    # Special effect moves
                    if move_name == 'earthquake' and 'flying' not in defender['types']:
                        battle_log.append(f"💥 {chosen_move['name'].upper()} shook the ground violently!")
                        
                    elif move_name == 'surf':
                        battle_log.append(f"🌊 A huge wave crashed over {defender['name'].upper()}!")
                        
                    elif move_name == 'hyper-beam':
                        attacker['recharge'] = True
                        battle_log.append(f"💢 {attacker['name'].upper()} must recharge next turn!")
                        
                    elif move_name == 'fire-blast' and effectiveness > 0:
                        if random.random() < 0.10 and not defender['status']:  # 10% burn chance
                            defender['status'] = 'burn'
                            defender['status_duration'] = -1  # Permanent until cured
                            battle_log.append(f"🔥 {defender['name'].upper()} was burned by Fire Blast!")
                            
                    elif move_name == 'thunder' and effectiveness > 0:
                        if random.random() < 0.30 and not defender['status']:  # 30% paralysis chance
                            defender['status'] = 'paralysis'
                            defender['status_duration'] = -1  # Permanent until cured
                            battle_log.append(f"⚡ {defender['name'].upper()} was paralyzed by Thunder!")
                    
                    # Multi-hit moves
                    if chosen_move.get('meta', {}).get('max_hits', 1) > 1:
                        min_hits = chosen_move['meta'].get('min_hits', 1)
                        max_hits = chosen_move['meta'].get('max_hits', 1)
                        num_hits = random.randint(min_hits, max_hits)
                        total_damage = damage * num_hits
                        damage = total_damage  # Update the damage value
                        battle_log.append(f"🔄 {chosen_move['name'].upper()} hit {num_hits} times for a total of {total_damage} damage!")
                    
                    # Ensure minimum damage of 1 if the move affects the target
                    if effectiveness > 0 and move_power > 0:
                        damage = max(1, damage)
                    else:
                        damage = 0
                    
                    # Apply damage
                    defender['hp'] -= damage
                    defender['hp'] = max(0, defender['hp'])  # Prevent negative HP
                    
                    battle_log.append(f"💥 {defender['name'].upper()} took {damage} damage. Remaining HP: {defender['hp']}")
                    
                    # Handle recoil damage (like Struggle)
                    if chosen_move.get('name') == 'struggle' or (chosen_move.get('meta') and chosen_move['meta'].get('drain', 0) < 0):
                        recoil_percent = abs(chosen_move.get('meta', {}).get('drain', 25))
                        recoil_damage = max(1, int(damage * (recoil_percent / 100)))
                        attacker['hp'] -= recoil_damage
                        attacker['hp'] = max(0, attacker['hp'])
                        battle_log.append(f"↩️ {attacker['name'].upper()} is damaged by recoil! Lost {recoil_damage} HP.")
                    
                    # Healing moves (drain)
                    if chosen_move.get('meta') and chosen_move['meta'].get('drain', 0) > 0:
                        drain_percent = chosen_move['meta']['drain']
                        heal_amount = max(1, int(damage * (drain_percent / 100)))
                        old_hp = attacker['hp']
                        max_hp = p1_battle_stats['hp'] if attacker == p1_battle_stats else p2_battle_stats['hp']
                        attacker['hp'] = min(max_hp, attacker['hp'] + heal_amount)
                        battle_log.append(f"💚 {attacker['name'].upper()} absorbed {heal_amount} HP! ({old_hp} → {attacker['hp']})")
                    
                    # Secondary effect chance
                    effect_chance = chosen_move.get('effect_chance', 0)
                    if effect_chance and random.randint(1, 100) <= effect_chance:
                        battle_log.append(f"✨ Secondary effect of {chosen_move['name'].upper()} triggered! ({effect_chance}% chance) ✨")
                        # Apply secondary effects like status or stat changes
                        if 'meta' in chosen_move and chosen_move['meta'].get('ailment') and chosen_move['meta']['ailment'] != 'none':
                            ailment = chosen_move['meta']['ailment']
                            if ailment in status_effects and not defender['status'] and effectiveness > 0:
                                defender['status'] = ailment
                                defender['status_duration'] = random.randint(2, 5)
                                
                                # Display status effect icons
                                status_icon = "⚙️"
                                if ailment == 'paralysis':
                                    status_icon = "⚡"
                                elif ailment == 'poison':
                                    status_icon = "☠️"
                                elif ailment == 'burn':
                                    status_icon = "🔥"
                                elif ailment == 'sleep':
                                    status_icon = "💤"
                                elif ailment == 'freeze':
                                    status_icon = "❄️"
                                
                                battle_log.append(f"{status_icon} {defender['name'].upper()} was afflicted with {ailment} as a secondary effect!")
                
                # Handle flinch chance
                if chosen_move.get('meta') and chosen_move['meta'].get('flinch_chance'):
                    flinch_chance = chosen_move['meta']['flinch_chance']
                    if random.randint(1, 100) <= flinch_chance:
                        defender['flinch'] = True
                        battle_log.append(f"😵 {defender['name'].upper()} flinched from {chosen_move['name'].upper()}! ({flinch_chance}% chance)")

        # Check if defender fainted
        if defender['hp'] <= 0:
            battle_log.append(f"☠️ {defender['name'].upper()} fainted!")
            break
        
        # If attacker needs to recharge, they can't move next turn
        if attacker.get('recharge'):
            battle_log.append(f"💢 {attacker['name'].upper()} must recharge!")
            attacker.pop('recharge')  # Remove recharge status after this turn
            attacker, defender = defender, attacker  # Switch roles
        # If defender flinched, they lose their turn
        elif defender.get('flinch'):
            battle_log.append(f"😵 {defender['name'].upper()} can't move due to flinch!")
            defender.pop('flinch')  # Remove flinch status after one turn
            # Don't switch roles - the attacker gets to go again
        else:
            # Switch roles normally
            attacker, defender = defender, attacker
    
    # Determine winner
    winner = None
    if p1_battle_stats['hp'] <= 0 and p2_battle_stats['hp'] > 0:
        winner = p2_battle_stats['name']
        battle_log.append(f"\n🏆 {p2_battle_stats['name'].upper()} wins the battle! 🏆")
    elif p2_battle_stats['hp'] <= 0 and p1_battle_stats['hp'] > 0:
        winner = p1_battle_stats['name']
        battle_log.append(f"\n🏆 {p1_battle_stats['name'].upper()} wins the battle! 🏆")
    elif turn >= max_turns:
        battle_log.append(f"\n⌛ The battle reached the maximum turn limit ({max_turns})!")
        # Simplistic draw or HP comparison for winner if max turns reached
        if p1_battle_stats['hp'] > p2_battle_stats['hp']:
            winner = p1_battle_stats['name']
            battle_log.append(f"🏆 {p1_battle_stats['name'].upper()} wins by HP comparison! 🏆")
        elif p2_battle_stats['hp'] > p1_battle_stats['hp']:
            winner = p2_battle_stats['name']
            battle_log.append(f"🏆 {p2_battle_stats['name'].upper()} wins by HP comparison! 🏆")
        else:
            winner = "Draw"
            battle_log.append(f"🤝 It's a draw! Both Pokémon have equal HP remaining.")
    else:  # Both fainted (e.g. from recoil, status at same time)
        winner = "Draw (Both fainted)"
        battle_log.append(f"\n🤝 It's a draw! Both Pokémon fainted.")
    
    # Battle summary
    battle_log.append(f"\n" + "="*50)
    battle_log.append(f"BATTLE SUMMARY")
    battle_log.append("="*50)
    
    if winner != "Draw" and winner != "Draw (Both fainted)":
        if winner == p1_battle_stats['name']:
            battle_log.append(f"Winner: 🔴 {p1_battle_stats['name'].upper()} with {p1_battle_stats['hp']} HP remaining")
            battle_log.append(f"Loser:  🔵 {p2_battle_stats['name'].upper()} with {p2_battle_stats['hp']} HP remaining")
        else:
            battle_log.append(f"Winner: 🔵 {p2_battle_stats['name'].upper()} with {p2_battle_stats['hp']} HP remaining")
            battle_log.append(f"Loser:  🔴 {p1_battle_stats['name'].upper()} with {p1_battle_stats['hp']} HP remaining")
    else:
        battle_log.append(f"Result: Draw")
        battle_log.append(f"🔴 {p1_battle_stats['name'].upper()}: {p1_battle_stats['hp']} HP remaining")
        battle_log.append(f"🔵 {p2_battle_stats['name'].upper()}: {p2_battle_stats['hp']} HP remaining")
    
    battle_log.append(f"Number of turns: {turn}")
    
    # Add effectiveness summary
    battle_log.append("\nType Effectiveness Summary:")
    battle_log.append(f"🔴 {p1_battle_stats['name'].upper()} ({'/'.join(p1_battle_stats['types']).upper()}) VS 🔵 {p2_battle_stats['name'].upper()} ({'/'.join(p2_battle_stats['types']).upper()})")
    
    # Show status effects that occurred
    if p1_battle_stats.get('status') or p2_battle_stats.get('status'):
        battle_log.append("\nStatus Effects:")
        if p1_battle_stats.get('status'):
            battle_log.append(f"🔴 {p1_battle_stats['name'].upper()} was affected by {p1_battle_stats['status']}")
        if p2_battle_stats.get('status'):
            battle_log.append(f"🔵 {p2_battle_stats['name'].upper()} was affected by {p2_battle_stats['status']}")
    
    return {"battle_log": battle_log, "winner": winner}

# We'll need to import this file in pokemcp_server/server.py as well. 