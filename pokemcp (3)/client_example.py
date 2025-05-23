# Client example script for the Pokémon Battle Simulation System

import asyncio
import json
import base64
import sys
import os
import httpx
import random
import platform
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Add a function to get a list of available Pokémon
async def get_random_pokemon(num_pokemon=2, limit=151):
    """Fetch random Pokémon IDs from the PokeAPI."""
    try:
        async with httpx.AsyncClient() as client:
            # Get the list of Pokémon (first generation by default)
            response = await client.get(f"https://pokeapi.co/api/v2/pokemon?limit={limit}")
            response.raise_for_status()
            data = response.json()
            
            pokemon_list = data['results']
            selected_pokemon = random.sample(pokemon_list, num_pokemon)
            return [pokemon['name'] for pokemon in selected_pokemon]
    except Exception as e:
        print(f"Error fetching random Pokémon: {e}")
        # Fallback to classic Pokémon if API fails
        fallback_pokemon = ["pikachu", "charizard", "bulbasaur", "squirtle", "eevee", 
                           "jigglypuff", "mewtwo", "snorlax", "gengar", "gyarados"]
        return random.sample(fallback_pokemon, num_pokemon)

async def main():
    # Platform-specific setup for the virtual environment
    print(f"Detected platform: {platform.system()}")
    
    # Define the command to start your server with platform-independent paths
    if platform.system() == 'Windows':
        python_executable = os.path.join(".venv", "Scripts", "python")
    else:
        # macOS or Linux
        python_executable = os.path.join(".venv", "bin", "python3")
        
        # Check if the python3 executable exists, otherwise try python
        if not os.path.exists(python_executable):
            python_executable = os.path.join(".venv", "bin", "python")
    
    # Check if the executable exists
    if not os.path.exists(python_executable):
        # If virtual environment python isn't found, try using system python
        if platform.system() == 'Windows':
            python_executable = "python"
        else:
            python_executable = "python3"
        print(f"Virtual environment Python not found, using system Python: {python_executable}")
    
    server_command = [python_executable, "-m", "pokemcp_server.server"]

    print(f"Starting server with command: {server_command[0]} {' '.join(server_command[1:])}")
    
    server_params = StdioServerParameters(
        command=server_command[0], # The python interpreter from your venv
        args=server_command[1:]    # The arguments: ["-m", "pokemcp_server.server"]
    )

    print("Attempting to connect to server and list available resources...")

    try:
        async with stdio_client(server_params) as (read_stream, write_stream):
            print("Successfully connected to stdio_client streams.")
            async with ClientSession(read_stream, write_stream) as session:
                print("ClientSession established. Initializing...")
                await session.initialize()
                
                # First list all available resources
                print("Listing available resources:")
                resources = await session.list_resources()
                print(f"Available resources: {resources}")
                
                # Try the simple Hello World resource
                try:
                    print("\nReading simple resource: hello://world")
                    hello_result = await session.read_resource("hello://world")
                    print(f"Raw hello result type: {type(hello_result)}")
                    
                    # Access using the contents attribute
                    hello_contents = hello_result.contents
                    for content in hello_contents:
                        print(f"Content URI: {content.uri}")
                        print(f"Content MIME type: {content.mimeType}")
                        # Decode base64
                        decoded_data = base64.b64decode(content.blob).decode('utf-8')
                        print(f"Content data: {decoded_data}")
                except Exception as e:
                    print(f"Error reading hello://world: {e}")
                
                # Get random Pokémon for this run
                pokemon_names = await get_random_pokemon(2)
                print(f"\n🎲 Randomly selected Pokémon: {', '.join(pokemon_names).upper()} 🎲")
                
                # Try the imported Pokemon resource
                try:
                    # Fetch and display information for multiple Pokémon
                    for pokemon_name in pokemon_names:
                        print(f"\nReading Pokemon resource: pokemon://{pokemon_name}")
                        try:
                            pokemon_result = await session.read_resource(f"pokemon://{pokemon_name}")
                            
                            # Access using the contents attribute
                            pokemon_contents = pokemon_result.contents
                            for content in pokemon_contents:
                                decoded_data = base64.b64decode(content.blob).decode('utf-8')
                                # Parse the JSON
                                pokemon_data = json.loads(decoded_data)
                                
                                # Print Pokémon details in a more formatted way
                                print("\n" + "="*50)
                                print(f"POKÉMON DETAILS: {pokemon_data['name'].upper()}")
                                print("="*50)
                                print(f"Pokédex ID: {pokemon_data['id']}")
                                
                                # Type information
                                types_str = ", ".join(pokemon_data['types'])
                                print(f"Type: {types_str}")
                                
                                # Stats with a nice format
                                print("\nBase Stats:")
                                print(f"  HP:              {pokemon_data['base_stats'].get('hp', 'N/A')}")
                                print(f"  Attack:          {pokemon_data['base_stats'].get('attack', 'N/A')}")
                                print(f"  Defense:         {pokemon_data['base_stats'].get('defense', 'N/A')}")
                                print(f"  Special Attack:  {pokemon_data['base_stats'].get('special-attack', 'N/A')}")
                                print(f"  Special Defense: {pokemon_data['base_stats'].get('special-defense', 'N/A')}")
                                print(f"  Speed:           {pokemon_data['base_stats'].get('speed', 'N/A')}")
                                
                                # Abilities
                                abilities_str = ", ".join(pokemon_data['abilities'])
                                print(f"\nAbilities: {abilities_str}")
                                
                                # Evolution chain
                                evo_chain = " → ".join(pokemon_data['evolution_chain'])
                                print(f"\nEvolution chain: {evo_chain}")
                                
                                # Moves (show only first 5 to save space)
                                print(f"\nSample moves (showing 5 of {len(pokemon_data['moves'])}):")
                                for move in pokemon_data['moves'][:5]:
                                    print(f"  • {move}")
                                    
                                    # Fetch and display move effects for each move
                                    try:
                                        # Create a new client for fetching move data
                                        async with httpx.AsyncClient() as move_client:
                                            move_response = await move_client.get(f"https://pokeapi.co/api/v2/move/{move.lower()}")
                                            move_data = move_response.json()
                                            
                                            # Extract basic move info
                                            move_type = move_data['type']['name']
                                            move_power = move_data.get('power', 'N/A')
                                            move_accuracy = move_data.get('accuracy', 'N/A')
                                            move_category = move_data['damage_class']['name']
                                            
                                            print(f"      Type: {move_type}, Power: {move_power}, Accuracy: {move_accuracy}, Category: {move_category}")
                                            
                                            # Extract effect text
                                            if 'effect_entries' in move_data and move_data['effect_entries']:
                                                effect_text = move_data['effect_entries'][0]['short_effect']
                                                # Replace effect_chance with actual value if present
                                                if move_data.get('effect_chance') is not None:
                                                    effect_text = effect_text.replace('$effect_chance', str(move_data['effect_chance']))
                                                print(f"      Effect: {effect_text}")
                                            
                                            # Add separation between moves
                                            print()
                                    except Exception as move_error:
                                        print(f"      (Failed to load move details: {move_error})")
                                        
                                print()
                        except Exception as e:
                            print(f"Error reading pokemon://{pokemon_name}: {e}")
                            print("Attempting to fetch data directly from PokeAPI...")
                            
                            # Fallback to direct API call
                            async with httpx.AsyncClient() as client:
                                try:
                                    response = await client.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}")
                                    response.raise_for_status()
                                    data = response.json()
                                    
                                    stats = {s['stat']['name']: s['base_stat'] for s in data['stats']}
                                    types = [t['type']['name'] for t in data['types']]
                                    abilities = [a['ability']['name'] for a in data['abilities']]
                                    moves = [m['move']['name'] for m in data['moves']]
                                    
                                    print("\n" + "="*50)
                                    print(f"POKÉMON DETAILS: {data['name'].upper()} (Direct API)")
                                    print("="*50)
                                    print(f"Pokédex ID: {data['id']}")
                                    
                                    # Type information
                                    types_str = ", ".join(types)
                                    print(f"Type: {types_str}")
                                    
                                    # Stats with a nice format
                                    print("\nBase Stats:")
                                    print(f"  HP:              {stats.get('hp', 'N/A')}")
                                    print(f"  Attack:          {stats.get('attack', 'N/A')}")
                                    print(f"  Defense:         {stats.get('defense', 'N/A')}")
                                    print(f"  Special Attack:  {stats.get('special-attack', 'N/A')}")
                                    print(f"  Special Defense: {stats.get('special-defense', 'N/A')}")
                                    print(f"  Speed:           {stats.get('speed', 'N/A')}")
                                    
                                    # Abilities
                                    abilities_str = ", ".join(abilities)
                                    print(f"\nAbilities: {abilities_str}")
                                    
                                    # Moves (show only first 5 to save space)
                                    print(f"\nSample moves (showing 5 of {len(moves)}):")
                                    for move in moves[:5]:
                                        print(f"  • {move}")
                                        
                                        # Fetch and display move effects for each move
                                        try:
                                            # Create a new client for fetching move data
                                            async with httpx.AsyncClient() as move_client:
                                                move_response = await move_client.get(f"https://pokeapi.co/api/v2/move/{move.lower()}")
                                                move_data = move_response.json()
                                                
                                                # Extract basic move info
                                                move_type = move_data['type']['name']
                                                move_power = move_data.get('power', 'N/A')
                                                move_accuracy = move_data.get('accuracy', 'N/A')
                                                move_category = move_data['damage_class']['name']
                                                
                                                print(f"      Type: {move_type}, Power: {move_power}, Accuracy: {move_accuracy}, Category: {move_category}")
                                                
                                                # Extract effect text
                                                if 'effect_entries' in move_data and move_data['effect_entries']:
                                                    effect_text = move_data['effect_entries'][0]['short_effect']
                                                    # Replace effect_chance with actual value if present
                                                    if move_data.get('effect_chance') is not None:
                                                        effect_text = effect_text.replace('$effect_chance', str(move_data['effect_chance']))
                                                    print(f"      Effect: {effect_text}")
                                                
                                                # Add separation between moves
                                                print()
                                        except Exception as move_error:
                                            print(f"      (Failed to load move details: {move_error})")
                                            
                                    print()
                                    
                                except Exception as direct_api_error:
                                    print(f"Error with direct API call: {direct_api_error}")
                except Exception as e:
                    print(f"Error in Pokemon information section: {e}")

                # Try using the tool
                try:
                    print("\nChecking available tools:")
                    tools = await session.list_tools()
                    print(f"Available tools: {tools}")
                    
                    print("\n" + "="*50)
                    print("POKÉMON BATTLE SIMULATION")
                    print("="*50)
                    print(f"Simulating battle between {pokemon_names[0].upper()} and {pokemon_names[1].upper()}...")
                    
                    # Add error handling for the battle simulation
                    try:
                        battle_result = await session.call_tool("simulate_battle", {
                            "pokemon1_name": pokemon_names[0], 
                            "pokemon2_name": pokemon_names[1]
                        })
                        
                        if isinstance(battle_result, dict) and "battle_log" in battle_result:
                            # Format the battle log nicely
                            print("\nBATTLE LOG:")
                            print("-"*80)
                            for line in battle_result["battle_log"]:
                                print(line)
                            print("-"*80)
                            
                            if "winner" in battle_result:
                                print(f"\nWinner: {battle_result['winner'].upper()}")
                        else:
                            # If the result is not what we expected, try to extract the battle log
                            print(f"\nBattle result in unexpected format. Attempting to process...")
                            
                            if hasattr(battle_result, 'content') and len(battle_result.content) > 0:
                                for content in battle_result.content:
                                    if hasattr(content, 'text'):
                                        try:
                                            result_data = json.loads(content.text)
                                            if "battle_log" in result_data:
                                                print("\nBATTLE LOG:")
                                                print("-"*80)
                                                for line in result_data["battle_log"]:
                                                    print(line)
                                                print("-"*80)
                                                
                                                if "winner" in result_data:
                                                    print(f"\nWinner: {result_data['winner'].upper()}")
                                        except json.JSONDecodeError:
                                            print(f"Unable to parse battle result as JSON: {content.text[:200]}...")
                            else:
                                # Last resort: just print the battle result
                                print(f"Battle result: {battle_result}")
                    except Exception as battle_error:
                        print(f"Error in battle simulation: {battle_error}")
                
                except Exception as e:
                    print(f"Error using battle simulator tool: {e}")

    except Exception as e:
        print(f"\n--- CLIENT ERROR ---")
        print(f"An error occurred: {e}")
        print("\nDEBUG INFO: The MCP library often includes server stderr in the exception message above.")
        print("Make sure your MCP server is NOT already running in another terminal when you run this client.")
        print("This client script will start the server process itself.")

if __name__ == "__main__":
    # Run on all platforms consistently
    if platform.system() == 'Windows':
        # Windows uses asyncio's ProactorEventLoop by default in Python 3.8+
        asyncio.run(main())
    else:
        # macOS and Linux
        asyncio.run(main()) 