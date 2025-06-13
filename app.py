import streamlit as st
import pandas as pd
import os
import base64

GIFT_IMAGE_DIR = os.path.join('images', 'gift')

@st.cache_data
def get_image_as_base64(path):
    if path is None or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

@st.cache_data
def load_rarity_data():
    rarity_file = 'rarity.csv'
    if not os.path.exists(rarity_file):
        return {}
    
    try:
        rarity_df = pd.read_csv(rarity_file, encoding='utf-8')
        rarity_df.columns = rarity_df.columns.str.strip()
        rarity_df['giftname'] = rarity_df['giftname'].fillna('').astype(str).str.strip()
        return dict(zip(rarity_df['giftname'], rarity_df['rarity']))
    except Exception:
        st.error("ファイル読み込みエラー")
        return {}

def get_rarity_border_style(gift_name, rarity_dict):
    rarity = rarity_dict.get(gift_name, 0)
    if rarity == 1:
        return "border: 3px solid #8B5CF6; box-shadow: 0 0 6px rgba(139, 92, 246, 0.5);"
    else:
        return "border: 3px solid #F59E0B; box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);"

@st.cache_data
def load_data():
    csv_file = 'gifts.csv'
    if not os.path.exists(csv_file):
        return None, None, None

    try:
        df = pd.read_csv(csv_file, encoding='utf-8')
        df.columns = df.columns.str.strip()
        for col in ['character', 'gift', 'effect']:
            if col in df.columns:
                df[col] = df[col].fillna('').astype(str).str.strip()

        all_characters = sorted(df[df['character'] != '']['character'].unique())
        all_gifts = set(df[df['gift'] != '']['gift'].unique())

        valid_effects = ['中', '大', '特大']
        df = df[df['effect'].isin(valid_effects)].copy()

        effect_order = ['中', '大', '特大']
        df['effect_cat'] = pd.Categorical(df['effect'], categories=effect_order, ordered=True)
        
        return df, all_characters, all_gifts
    except Exception:
        st.error("ファイル読み込みエラー")
        return None, None, None

def find_best_gifts(df, selected_characters):
    if df is None or df.empty or not selected_characters:
        return pd.DataFrame()

    result_df = df[df['character'].isin(selected_characters)].copy()
    
    if not result_df.empty:
        result_df['num_chars'] = result_df.groupby('gift')['character'].transform('count')
        result_df.sort_values(
            by=['num_chars', 'effect_cat', 'gift'],
            ascending=[False, False, True],
            inplace=True
        )
    return result_df

def get_optimal_gifts_per_character(df, selected_characters, rarity_dict):
    if df is None or df.empty or not selected_characters:
        return {}

    filtered_df = df[df['character'].isin(selected_characters)].copy()
    if filtered_df.empty:
        return {char: {'unique': [], 'shared': []} for char in selected_characters}

    idx = filtered_df.groupby(['gift'])['effect_cat'].transform(lambda x: x == x.max())
    best_use_df = filtered_df[idx].copy()

    gift_competition = best_use_df.groupby('gift')['character'].nunique()
    best_use_df['competition'] = best_use_df['gift'].map(gift_competition)

    optimal_gifts = {}
    for char in selected_characters:
        char_gifts_df = best_use_df[best_use_df['character'] == char].copy()
        
        if not char_gifts_df.empty:
            char_gifts_df.loc[:, 'rarity'] = char_gifts_df['gift'].map(lambda x: rarity_dict.get(x, 0))
            
            unique_gifts_df = char_gifts_df[char_gifts_df['competition'] == 1].copy()
            shared_gifts_df = char_gifts_df[char_gifts_df['competition'] > 1].copy()
            
            unique_sorted = unique_gifts_df.sort_values(
                by=['rarity', 'effect_cat', 'gift'],
                ascending=[False, False, True]
            )
            
            shared_sorted = shared_gifts_df.sort_values(
                by=['rarity', 'competition', 'effect_cat', 'gift'],
                ascending=[False, True, False, True]
            )
            
            optimal_gifts[char] = {
                'unique': unique_sorted['gift'].tolist(),
                'shared': shared_sorted['gift'].tolist()
            }
        else:
            optimal_gifts[char] = {'unique': [], 'shared': []}
            
    return optimal_gifts

