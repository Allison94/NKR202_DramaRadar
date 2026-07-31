from domains.store.service import get_dashboard_dataframe

df = get_dashboard_dataframe()
print("rows:", len(df))
print(df[["name", "__data_source", "intensity", "review_text"]].head(2).to_string(index=False))
