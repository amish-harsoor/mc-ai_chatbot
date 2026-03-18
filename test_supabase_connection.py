import psycopg2
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

# Test basic connection to Supabase
host = os.getenv("SUPABASE_HOST")
port = os.getenv("SUPABASE_PORT", "5432")
database = os.getenv("SUPABASE_DATABASE", "postgres")
user = os.getenv("SUPABASE_USER")
password = os.getenv("SUPABASE_PASSWORD")

print("Testing Supabase connection...")
print(f"Host: {host}")
print(f"Port: {port}")
print(f"Database: {database}")
print(f"User: {user}")
print(f"Password: {'*' * len(password) if password else 'EMPTY'}")

if not all([host, user, password]):
    print("ERROR: Missing credentials")
    exit(1)

# URL encode the password
encoded_password = urllib.parse.quote_plus(password)
print(f"URL encoded password: {encoded_password}")

# Try different connection methods
print("\n=== Method 1: Connection string with URL encoding ===")
try:
    conn_str = f"postgresql://{user}:{encoded_password}@{host}:{port}/{database}"
    print(f"Trying: postgresql://{user}:[REDACTED]@{host}:{port}/{database}")
    conn = psycopg2.connect(conn_str)
    print("SUCCESS: Connected with connection string!")
    conn.close()
except Exception as e:
    print(f"FAILED: {e}")

print("\n=== Method 2: Try direct connection (if pooler is the issue) ===")
# Try changing from pooler to direct connection
if "pooler" in host:
    direct_host = host.replace("pooler", "db")
    print(f"Trying direct host: {direct_host}")
    try:
        conn_str = f"postgresql://{user}:{encoded_password}@{direct_host}:{port}/{database}"
        conn = psycopg2.connect(conn_str)
        print("SUCCESS: Connected with direct host!")
        conn.close()
    except Exception as e:
        print(f"FAILED with direct host: {e}")

print("\n=== Method 3: Test with psql command line format ===")
try:
    import subprocess
    cmd = f'psql "postgresql://{user}:{encoded_password}@{host}:{port}/{database}" -c "SELECT version();"'
    print(f"Command: psql \"postgresql://{user}:[REDACTED]@{host}:{port}/{database}\" -c \"SELECT version();\"")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print("SUCCESS: psql command worked!")
        print("Output:", result.stdout[:200])
    else:
        print("FAILED: psql command failed")
        print("Error:", result.stderr[:200])
except Exception as e:
    print(f"FAILED to run psql: {e}")