def find_image_path(dir_path, name):
    for ext in ['.png', '.jpg', '.jpeg']:
        path = os.path.join(dir_path, f"{name}{ext}")
        if os.path.exists(path):
            return path
    return None

st.set_page_config(page_title="贈り物検索", layout="wide")

st.markdown("""
    <style>
    div.stApp {
        font-size: 45%;
    }
    div[data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"] [data-testid="stContainer"] {
        box-sizing: border-box !important;
        height: auto !important; 
        padding: 15px !important;
    }
    .image-placeholder-card {
        width: 80px;
        height: 80px;
        display: flex;
        align-items: center;
        justify-content: center;
        background-color: #f0f2f6;
        border-radius: 8px;
        color: #888;
        font-size: 0.9em;
        margin: 0 auto;
    }
    .no-image-list-item {
        width: 40px;
        height: 40px;
        margin: 2px;
        background-color: #f0f2f6;
        border-radius: 5px;
        display: inline-block;
        vertical-align: middle;
    }
    .gift-card {
        display: flex;
        align-items: center;
        min-height: 80px;
        padding: 0;
    }
    .gift-image-container {
        flex: 0 0 85px;
        display: flex;
        align-items: center;
        justify-content: center;
        height: 80px;
    }
    .gift-text-container {
        flex: 1;
        padding-left: 15px;
        display: flex;
        align-items: center;
        height: 80px;
    }
    .character-list {
        line-height: 1.4;
        font-size: 13px;
        margin: 0;
    }
    </style>
    """, unsafe_allow_html=True)

df, all_characters, all_gifts = load_data()
rarity_dict = load_rarity_data()

