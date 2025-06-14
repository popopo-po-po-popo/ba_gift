import streamlit as st
import pandas as pd
import os
import base64
from PIL import Image
import io

GIFT_IMAGE_DIR = os.path.join('images', 'gift')
CHAR_IMAGE_DIR = os.path.join('images', 'char')

@st.cache_data
def get_image_as_base64(path):
    if path is None or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

@st.cache_data
def get_char_image_as_base64(char_name):
    image_path = find_image_path(CHAR_IMAGE_DIR, char_name)
    if not image_path:
        return None
    
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGBA")
            width, height = img.size
            
            short_side = min(width, height)
            left = (width - short_side) / 2
            top = (height - short_side) / 2
            right = (width + short_side) / 2
            bottom = (height + short_side) / 2
            cropped_img = img.crop((left, top, right, bottom))
            
            buffered = io.BytesIO()
            cropped_img.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()
    except Exception:
        return None

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

def get_shared_gifts_reverse_lookup(df, selected_characters, rarity_dict):
    if df is None or df.empty or not selected_characters:
        return {}

    filtered_df = df[df['character'].isin(selected_characters)].copy()
    if filtered_df.empty:
        return {}

    idx = filtered_df.groupby(['gift'])['effect_cat'].transform(lambda x: x == x.max())
    best_use_df = filtered_df[idx].copy()

    gift_competition = best_use_df.groupby('gift')['character'].nunique()
    best_use_df['competition'] = best_use_df['gift'].map(gift_competition)

    shared_gifts_df = best_use_df[best_use_df['competition'] > 1].copy()
    
    if shared_gifts_df.empty:
        return {}

    effect_order_dict = {'中': 0, '大': 1, '特大': 2}

    shared_gifts_reverse = {}
    for gift_name in shared_gifts_df['gift'].unique():
        gift_chars_df = shared_gifts_df[shared_gifts_df['gift'] == gift_name]
        characters = sorted(gift_chars_df['character'].unique())
        
        rarity = rarity_dict.get(gift_name, 0)
        competition = gift_chars_df['competition'].iloc[0]
        effect_cat = gift_chars_df['effect_cat'].iloc[0]
        effect_order = effect_order_dict.get(str(effect_cat), 0)
        
        shared_gifts_reverse[gift_name] = {
            'characters': characters,
            'rarity': rarity,
            'competition': competition,
            'effect_order': effect_order
        }
    
    sorted_gifts = sorted(shared_gifts_reverse.items(), 
                         key=lambda x: (-x[1]['rarity'], x[1]['competition'], -x[1]['effect_order'], x[0]))
    
    return dict(sorted_gifts)

