"""
Step 10 — Environment Test
Verifies: Python, Pandas, NumPy, SQLAlchemy, psycopg2, dotenv
Run: venv/bin/python tests/test_environment.py
"""
import sys
import os

def check(label: str, fn):
    try:
        result = fn()
        print(f"  ✓  {label}: {result}")
        return True
    except Exception as e:
        print(f"  ✗  {label}: {e}")
        return False

print("\n" + "=" * 50)
print("  ENVIRONMENT CHECK")
print("=" * 50)

results = []

# Python
results.append(check("Python", lambda: sys.version.split()[0]))

# pandas
results.append(check("Pandas", lambda: __import__("pandas").__version__))

# numpy
results.append(check("NumPy", lambda: __import__("numpy").__version__))

# SQLAlchemy
results.append(check("SQLAlchemy", lambda: __import__("sqlalchemy").__version__))

# psycopg2
results.append(check("psycopg2", lambda: __import__("psycopg2").__version__))

# python-dotenv
results.append(check("python-dotenv", lambda: __import__("importlib.metadata", fromlist=["version"]).version("python-dotenv")))

# .env file readable
def check_env():
    from dotenv import load_dotenv
    load_dotenv()
    host = os.getenv("POSTGRES_HOST", "NOT SET")
    return f"POSTGRES_HOST={host}"
results.append(check(".env readable", check_env))

# PostgreSQL connection
def check_pg():
    from dotenv import load_dotenv
    load_dotenv()
    from sqlalchemy import create_engine, text
    url = (
        f"postgresql+psycopg2://"
        f"{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}"
        f"/{os.getenv('POSTGRES_DB')}"
    )
    engine = create_engine(url)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar()
    return version.split(",")[0]
results.append(check("PostgreSQL connection", check_pg))

print("=" * 50)
passed = sum(results)
total = len(results)
print(f"\n  Result: {passed}/{total} checks passed")

if passed == total:
    print("  ✅  All systems ready!\n")
else:
    print("  ⚠️   Some checks failed — see above\n")
    if not results[-1]:
        print("  NOTE: PostgreSQL connection failure is expected")
        print("        if you haven't created 'ecommerce_db' yet.\n")
