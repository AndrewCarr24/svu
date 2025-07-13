
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
        min-width: 370px;
        max-width: 470px;
        width: 370px;
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
# Remove season 27 if present (no data)
seasons = sorted([s for s in df["Season"].unique() if s != 27])
# Add Select Season title
st.sidebar.markdown("**Select Season**")
# Grid of season buttons (Streamlit native)
n_cols = 5  # Number of columns in the grid
season_cols = st.sidebar.columns(n_cols)
if "selected_season" not in st.session_state or st.session_state.selected_season not in seasons:
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

# Rating slider filter
min_rating = float(df["Rating"].min()) if "Rating" in df.columns else 0.0
max_rating = float(df["Rating"].max()) if "Rating" in df.columns else 10.0
rating_range = st.sidebar.slider(
    "Filter by IMDb Rating",
    min_value=min_rating,
    max_value=max_rating,
    value=(min_rating, max_rating),
    step=0.1,
)


# Filter by rating for all seasons (for bar chart)
if "Rating" in df.columns:
    rating_filtered_df = df[df["Rating"].between(rating_range[0], rating_range[1], inclusive="both")]
else:
    rating_filtered_df = df.copy()

# --- Character filter: Find top 15 most frequent characters ---
import ast
from collections import Counter

# Parse Main Cast column (may be string if loaded from CSV)
def parse_cast(val):
    if isinstance(val, list):
        return val
    if pd.isna(val):
        return []
    try:
        return ast.literal_eval(val)
    except Exception:
        return []

df["Main Cast"] = df["Main Cast"].apply(parse_cast)

# Count character appearances (flatten all names)
all_characters = [actor for cast in df["Main Cast"] for actor in cast]
top_characters = [name for name, _ in Counter(all_characters).most_common(15)]


# Sidebar: Actor filter (buttons)
st.sidebar.markdown("**Filter by Actor**")
char_cols = st.sidebar.columns(3)
if "selected_character" not in st.session_state:
    st.session_state.selected_character = None
for idx, char in enumerate(top_characters):
    col = char_cols[idx % 3]
    if col.button(char, key=f"char_btn_{char}"):
        if st.session_state.selected_character == char:
            st.session_state.selected_character = None  # Toggle off
        else:
            st.session_state.selected_character = char
selected_character = st.session_state.selected_character




# Prepare bar charts (Altair)
import altair as alt


# Bar chart: Combined effect of IMDb rating and actor filter (static x axis)
all_seasons = [int(s) for s in sorted([s for s in df["Season"].unique() if s != 27])]

# Apply both filters to the full dataframe for the bar chart
bar_chart_mask = df["Rating"].between(rating_range[0], rating_range[1], inclusive="both") if "Rating" in df.columns else pd.Series([True] * len(df))
if selected_character:
    bar_chart_mask &= df["Main Cast"].apply(lambda cast: selected_character in cast)
bar_chart_filtered = df[bar_chart_mask]
bar_data = pd.DataFrame({"Season": all_seasons})
bar_data = bar_data.merge(
    bar_chart_filtered.groupby("Season").size().reset_index(name="Episodes"),
    on="Season", how="left"
).fillna({"Episodes": 0})
bar_data["Season"] = bar_data["Season"].apply(lambda x: int(x))
bar_data["Episodes"] = bar_data["Episodes"].apply(lambda x: int(x))
max_episodes = int(df.groupby("Season").size().max()) if len(df) > 0 else 1
# Set y axis to always be static and remove y axis label
bar_chart = alt.Chart(bar_data).mark_bar(size=28, cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
    x=alt.X("Season:O", title="Season", axis=alt.Axis(labelAngle=0), sort=all_seasons),
    y=alt.Y("Episodes:Q", title=None, scale=alt.Scale(domain=[0, max_episodes])),
    tooltip=["Season", "Episodes"]
).properties(
    width=420,
    height=180
).configure_axis(
    grid=False
).configure_view(
    strokeWidth=0
)



# --- Unified filtering for episode list ---
episode_mask = pd.Series([True] * len(df))
if "Rating" in df.columns:
    episode_mask &= df["Rating"].between(rating_range[0], rating_range[1], inclusive="both")
if selected_character:
    episode_mask &= df["Main Cast"].apply(lambda cast: selected_character in cast)
episode_mask &= df["Season"] == selected_season
filtered_data = df[episode_mask].copy()



# If search term is provided, filter across all episodes (not just current season)
if search_term.strip():
    # Apply all filters except season, then search across all seasons
    search_mask = pd.Series([True] * len(df))
    if "Rating" in df.columns:
        search_mask &= df["Rating"].between(rating_range[0], rating_range[1], inclusive="both")
    if selected_character:
        search_mask &= df["Main Cast"].apply(lambda cast: selected_character in cast)
    search_df = df[search_mask].copy()
    search_lower = search_term.lower()
    # Search in Title, Description, and Main Cast (actor names)
    def cast_contains_search(cast):
        return any(search_lower in str(actor).lower() for actor in cast) if isinstance(cast, list) else False
    text_mask = (
        search_df["Title"].str.lower().str.contains(search_lower, na=False) |
        search_df["Description"].str.lower().str.contains(search_lower, na=False) |
        search_df["Main Cast"].apply(cast_contains_search)
    )
    filtered_data = search_df[text_mask]
    header_text = f"Search Results for '{search_term}' ({len(filtered_data)} episodes found)"
else:
    # Build filter description for header
    filter_desc = []
    if selected_character:
        filter_desc.append(f"featuring {selected_character}")
    # Only show rating filter if not the full range
    min_rating_display = min_rating
    max_rating_display = max_rating
    if rating_range[0] > min_rating_display or rating_range[1] < max_rating_display:
        if rating_range[0] == rating_range[1]:
            filter_desc.append(f"with IMDb rating {rating_range[0]:.1f}")
        else:
            filter_desc.append(f"with IMDb rating between {rating_range[0]:.1f} and {rating_range[1]:.1f}")
    filter_str = ""
    if filter_desc:
        filter_str = " (Episodes " + " and ".join(filter_desc) + ")"
    header_text = f"Season {selected_season}{filter_str}\nEpisodes: {len(filtered_data)}"

# Show header
if '\n' in header_text:
    st.header(header_text.split('\n')[0])
    st.write(header_text.split('\n')[1])
else:
    st.header(header_text)

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
        # Show main cast under description
        cast_list = episode["Main Cast"] if isinstance(episode["Main Cast"], list) else []
        if cast_list:
            st.write(f"Main Cast: {', '.join(cast_list)}")
        else:
            st.write("Main Cast: (not available)")
        st.divider()








# Show the combined bar chart below the episode list, in a collapsible expander, with all toolbar icons hidden
with st.expander("Show effect of all filters across all seasons", expanded=False):
    st.markdown("""
        <style>
        [data-testid=\"stElementToolbar\"] {display: none !important;}
        div[role=\"figure\"] > div[tabindex=\"0\"] {display: none !important;}
        </style>
        <div style='margin-bottom:0.5rem;'></div>
    """, unsafe_allow_html=True)
    st.altair_chart(bar_chart, use_container_width=True)