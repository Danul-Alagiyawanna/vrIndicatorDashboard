"""Update E1 indicator unit from 'USD bn' to 'bn' in Supabase."""
import os
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

result = client.table("indicators").update({"unit": "bn"}).eq("id", "E1").execute()
print(f"Updated E1 unit: {result.data}")
