"""Delete all L2 readings for IN and SL from Supabase."""
import os
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

for country in ["IN", "SL"]:
    result = client.table("readings").delete().eq("indicator_id", "L2").eq("country_id", country).execute()
    print(f"Deleted L2/{country}: {len(result.data)} rows removed")
