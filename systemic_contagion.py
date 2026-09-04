import streamlit as st
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

# --- 1. QUANTITATIVE SYSTEMIC RISK ENGINE ---

class InterbankContagionEngine:
    def __init__(self, bank_names, tier1_capital, interbank_matrix):
        """
        Models interbank counterparty contagion networks.
        interbank_matrix: 2D array where matrix[i][j] is the loan amount from Bank i to Bank j.
        """
        self.names = bank_names
        self.num_banks = len(bank_names)
        self.initial_capital = np.array(tier1_capital, dtype=float)
        self.interbank_matrix = np.array(interbank_matrix, dtype=float)
        
    def simulate_systemic_shock(self, trigger_bank_idx, recovery_rate=0.40):
        """
        Simulates a Furfine-style domino default cascade across the banking network.
        """
        capital = self.initial_capital.copy()
        defaulted = np.zeros(self.num_banks, dtype=bool)
        
        # Trigger the initial systemic failure
        defaulted[trigger_bank_idx] = True
        capital[trigger_bank_idx] = 0.0
        
        new_defaults = True
        cascade_rounds = 0
        
        # Track cascade history for network color-coding
        cascade_history = {self.names[trigger_bank_idx]: 0} # {Bank Name: Round Defaulted}
        
        while new_defaults:
            new_defaults = False
            cascade_rounds += 1
            
            # Scan each active bank for asset impairment
            for i in range(self.num_banks):
                if defaulted[i]:
                    continue
                
                # Calculate loss from counterparties that have defaulted
                total_loss = 0.0
                for j in range(self.num_banks):
                    if defaulted[j]:
                        # Loss = Exposure * (1 - Recovery Rate)
                        total_loss += self.interbank_matrix[i][j] * (1 - recovery_rate)
                
                # Impair the bank's capital pool
                current_capital = self.initial_capital[i] - total_loss
                capital[i] = max(0.0, current_capital)
                
                # Check for insolvency threshold breach
                if capital[i] <= 0:
                    defaulted[i] = True
                    new_defaults = True
                    cascade_history[self.names[i]] = cascade_rounds
                    
        total_system_loss_pct = (1 - (np.sum(capital) / np.sum(self.initial_capital))) * 100
        
        return {
            "Trigger Asset": self.names[trigger_bank_idx],
            "Total Default Count": int(np.sum(defaulted)),
            "Defaulted List": [self.names[idx] for idx, d in enumerate(defaulted) if d],
            "Systemic Capital Destruction (%)": total_system_loss_pct,
            "Rounds to Stabilization": cascade_rounds,
            "Cascade History": cascade_history,
            "Final Capital Pool": capital
        }

# --- 2. STREAMLIT INTERFACE & DYNAMIC CONTROL DECK ---

st.set_page_config(page_title="Systemic Contagion Engine", layout="wide")
st.title("Systemic Interbank Contagion & Default Cascade Engine")
st.markdown("Model financial institutions as nodes in an interconnected network and simulate Furfine domino cascades driven by counterparty defaults.")

# Sidebar Controls
st.sidebar.header("Network & Distress Parameters")

recovery_slider = st.sidebar.slider("Asset Recovery Rate on Default (%)", 0, 100, 40) / 100
severity_slider = st.sidebar.slider("Interbank Exposure Severity Multiplier", 1.0, 3.0, 1.5, step=0.1)

# Base Bank Metadata Setup
bank_names = ["GlobalMegaBank", "RegionalCredit", "ShadowLender", "RetailFintech", "ClearHouse Hub"]
base_capital = [500_000_000, 120_000_000, 80_000_000, 45_000_000, 250_000_000] # Tier 1 Capital

# Standardized Interbank Borrowing Matrix (Rows = Lenders, Columns = Borrowers)
base_loans_matrix = np.array([
    [0, 150_000_000, 40_000_000, 10_000_000, 200_000_000], # GlobalMegaBank lent to others
    [20_000_000, 0, 95_000_000, 5_000_000, 50_000_000],  # RegionalCredit lent to others
    [10_000_000, 85_000_000, 0, 15_000_000, 10_000_000],  # ShadowLender lent to others
    [5_000_000, 10_000_000, 30_000_000, 0, 50_000_000],   # RetailFintech lent to others
    [150_000_000, 50_000_000, 10_000_000, 20_000_000, 0]  # ClearHouse Hub lent to others
])

