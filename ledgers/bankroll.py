import pandas as pd
import numpy as np
import random
import matplotlib.pyplot as plt

sims = 10000
bankroll = 20000
weeks = 10
bets_per_week = np.random.poisson(
    15, weeks
)  # Random number of bets per week based on Poisson distribution

edge = 0.05
bet_size = 100
avg_odds = 1.91


def simulate_bet(edge, bet_size, avg_odds):
    # Simulate a single bet outcome
    if random.random() < (0.5 + edge):  # Win condition based on edge
        return bet_size * (avg_odds - 1)  # Profit from winning
    else:
        return -bet_size  # Loss from losing


def simulate_week(bets_per_week, edge, bet_size, avg_odds):
    weekly_profit = 0
    for _ in range(bets_per_week):
        weekly_profit += simulate_bet(edge, bet_size, avg_odds)
    return weekly_profit


def simulate_bankroll(sims, bankroll, weeks, bets_per_week, edge, bet_size, avg_odds):
    results = []
    for _ in range(sims):
        current_bankroll = bankroll
        for week in range(weeks):
            weekly_bets = bets_per_week[week]
            weekly_profit = simulate_week(weekly_bets, edge, bet_size, avg_odds)
            current_bankroll += weekly_profit
        results.append(current_bankroll)
    return results


profit_results = simulate_bankroll(
    sims, bankroll, weeks, bets_per_week, edge, bet_size, avg_odds
)
# Convert results to a DataFrame for analysis
profit_df = pd.DataFrame({"Final_Bankroll": profit_results})

print(
    profit_df.describe()
)  # Print summary statistics of the final bankroll after simulations

plt.hist(profit_results, bins=50, edgecolor="black")
plt.title("Distribution of Final Bankroll After Simulations")
plt.xlabel("Final Bankroll")
plt.ylabel("Frequency")
plt.show()