def get_generation_candidates(df, selected_characters, rarity_dict):
    if df is None or df.empty or not selected_characters:
        return []
    
    filtered_df = df[df['character'].isin(selected_characters)].copy()
    if filtered_df.empty:
        return []
    
    yellow_gifts_df = filtered_df[filtered_df['gift'].map(lambda x: rarity_dict.get(x, 0) == 0)].copy()
    if yellow_gifts_df.empty:
        return []
    
    best_effect_df = yellow_gifts_df.loc[yellow_gifts_df.groupby('gift')['effect_cat'].idxmax()].copy()
    
    max_effect = best_effect_df['effect_cat'].max()
    
    top_candidates = best_effect_df[best_effect_df['effect_cat'] == max_effect].copy()
    
    top_candidates['num_chars'] = top_candidates.groupby('gift')['character'].transform('count')
    top_candidates_sorted = top_candidates.sort_values(
        by=['num_chars', 'gift'],
        ascending=[False, True]
    )
    
    return top_candidates_sorted['gift'].unique().tolist()

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
    .reverse-lookup-item {
        display: flex;
        align-items: center;
        margin-bottom: 8px;
        min-height: 44px;
    }
    .reverse-lookup-image {
        flex: 0 0 44px;
        margin-right: 10px;
    }
    .reverse-lookup-characters {
        flex: 1;
        font-size: 14px;
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
                max_unique_width = 0
                for char in optimal_gifts_data.keys():
                    unique_gifts = optimal_gifts_data[char]['unique']
                    unique_width = len(unique_gifts) * 44
                    max_unique_width = max(max_unique_width, unique_width)
                
                char_image_container_width = 44
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

                    char_image_base64 = get_char_image_as_base64(char)
                    if char_image_base64:
                        char_html = f"<img src='data:image/png;base64,{char_image_base64}' title='{char}' style='width: 44px; height: 44px; border-radius: 50%; object-fit: cover;'>"
                    else:
                        char_html = f"<div title='{char}' style='width: 44px; height: 44px; border-radius: 50%; background-color: #e0e0e0; display: flex; align-items: center; justify-content: center; font-size: 14px; text-align: center; color: #555; line-height: 1.2; font-weight: bold;'>{char[:2]}</div>"
                    
                    full_line_html = f"""
                    <div style="display: flex; align-items: center; margin-bottom: 8px; min-height: 44px;">
                        <div style="width: {char_image_container_width}px; flex-shrink: 0; margin-right: 10px;">{char_html}</div>
                        {gifts_container}
                    </div>
                    """
                    st.markdown(full_line_html, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("#### 共通品 逆引き")
            shared_gifts_reverse = get_shared_gifts_reverse_lookup(df, selected_characters, rarity_dict)
            
            if shared_gifts_reverse:
                gifts_list = list(shared_gifts_reverse.items())
                
                left_column_items = []
                right_column_items = []

                for i in range(0, len(gifts_list), 2):
                    left_gift_name, left_gift_data = gifts_list[i]
                    left_chars_html_parts = []
                    for char in left_gift_data['characters']:
                        base64_img = get_char_image_as_base64(char)
                        if base64_img:
                            left_chars_html_parts.append(f"<img src='data:image/png;base64,{base64_img}' title='{char}' style='width: 44px; height: 44px; border-radius: 50%; object-fit: cover; margin: 2px;'>")
                        else:
                            left_chars_html_parts.append(f"<div title='{char}' style='width: 44px; height: 44px; border-radius: 50%; background-color: #e0e0e0; display: flex; align-items: center; justify-content: center; font-size: 14px; margin: 2px; font-weight: bold;'>{char[:2]}</div>")
                    left_characters_html = f"<div style='display: flex; align-items: center; flex-wrap: wrap;'>{''.join(left_chars_html_parts)}</div>"
                    
                    left_gift_image_path = find_image_path(GIFT_IMAGE_DIR, left_gift_name)
                    left_base64_image = get_image_as_base64(left_gift_image_path)
                    left_border_style = get_rarity_border_style(left_gift_name, rarity_dict)
                    if left_base64_image:
                        file_extension = os.path.splitext(left_gift_image_path)[1][1:].lower()
                        mime_type = f"image/{'jpeg' if file_extension == 'jpg' else file_extension}"
                        left_image_html = f"<img src='data:{mime_type};base64,{left_base64_image}' width='40' title='{left_gift_name}' style='border-radius: 5px; {left_border_style}'>"
                    else:
                        left_image_html = f"<div class='no-image-list-item' title='{left_gift_name}' style='{left_border_style}'></div>"
                    
                    left_item_html = f'<div style="display: flex; align-items: center; min-height: 44px; margin-bottom: 8px;">' \
                                   f'<div style="flex-shrink: 0; margin-right: 10px;">{left_image_html}</div>' \
                                   f'<div>{left_characters_html}</div>' \
                                   f'</div>'
                    left_column_items.append(left_item_html)

                    if i + 1 < len(gifts_list):
                        right_gift_name, right_gift_data = gifts_list[i + 1]
                        right_chars_html_parts = []
                        for char in right_gift_data['characters']:
                            base64_img = get_char_image_as_base64(char)
                            if base64_img:
                                right_chars_html_parts.append(f"<img src='data:image/png;base64,{base64_img}' title='{char}' style='width: 44px; height: 44px; border-radius: 50%; object-fit: cover; margin: 2px;'>")
                            else:
                                right_chars_html_parts.append(f"<div title='{char}' style='width: 44px; height: 44px; border-radius: 50%; background-color: #e0e0e0; display: flex; align-items: center; justify-content: center; font-size: 14px; margin: 2px; font-weight: bold;'>{char[:2]}</div>")
                        right_characters_html = f"<div style='display: flex; align-items: center; flex-wrap: wrap;'>{''.join(right_chars_html_parts)}</div>"

                        right_gift_image_path = find_image_path(GIFT_IMAGE_DIR, right_gift_name)
                        right_base64_image = get_image_as_base64(right_gift_image_path)
                        right_border_style = get_rarity_border_style(right_gift_name, rarity_dict)
                        if right_base64_image:
                            file_extension = os.path.splitext(right_gift_image_path)[1][1:].lower()
                            mime_type = f"image/{'jpeg' if file_extension == 'jpg' else file_extension}"
                            right_image_html = f"<img src='data:{mime_type};base64,{right_base64_image}' width='40' title='{right_gift_name}' style='border-radius: 5px; {right_border_style}'>"
                        else:
                            right_image_html = f"<div class='no-image-list-item' title='{right_gift_name}' style='{right_border_style}'></div>"
                        
                        right_item_html = f'<div style="display: flex; align-items: center; min-height: 44px; margin-bottom: 8px;">' \
                                        f'<div style="flex-shrink: 0; margin-right: 10px;">{right_image_html}</div>' \
                                        f'<div>{right_characters_html}</div>' \
                                        f'</div>'
                        right_column_items.append(right_item_html)
                    else:
                        right_column_items.append('<div style="min-height: 44px; margin-bottom: 8px;"></div>')

                left_column_full_html = "".join(left_column_items)
                right_column_full_html = "".join(right_column_items)
                
                full_reverse_html = f"""
                <div style="display: grid; grid-template-columns: max-content 1fr; align-items: start; gap: 0 20px;">
                    <div>{left_column_full_html}</div>
                    <div>{right_column_full_html}</div>
                </div>
                """
                st.markdown(full_reverse_html, unsafe_allow_html=True)
            else:
                st.write("（なし）")

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
            st.markdown("#### 選択ボックス")
            generation_candidates = get_generation_candidates(df, selected_characters, rarity_dict)
            
            if generation_candidates:
                image_html_parts = []
                for gift_name in generation_candidates:
                    gift_image_path = find_image_path(GIFT_IMAGE_DIR, gift_name)
                    base64_image = get_image_as_base64(gift_image_path)
                    border_style = get_rarity_border_style(gift_name, rarity_dict)
                    
                    if base64_image:
                        file_extension = os.path.splitext(gift_image_path)[1][1:].lower()
                        mime_type = f"image/{'jpeg' if file_extension == 'jpg' else file_extension}"
                        image_html_parts.append(f"<img src='data:{mime_type};base64,{base64_image}' width='40' title='{gift_name}' style='margin: 2px; border-radius: 5px; {border_style}'>")
                    else:
                        image_html_parts.append(f"<div class='no-image-list-item' title='{gift_name}' style='{border_style}'></div>")
                
                candidates_html = f"<div style='display: flex; flex-wrap: wrap; align-items: center;'>{''.join(image_html_parts)}</div>"
                st.markdown(candidates_html, unsafe_allow_html=True)
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