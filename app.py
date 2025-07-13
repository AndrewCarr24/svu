
import streamlit as st
import pandas as pd
import requests
from PIL import Image
from io import BytesIO

# Set wider sidebar and improve button styling
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        min-width: 300px;
        max-width: 400px;
        width: 300px;
    }
    [data-testid="stSidebar"] button {
        min-width: 36px;
        text-align: center;
        padding: 0.1rem 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# Load data
@st.cache_data
def load_data():
    return pd.read_csv("output_data/law_and_order_svu_episodes.csv")

df = load_data()

# App title
st.title("Law & Order: SVU Episode Explorer")



# Sidebar filters
st.sidebar.header("Filters")
seasons = sorted(df["Season"].unique())
# Add Select Season title
st.sidebar.markdown("**Select Season**")
# Grid of season buttons (Streamlit native)
n_cols = 5  # Number of columns in the grid
season_cols = st.sidebar.columns(n_cols)
if "selected_season" not in st.session_state:
    st.session_state.selected_season = seasons[0]
for idx, season in enumerate(seasons):
    col = season_cols[idx % n_cols]
    if col.button(str(season), key=f"season_btn_{season}"):
        st.session_state.selected_season = season
selected_season = st.session_state.selected_season


# Search bar (searches across all episodes) - move to sidebar
search_bar_html = """
<div style='margin-bottom:0.8rem; font-weight:bold;'>Search All Episodes</div>
"""
st.sidebar.markdown(search_bar_html, unsafe_allow_html=True)
search_term = st.sidebar.text_input("Search All Episodes", "", label_visibility="collapsed")

# Filter by season
filtered_data = df[df["Season"] == selected_season]

# If search term is provided, filter across all episodes
if search_term.strip():
    search_lower = search_term.lower()
    search_mask = (
        df["Title"].str.lower().str.contains(search_lower, na=False) |
        df["Description"].str.lower().str.contains(search_lower, na=False)
    )
    filtered_data = df[search_mask]
    st.header(f"Search Results for '{search_term}' ({len(filtered_data)} episodes found)")
else:
    st.header(f"Season {selected_season}")
    st.write(f"Episodes: {len(filtered_data)}")

# Show episode list (single pane, larger images)
for _, episode in filtered_data.iterrows():
    col1, col2 = st.columns([1, 3])
    with col1:
        if pd.notna(episode["Image URL"]):
            try:
                response = requests.get(episode["Image URL"])
                if response.status_code == 200:
                    st.markdown(
                        f'<img src="{episode["Image URL"]}" style="display:block;margin:auto;width:100%;max-width:600px;height:auto;">',
                        unsafe_allow_html=True
                    )
                else:
                    st.write("Image not available")
            except:
                st.write("Image not available")
    with col2:
        st.markdown(f'<div style="font-size:1.3em;font-weight:600;line-height:1.2;">S{episode["Season"]}E{episode["Episode"]} - {episode["Title"]}</div>', unsafe_allow_html=True)
        st.write(f"Air Date: {episode['Air Date']}")
        if pd.notna(episode["Rating"]):
            st.write(f"Rating: {episode['Rating']}/10")
        st.write(episode["Description"])
        st.divider()