if df is not None:
    with st.sidebar:
        selected_characters = st.multiselect('キャラクターを選択:', options=all_characters, placeholder="キャラクター名を入力...")
        search_button = st.button('検索', type="primary", use_container_width=True)

    if search_button:
        if not selected_characters:
            st.warning('キャラクター未選択')
        else:
            result_df = find_best_gifts(df, selected_characters)
            optimal_gifts_data = get_optimal_gifts_per_character(df, selected_characters, rarity_dict)

            st.markdown("#### 贈り方")
            if optimal_gifts_data:
                max_char_length = 0
                max_unique_width = 0
                
                for char in optimal_gifts_data.keys():
                    char_length = sum(2 if ord(c) > 127 else 1 for c in char)
                    max_char_length = max(max_char_length, char_length)
                    
                    unique_gifts = optimal_gifts_data[char]['unique']
                    unique_width = len(unique_gifts) * 44
                    max_unique_width = max(max_unique_width, unique_width)
                
                char_name_width = max(max_char_length * 9 + 20, 80)
                unique_section_width = max(max_unique_width, 0)
                
                for char, gifts_data in optimal_gifts_data.items():
                    unique_gifts = gifts_data['unique']
                    shared_gifts = gifts_data['shared']
                    
                    unique_html_parts = []
                    if unique_gifts:
                        for gift_name in unique_gifts:
                            gift_image_path = find_image_path(GIFT_IMAGE_DIR, gift_name)
                            base64_image = get_image_as_base64(gift_image_path)
                            border_style = get_rarity_border_style(gift_name, rarity_dict)
                            
                            if base64_image:
                                file_extension = os.path.splitext(gift_image_path)[1][1:].lower()
                                mime_type = f"image/{'jpeg' if file_extension == 'jpg' else file_extension}"
                                unique_html_parts.append(f"<img src='data:{mime_type};base64,{base64_image}' width='40' title='{gift_name}' style='margin: 2px; border-radius: 5px; vertical-align: middle; {border_style}'>")
                            else:
                                unique_html_parts.append(f"<div class='no-image-list-item' title='{gift_name}' style='{border_style}'></div>")
                    
                    shared_html_parts = []
                    if shared_gifts:
                        for gift_name in shared_gifts:
                            gift_image_path = find_image_path(GIFT_IMAGE_DIR, gift_name)
                            base64_image = get_image_as_base64(gift_image_path)
                            border_style = get_rarity_border_style(gift_name, rarity_dict)
                            
                            if base64_image:
                                file_extension = os.path.splitext(gift_image_path)[1][1:].lower()
                                mime_type = f"image/{'jpeg' if file_extension == 'jpg' else file_extension}"
                                shared_html_parts.append(f"<img src='data:{mime_type};base64,{base64_image}' width='40' title='{gift_name}' style='margin: 2px; border-radius: 5px; vertical-align: middle; {border_style}'>")
                            else:
                                shared_html_parts.append(f"<div class='no-image-list-item' title='{gift_name}' style='{border_style}'></div>")
                    
                    unique_container_html = f"<div style='width: {unique_section_width}px; display: flex; flex-wrap: wrap; align-items: center;'>{''.join(unique_html_parts)}</div>"
                    shared_container_html = f"<div style='display: flex; flex-wrap: wrap; align-items: center;'>{''.join(shared_html_parts)}</div>" if shared_html_parts else ""
                    
                    separator = "<div style='width: 15px;'></div>" if unique_section_width > 0 and shared_container_html else ""
                    gifts_container = f"<div style='flex-grow: 1; display: flex; align-items: center;'>{unique_container_html}{separator}{shared_container_html}</div>"

                    full_line_html = f"""
                    <div style="display: flex; align-items: center; margin-bottom: 8px; min-height: 44px;">
                        <div style="width: {char_name_width}px; font-weight: bold; flex-shrink: 0; margin-right: 10px; font-size: 14px;">{char}</div>
                        {gifts_container}
                    </div>
                    """
                    st.markdown(full_line_html, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("#### テイラー")
            favorite_gifts = set(result_df['gift'].unique())
            useless_gifts = list(all_gifts - favorite_gifts)
            
            rare_useless_gifts = [gift for gift in useless_gifts if rarity_dict.get(gift, 0) == 1]
            common_useless_gifts = [gift for gift in useless_gifts if rarity_dict.get(gift, 0) != 1]
            
            common_useless_gifts_with_rarity = [(gift, rarity_dict.get(gift, 0)) for gift in common_useless_gifts]
            common_useless_gifts_sorted = sorted(common_useless_gifts_with_rarity, key=lambda x: (-x[1], x[0]))
            common_useless_gifts = [gift for gift, _ in common_useless_gifts_sorted]
            
            if common_useless_gifts:
                image_html_parts = []
                for gift_name in common_useless_gifts:
                    gift_image_path = find_image_path(GIFT_IMAGE_DIR, gift_name)
                    base64_image = get_image_as_base64(gift_image_path)
                    border_style = get_rarity_border_style(gift_name, rarity_dict)
                    
                    if base64_image:
                        file_extension = os.path.splitext(gift_image_path)[1][1:].lower()
                        mime_type = f"image/{'jpeg' if file_extension == 'jpg' else file_extension}"
                        image_html_parts.append(f"<img src='data:{mime_type};base64,{base64_image}' width='40' title='{gift_name}' style='margin: 2px; border-radius: 5px; {border_style}'>")
                    else:
                        image_html_parts.append(f"<div class='no-image-list-item' title='{gift_name}' style='{border_style}'></div>")
                
                useless_gifts_html = f"<div style='display: flex; flex-wrap: wrap; align-items: center;'>{''.join(image_html_parts)}</div>"
                st.markdown(useless_gifts_html, unsafe_allow_html=True)
            else:
                st.write("（なし）")

            st.markdown("---")
            st.markdown("#### うんち")
            if rare_useless_gifts:
                rare_useless_gifts_sorted = sorted(rare_useless_gifts)
                image_html_parts = []
                for gift_name in rare_useless_gifts_sorted:
                    gift_image_path = find_image_path(GIFT_IMAGE_DIR, gift_name)
                    base64_image = get_image_as_base64(gift_image_path)
                    border_style = get_rarity_border_style(gift_name, rarity_dict)
                    
                    if base64_image:
                        file_extension = os.path.splitext(gift_image_path)[1][1:].lower()
                        mime_type = f"image/{'jpeg' if file_extension == 'jpg' else file_extension}"
                        image_html_parts.append(f"<img src='data:{mime_type};base64,{base64_image}' width='40' title='{gift_name}' style='margin: 2px; border-radius: 5px; {border_style}'>")
                    else:
                        image_html_parts.append(f"<div class='no-image-list-item' title='{gift_name}' style='{border_style}'></div>")
                
                rare_useless_gifts_html = f"<div style='display: flex; flex-wrap: wrap; align-items: center;'>{''.join(image_html_parts)}</div>"
                st.markdown(rare_useless_gifts_html, unsafe_allow_html=True)
            else:
                st.write("（なし）")
else:
    st.error("データファイルが見つかりません")