# Scale exposures dynamically using the sidebar severity factor
stressed_loans_matrix = base_loans_matrix * severity_slider

st.sidebar.subheader("Trigger Idiosyncratic Collapse")
trigger_choice = st.sidebar.selectbox("Select Institution to Fail Initial Shock", bank_names, index=2)
trigger_idx = bank_names.index(trigger_choice)

# --- 3. EXECUTE RISK CASCADE MATH ---
engine = InterbankContagionEngine(bank_names, base_capital, stressed_loans_matrix)
report = engine.simulate_systemic_shock(trigger_bank_idx=trigger_idx, recovery_rate=recovery_slider)

# Display KPI Report Cards
st.markdown("### Systemic Fragility Assessment")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Initial Instigator Failure", report['Trigger Asset'])
c2.metric("Total Bank Failures", f"{report['Total Default Count']} / {len(bank_names)}")
c3.metric("Systemic Capital Loss", f"{report['Systemic Capital Destruction (%)']:.2f}%")
c4.metric("Cascade Steps to Stability", report['Rounds to Stabilization'])

st.markdown("---")
chart_col, data_col = st.columns([3, 2])

with chart_col:
    st.subheader("Network Topology Contagion Map")
    st.markdown("Directed arrows indicate loan directions (Lender → Borrower). Nodes resize based on remaining Tier 1 capital.")
    
    # Initialize NetworkX Directed Graph
    G = nx.DiGraph()
    
    # Add nodes and edges with weights
    for i, name in enumerate(bank_names):
        G.add_node(name, size=max(10, report['Final Capital Pool'][i]))
        
    for i in range(len(bank_names)):
        for j in range(len(bank_names)):
            if stressed_loans_matrix[i][j] > 0:
                G.add_edge(bank_names[i], bank_names[j], weight=stressed_loans_matrix[i][j])
                
    # Build Node Color Codes based on Cascade History
    node_colors = []
    for name in bank_names:
        if name not in report['Cascade History']:
            node_colors.append('#2ca02c') # Safe / Non-defaulted = Green
        elif report['Cascade History'][name] == 0:
            node_colors.append('#d62728') # Trigger default node = Red
        else:
            node_colors.append('#ff7f0e') # Cascaded default node = Orange
            
    # Draw Graph Topologies
    fig, ax = plt.subplots(figsize=(7, 5))
    pos = nx.kamada_kawai_layout(G) # Clean proportional network layout
    
    # Node sizing multiplier for clear dashboard display
    node_sizes = [max(300, report['Final Capital Pool'][i] / 500000) for i in range(len(bank_names))]
    
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight="bold", font_family="sans-serif", ax=ax)
    nx.draw_networkx_edges(G, pos, arrowstyle="->", arrowsize=15, edge_color="gray", width=1.5, ax=ax)
    
    ax.axis('off')
    st.pyplot(fig, use_container_width=True)

with data_col:
    st.subheader("Systemic Cascade Progression Log")
    st.markdown("Chronological tracking of capital erosion and domino breakdowns:")
    
    st.error(f"**Round 0 (Initial Shock):** {report['Trigger Asset']} suffers a non-recoverable asset write-down and goes insolvent.")
    
    # Sort history to list breakdown sequence
    sorted_history = sorted(report['Cascade History'].items(), key=lambda x: x[1])
    
    for name, r in sorted_history:
        if r == 0:
            continue
        st.warning(f"**Round {r} Contagion Wave:** {name}'s capital reserves hit 0.00% due to exposure haircuts from defaulted counterparts. Bank falls into default.")
        
    # Check if any banks survived intact
    survivors = [name for name in bank_names if name not in report['Cascade History']]
    if survivors:
        st.success(f"**System Stabilized:** Remaining compliant institutions with safe capital buffers: {', '.join(survivors)}")
    else:
        st.error("**Complete Systemic Collapse:** Every institution within the testing perimeter has been fully depleted.")
