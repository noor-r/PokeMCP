import httpx
import json
import sys
from pokemcp_server.mcp_instance import mcp

BASE_URL = "https://pokeapi.co/api/v2/pokemon"

@mcp.resource("pokemon://{name}", mime_type="application/json")
async def get_pokemon_details(name: str) -> bytes:
    """Fetches detailed information for a given Pokémon by its name."""
    try:
        print(f"Fetching pokemon data for: {name}", file=sys.stderr)
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/{name.lower()}")
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
            
            print(f"Successfully fetched pokemon data for: {name}", file=sys.stderr)
            # Return bytes, not str or dict
            return json.dumps(result).encode('utf-8')
    except Exception as e:
        print(f"Error fetching pokemon data for {name}: {e}", file=sys.stderr)
        error_response = {"error": str(e), "message": f"Failed to fetch data for {name}"}
        return json.dumps(error_response).encode('utf-8')

# To make this resource discoverable, we need to ensure this file is imported
# when the server starts. We'll modify pokemcp_server/server.py to import it. 