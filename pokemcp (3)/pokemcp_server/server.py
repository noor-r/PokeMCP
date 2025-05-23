from mcp.server.fastmcp import Context
import sys # Import sys for stderr
import traceback # Import traceback
import asyncio
import json
import httpx
import random

# Import the mcp instance
from pokemcp_server.mcp_instance import mcp

# Function to fetch Pokémon data
async def fetch_pokemon_data(name: str) -> dict:
    """Helper function to fetch Pokémon data from the PokeAPI."""
    base_url = "https://pokeapi.co/api/v2/pokemon"
    
    print(f"Fetching data for {name} from PokeAPI", file=sys.stderr)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/{name.lower()}")
        response.raise_for_status()
        data = response.json()
        
        stats = {s['stat']['name']: s['base_stat'] for s in data['stats']}
        types = [t['type']['name'] for t in data['types']]
        abilities = [a['ability']['name'] for a in data['abilities']]
        moves = [m['move']['name'] for m in data['moves']]
        
        species_url = data['species']['url']
        species_response = await client.get(species_url)
        species_response.raise_for_status()
        species_data = species_response.json()
        
        evolution_chain_url = species_data['evolution_chain']['url']
        evolution_response = await client.get(evolution_chain_url)
        evolution_response.raise_for_status()
        evolution_data = evolution_response.json()
        
        evolutions = []
        current_evolution = evolution_data['chain']
        while current_evolution:
            evolutions.append(current_evolution['species']['name'])
            if current_evolution['evolves_to']:
                current_evolution = current_evolution['evolves_to'][0] 
            else:
                current_evolution = None

        return {
            "name": data['name'],
            "id": data['id'],
            "base_stats": stats,
            "types": types,
            "abilities": abilities,
            "moves": moves,
            "evolution_chain": evolutions
        }

# Define all resources explicitly with specific MIME types

@mcp.resource("hello://world", mime_type="text/plain")
async def hello_world() -> bytes:
    """A simple Hello World resource to test the MCP setup."""
    print("Hello resource accessed", file=sys.stderr)
    return "Hello from PokemonMCPServer!".encode('utf-8')

@mcp.resource("directpokemon://{name}", mime_type="text/plain")
async def direct_pokemon(name: str) -> bytes:
    """A direct Pokemon resource test within server.py."""
    print(f"Direct Pokemon resource accessed for {name}", file=sys.stderr)
    return f"Direct Pokemon resource for {name} from server.py!".encode('utf-8')

# Register the pokemon resource directly in server.py to ensure it's available
@mcp.resource("pokemon://{name}", mime_type="application/json")
async def get_pokemon_details(name: str) -> bytes:
    """Fetches detailed information for a given Pokémon by its name."""
    try:
        print(f"Fetching pokemon data for: {name} (server.py)", file=sys.stderr)
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://pokeapi.co/api/v2/pokemon/{name.lower()}")
            response.raise_for_status()
            data = response.json()
            
            stats = {s['stat']['name']: s['base_stat'] for s in data['stats']}
            types = [t['type']['name'] for t in data['types']]
            abilities = [a['ability']['name'] for a in data['abilities']]
            moves = [m['move']['name'] for m in data['moves']]
            
            species_url = data['species']['url']
            species_response = await client.get(species_url)
            species_response.raise_for_status()
            species_data = species_response.json()
            
            evolution_chain_url = species_data['evolution_chain']['url']
            evolution_response = await client.get(evolution_chain_url)
            evolution_response.raise_for_status()
            evolution_data = evolution_response.json()
            
            evolutions = []
            current_evolution = evolution_data['chain']
            while current_evolution:
                evolutions.append(current_evolution['species']['name'])
                if current_evolution['evolves_to']:
                    current_evolution = current_evolution['evolves_to'][0] 
                else:
                    current_evolution = None

            result = {
                "name": data['name'],
                "id": data['id'],
                "base_stats": stats,
                "types": types,
                "abilities": abilities,
                "moves": moves,
                "evolution_chain": evolutions
            }
            
            print(f"Successfully fetched pokemon data for: {name} (server.py)", file=sys.stderr)
            # Return bytes, not str or dict
            return json.dumps(result).encode('utf-8')
    except Exception as e:
        print(f"Error fetching pokemon data for {name}: {e}", file=sys.stderr)
        error_response = {"error": str(e), "message": f"Failed to fetch data for {name}"}
        return json.dumps(error_response).encode('utf-8')

# Battle simulator tool is imported from battle_simulator.py
# We don't define it here to avoid duplicate tool definitions

if __name__ == "__main__":
    try:
        print("Starting PokemonMCPServer...", file=sys.stderr)
        
        # Import modules to register their resources and tools
        import pokemcp_server.battle_simulator
        
        # Note: We now define the pokemon resource directly in server.py
        # so we don't need to import pokemon_data
        
        print("All modules imported successfully", file=sys.stderr)
        
        # Properly print available resources and tools using asyncio
        async def print_resources_and_tools():
            resources = await mcp.list_resources()
            tools = await mcp.list_tools()
            print(f"Available resources: {resources}", file=sys.stderr)
            print(f"Available tools: {tools}", file=sys.stderr)
        
        asyncio.run(print_resources_and_tools())
        
        print("Server is ready to handle requests", file=sys.stderr)
        mcp.run()
    except Exception as e:
        # Ensure error messages go to stderr and are flushed
        print(f"SERVER CRASHED: {type(e).__name__}: {e}", file=sys.stderr)
        print("SERVER TRACEBACK:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise # Re-raise after printing 