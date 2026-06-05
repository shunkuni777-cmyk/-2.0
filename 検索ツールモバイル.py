import os
import requests
import pandas as pd
import streamlit as st
from io import BytesIO
# 一番最初に100%確実に動いた、大元の部品だけを使います
from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth

# -------------------------------------------------------------
# ★★★【設定】ここに情報を貼り付けてください ★★★
BOX_CLIENT_ID = "qyolw1hpmuzh8reuoatj5a7lu9b2el1d"
BOX_CLIENT_SECRET = "dINvj7FIEdo7uaDsfJMf8xA6wB5BxpNH"
BOX_DEVELOPER_TOKEN = "iOdOXxtbunzhXOxsUzRz0MN3xBnwemJv"

BOX_FILE_ID = "2263601536663"

# 👇 【これが足りていませんでした！】ここに写真フォルダのIDを入れてください
BOX_FOLDER_ID = "387052239832"
# -------------------------------------------------------------
# --- 【超重要】1時間ごとに裏側でトークンを自動更新する関数 ---
def get_valid_token():
    # Streamlitのメモリ機能を使って、最新の有効なトークンを記憶しておく
    if "current_token" not in st.session_state:
        st.session_state.current_token = BOX_DEVELOPER_TOKEN.strip()
    
    # 記憶しているトークンが使えるかBoxに一度確認してみる
    test_url = f"https://api.box.com/2.0/files/{BOX_FILE_ID}"
    headers = {"Authorization": f"Bearer {st.session_state.current_token}"}
    res = requests.get(test_url, headers=headers)
    
    # もし401（期限切れ）だったら、裏側でクライアントIDを使って自動で新しいトークンを再取得する
    if res.status_code == 401:
        token_url = "https://api.box.com/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": BOX_CLIENT_ID.strip(),
            "client_secret": BOX_CLIENT_SECRET.strip(),
            "box_subject_type": "enterprise",
            "box_subject_id": BOX_CLIENT_ID.strip() # 個人アカウント用
        }
        token_res = requests.post(token_url, data=data)
        if token_res.status_code == 200:
            st.session_state.current_token = token_res.json().get("access_token")
            
    return st.session_state.current_token

# --- 1. Boxから安全にファイルを読み込む処理 ---
@st.cache_data(ttl=600)
def load_data_from_box_secure():
    try:
        # 自動で更新された「今使える有効なトークン」を取得
        valid_token = get_valid_token()
        
        # 一番最初に成功した、絶対にエラーが出ないプレーンな認証
        auth = BoxDeveloperTokenAuth(token=valid_token)
        client = BoxClient(auth=auth)
        
        # ファイルのダウンロード
        download_stream = client.downloads.download_file(file_id=BOX_FILE_ID)
        file_content = b"".join(download_stream)
        
        df = pd.read_excel(BytesIO(file_content))
        df = df.fillna("")
        for col in df.columns:
            df[col] = df[col].astype(str).map(lambda x: "".join(x.splitlines()))
        return df
            
    except Exception as e:
        st.error(f"Box連携でエラーが発生しました: {e}")
        return None

df = load_data_from_box_secure()

if df is None or df.empty:
    st.stop()

all_columns = list(df.columns)
display_columns = [col for col in all_columns if col != "写真"]

# --- 2. GUI（画面）の構築 ---
st.title("📷 社内機材 検索ツール (Box連携版)")

# 検索キーワード入力
keyword = st.text_input("検索キーワードを入力してください:", value="", key="search_key").strip()

if keyword:
    # 検索ロジック
    cond_name = df['機材名'].str.contains(keyword, case=False, na=False) if '機材名' in df.columns else False
    cond_maker = df['メーカー'].str.contains(keyword, case=False, na=False) if 'メーカー' in df.columns else False
    cond_model = df['型番'].str.contains(keyword, case=False, na=False) if '型番' in df.columns else False
    loc_col = '保管場所' if '保管場所' in df.columns else ('場所' if '場所' in df.columns else '')
    cond_loc = df[loc_col].str.contains(keyword, case=False, na=False) if loc_col else False
    
    result = df[cond_name | cond_maker | cond_model | cond_loc]

    if result.empty:
        st.warning("該当する機材は見つかりませんでした。")
    else:
        st.success(f"{len(result)} 件の機材が見つかりました。")

        for idx, row in result.iterrows():
            title = f"{row.get('機材名', '不明')}  ({row.get('型番', '-')})"
            
            with st.expander(title):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    for col_name in display_columns:
                        st.markdown(f"**【{col_name}】**: {row[col_name]}")
                
                with col2:
                    # --- Googleドライブからの写真表示処理 ---
                    image_urls_str = row.get("写真", "")
                    
                    if image_urls_str.strip():
                        image_urls = [url.strip() for url in image_urls_str.split(",") if url.strip()]
                        
                        for img_url in image_urls:
                            # 💡 Googleドライブの共有リンク（/file/d/xxxx/view）を、画像データ直接のURLに自動変換する
                            if "drive.google.com" in img_url:
                                if "/file/d/" in img_url:
                                    file_id = img_url.split("/file/d/")[1].split("/")[0]
                                    img_url = f"https://drive.google.com/uc?export=view&id={file_id}"
                            
                            # 📸 画面の中に直接画像を表示します
                            st.image(
                                img_url,
                                caption=f"{row.get('機材名', '機材')} の写真",
                                use_container_width=True
                            )
                    else:
                        st.caption("(写真未登録)")
else:
    st.info("キーワードを入力すると、ここに検索結果が表示されます。")
