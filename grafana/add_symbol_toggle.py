#!/usr/bin/env python3
"""
Add symbol toggle template variable to Grafana dashboards
"""
import json
import sys

def add_symbol_variable(dashboard_data):
    """Add symbol template variable to dashboard"""

    # Template variable configuration
    symbol_variable = {
        "current": {
            "selected": True,
            "text": ["All"],
            "value": ["$__all"]
        },
        "datasource": {
            "type": "postgres",
            "uid": "PostgreSQL"
        },
        "definition": "SELECT DISTINCT symbol FROM silver_gold.gold_daily_prices ORDER BY symbol",
        "hide": 0,
        "includeAll": True,
        "label": "Cryptocurrency",
        "multi": True,
        "name": "symbol",
        "options": [],
        "query": "SELECT DISTINCT symbol FROM silver_gold.gold_daily_prices ORDER BY symbol",
        "refresh": 1,
        "regex": "",
        "skipUrlSync": False,
        "sort": 0,
        "type": "query"
    }

    # Update templating section
    if "templating" not in dashboard_data:
        dashboard_data["templating"] = {"list": []}

    # Check if symbol variable already exists
    existing_symbols = [v for v in dashboard_data["templating"]["list"] if v.get("name") == "symbol"]

    if not existing_symbols:
        dashboard_data["templating"]["list"].append(symbol_variable)

    # Update all panel queries to use the symbol variable
    if "panels" in dashboard_data:
        for panel in dashboard_data["panels"]:
            if "targets" in panel:
                for target in panel["targets"]:
                    if "rawSql" in target and isinstance(target["rawSql"], str):
                        sql = target["rawSql"]

                        # Add WHERE clause if symbol filter makes sense
                        if "FROM silver_gold.gold_daily_prices" in sql or "FROM silver.silver_crypto_prices_cleaned" in sql or "FROM bronze.raw_crypto_prices" in sql:
                            # Only add filter if not already present and if there's no complex CTE
                            if "WHERE symbol IN" not in sql and "$symbol" not in sql:
                                # Simple approach: add symbol filter to WHERE clause
                                if " WHERE " in sql:
                                    # Add to existing WHERE
                                    sql = sql.replace(" WHERE ", " WHERE symbol IN ($symbol) AND ", 1)
                                elif " FROM silver_gold.gold_daily_prices" in sql or " FROM silver.silver_crypto_prices_cleaned" in sql or " FROM bronze.raw_crypto_prices" in sql:
                                    # Find the table and add WHERE after it
                                    for table in ["silver_gold.gold_daily_prices", "silver.silver_crypto_prices_cleaned", "bronze.raw_crypto_prices"]:
                                        if f" FROM {table}" in sql:
                                            # Check if there's already an alias
                                            if f"{table} g" in sql or f"{table}\n" in sql:
                                                # Has alias or newline
                                                parts = sql.split(f"FROM {table}")
                                                if len(parts) == 2:
                                                    # Get the part after FROM
                                                    after_from = parts[1]
                                                    # Find where to insert WHERE
                                                    if "\n" in after_from:
                                                        first_newline = after_from.index("\n")
                                                        sql = parts[0] + f"FROM {table}" + after_from[:first_newline] + f"\n    WHERE symbol IN ($symbol)" + after_from[first_newline:]
                                                    elif "ORDER BY" in after_from:
                                                        sql = sql.replace("ORDER BY", "WHERE symbol IN ($symbol)\n    ORDER BY", 1)
                                                    elif "GROUP BY" in after_from:
                                                        sql = sql.replace("GROUP BY", "WHERE symbol IN ($symbol)\n    GROUP BY", 1)
                                            break

                                target["rawSql"] = sql

    return dashboard_data

def main():
    if len(sys.argv) != 3:
        print("Usage: python add_symbol_toggle.py input.json output.json")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    # Read dashboard
    with open(input_file, 'r') as f:
        dashboard = json.load(f)

    # Add symbol variable
    dashboard = add_symbol_variable(dashboard)

    # Write updated dashboard
    with open(output_file, 'w') as f:
        json.dump(dashboard, f, indent=2)

    print(f"Updated dashboard written to {output_file}")

if __name__ == "__main__":
    main()
