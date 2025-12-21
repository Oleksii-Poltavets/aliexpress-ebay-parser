import pandas as pd

df = pd.read_csv('1_results.csv')
print('Description details:\n')
for i, row in df.iterrows():
    desc = row['description']
    print(f"Product {i+1}: {row['title'][:50]}...")
    print(f"Description length: {len(str(desc)) if pd.notna(desc) else 0} characters")
    if pd.notna(desc):
        print(f"First 200 chars: {str(desc)[:200]}...")
    print()
