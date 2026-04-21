import streamlit as st

# Secrets画面で password = "あきた" と設定している前提
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    # 画面中央にパスワード入力だけを表示
    pwd = st.text_input("パスワードを入力してください", type="password")
    if pwd == st.secrets["password"]:
        st.session_state.authenticated = True
        st.rerun()
    elif pwd != "":
        st.error("パスワードが違います")
    st.stop() # 正解するまでこれ以降のコードを実行しない

import pandas as pd
from datetime import datetime
import time
import matplotlib.pyplot as plt
import numpy as np
import math
import os

# --- 0. マスターデータ読み込み関数 (シート構造保持版) ---
@st.cache_data
def load_master_data_optimized(file_path):
    master_dict = {}  # { シート名: { 製品名: inch } }
    master_len = {}   # { 製品名: 長さ }
    
    if not os.path.exists(file_path):
        return {}, {}

    try:
        with pd.ExcelFile(file_path) as xls:
            sheets = [s for s in xls.sheet_names if s != "元シート"]
            for sheet in sheets:
                df = pd.read_excel(xls, sheet_name=sheet)
                if '製品名' not in df.columns: continue

                sheet_devices = {}
                for _, row in df.iterrows():
                    name = str(row['製品名'])
                    if name == 'nan' or name == '-': continue
                    
                    # --- 【修正】B(inch), C(mm), D(Fr)のどこからでも数値を拾うロジック ---
                    calc_inch = 0.0
                    if pd.notna(row.get('inch')):
                        calc_inch = float(row['inch'])
                    elif pd.notna(row.get('mm')):
                        calc_inch = float(row['mm']) / 25.4
                    elif pd.notna(row.get('Fr')):
                        calc_inch = float(row['Fr']) / 3 / 25.4
                    
                    # 親デバイス（内径）の場合の処理も統合
                    if "親" in str(row.get('種別', '')) and pd.notna(row.get('内径')):
                        calc_inch = float(row['内径'])

                    sheet_devices[name] = calc_inch
                    
                    try:
                        master_len[name] = float(row.get('長さ', 0))
                    except:
                        master_len[name] = 0.0
                
                master_dict[sheet] = sheet_devices
        return master_dict, master_len
    except Exception as e:
        st.error(f"Excel解析エラー: {e}")
        return {}, {}

# --- 1. アプリ起動時のデータ読み込み実行 ---
MASTER_FILE = "master_data.xlsx"  # ファイル名を統一
data, length = load_master_data_optimized(MASTER_FILE)

# session_stateに保存
st.session_state.MASTER_DATA = data
st.session_state.MASTER_LEN = length

# --- 2. ページ設定 ---
st.set_page_config(page_title="PCI Support System", layout="wide")
# --- 0. デバイスマスターデータ ---
if "MASTER_DATA" not in st.session_state:
    st.session_state.MASTER_DATA = {
        "GC": {"6Fr Heartrail": 0.070, "6Fr Hyperion": 0.071, "7Fr Heartrail": 0.080},
        "Wire": {"Sion Blue": 0.014, "Sion": 0.014, "Gladius": 0.014},
        "IVUS_OCT": {"OptiCross": 0.032, "AltaView": 0.030, "Makoto": 0.035},
        "Balloon": {"Sapphire Neo2": 0.026, "Euphora": 0.028, "NC Euphora": 0.030},
        "Stent": {"Onyx": 0.034, "Orsiro": 0.032, "Ultimaster": 0.033},
        "MicroCatheter": {"Finecross": 0.026, "Caravel": 0.025, "Corsair": 0.029}
    }

# --- 1. 状態保持 (session_state) ---
if 'pci_logs' not in st.session_state: st.session_state.pci_logs = []
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'elapsed_at_stop' not in st.session_state: st.session_state.elapsed_at_stop = 0
if 'timer_running' not in st.session_state: st.session_state.timer_running = False

# --- 2. サイドバー・ランチャー ---
st.sidebar.title("🚀 カテ室ランチャー")
# 【追加】一括リセットボタン：これを押さない限りチェックは維持されます
if st.sidebar.button("🧹 チェックと入力をリセット"):
    for key in list(st.session_state.keys()):
        if "_v30" in key: del st.session_state[key]
    st.rerun()
# サイドバーのページ切り替え（既存のコードに合わせて項目を追加）
page = st.sidebar.radio("メニューを選択", ["1. 👤患者基本情報", "2. 📏使用デバイス、干渉計算", "3. 📝治療記録ログ", "📖 資料","🔍 Tips検索"])

# --- 3. 各ページの実装 ---
if page == "1. 👤患者基本情報":
    st.header("👤 患者基本情報")

    # --- 1. セッション状態の初期化 (一括管理) ---
    # 入力項目が増えてもここに追加すれば保持されます
    defaults = {
        "p_id": "", "p_date": datetime.now().date(), "p_height": 165.0, "p_weight": 60.0,
        "p_cr": 0.0, "p_hb": 0.0, "t_onset": None, "t_door": None, "t_in": None, 
        "t_rep": None, "t_out": None, "f_min": 0.0, "f_mgy": 0.0, "f_gy": 0.0,
        "l_min": 0.0, "l_mgy": 0.0, "l_gy": 0.0, "dapt": [], "lipid": [], "remarks": ""
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # --- 2. 基本情報入力エリア ---
    with st.container(border=True):
        r1_c1, r1_c2, r1_c3, r1_c4, r1_c5 = st.columns([1.5, 1.5, 1, 1, 1])
        st.session_state.p_id = r1_c1.text_input("患者ID", value=st.session_state.p_id)
        st.session_state.p_date = r1_c2.date_input("施行日", value=st.session_state.p_date)
        st.session_state.p_height = r1_c3.number_input("身長 (cm)", value=st.session_state.p_height, step=0.1)
        st.session_state.p_weight = r1_c4.number_input("体重 (kg)", value=st.session_state.p_weight, step=0.1)
        
        # BSA自動計算
        bsa = 0.007184 * (st.session_state.p_height**0.725) * (st.session_state.p_weight**0.425)
        r1_c5.metric("BSA (m²)", f"{bsa:.2f}")

        r2_c1, r2_c2 = st.columns([1, 1])
        st.session_state.p_cr = r2_c1.number_input("Cr (mg/dL)", value=st.session_state.p_cr, format="%.2f")
        st.session_state.p_hb = r2_c2.number_input("Hb (g/dL)", value=st.session_state.p_hb, format="%.1f")

        st.divider()

        # --- 3. タイムコース管理 ---
        st.write("**【タイムコース管理】**")
        t_cols = st.columns(5)
        st.session_state.t_onset = t_cols[0].time_input("発症時間", value=st.session_state.t_onset)
        st.session_state.t_door = t_cols[1].time_input("到着時間", value=st.session_state.t_door)
        st.session_state.t_in = t_cols[2].time_input("入室時間", value=st.session_state.t_in)
        st.session_state.t_rep = t_cols[3].time_input("再灌流時間", value=st.session_state.t_rep)
        st.session_state.t_out = t_cols[4].time_input("退室時間", value=st.session_state.t_out)

        def calc_min(s, e):
            if s and e:
                return int((datetime.combine(datetime.today(), e) - datetime.combine(datetime.today(), s)).total_seconds() / 60)
            return None

        m_cols = st.columns(3)
        m_cols[0].metric("Onset to Rep", f"{calc_min(st.session_state.t_onset, st.session_state.t_rep) or '--'} min")
        m_cols[1].metric("D2B (Door to Rep)", f"{calc_min(st.session_state.t_door, st.session_state.t_rep) or '--'} min")
        m_cols[2].metric("Room to Out", f"{calc_min(st.session_state.t_in, st.session_state.t_out) or '--'} min")

        st.divider()

        # --- 4. 放射線情報 ---
        st.write("**【放射線情報】**")
        f_cols = st.columns(3)
        st.session_state.f_min = f_cols[0].number_input("透視時間 F (min)", value=st.session_state.f_min, step=0.1)
        st.session_state.f_mgy = f_cols[1].number_input("透視量 F (mGy/cm²)", value=st.session_state.f_mgy, step=1.0)
        st.session_state.f_gy = f_cols[2].number_input("透視量 F (Gy)", value=st.session_state.f_gy, step=0.01)
        
        l_cols = st.columns(3)
        st.session_state.l_min = l_cols[0].number_input("透視時間 L (min)", value=st.session_state.l_min, step=0.1)
        st.session_state.l_mgy = l_cols[1].number_input("透視量 L (mGy/cm²)", value=st.session_state.l_mgy, step=1.0)
        st.session_state.l_gy = l_cols[2].number_input("透視量 L (Gy)", value=st.session_state.l_gy, step=0.01)

        st.divider()

        # --- 5. 薬物・備考 ---
        med_c1, med_c2 = st.columns(2)
        st.session_state.dapt = med_c1.multiselect("DAPT選択", ["バイアスピリン", "プラビックス", "エフィエント", "ブリリンタ"], default=st.session_state.dapt)
        st.session_state.lipid = med_c2.multiselect("脂質低下薬選択", ["リピトール", "クレストール", "リバロ", "ローゼット"], default=st.session_state.lipid)
        st.session_state.remarks = st.text_input("その他備考", value=st.session_state.remarks)

st.sidebar.divider()
st.sidebar.header("⏱️ 手技タイマー")
t_col1, t_col2, t_col3 = st.sidebar.columns(3)
if t_col1.button("Start"):
    if not st.session_state.timer_running:
        st.session_state.start_time = time.time() - st.session_state.elapsed_at_stop
        st.session_state.timer_running = True
if t_col2.button("Stop"):
    if st.session_state.timer_running:
        st.session_state.elapsed_at_stop = time.time() - st.session_state.start_time
        st.session_state.timer_running = False
if t_col3.button("Reset"):
    st.session_state.start_time, st.session_state.elapsed_at_stop, st.session_state.timer_running = None, 0, False
    st.rerun()

# --- サイドバー：手技タイマー（修正版） ---
timer_display = st.sidebar.empty()

if st.session_state.timer_running:
    current_elapsed = time.time() - st.session_state.start_time
    mins, secs = divmod(int(current_elapsed), 60)
    timer_display.metric("経過時間", f"{mins:02d}:{secs:02d}")
    # アプリ全体を rerun せず、微小な待機を入れて自動更新のトリガーにする
    time.sleep(0.1)
    st.rerun() # ← これが原因ですが、次の「修正2」とセットで解決します
else:
    mins, secs = divmod(int(st.session_state.elapsed_at_stop), 60)
    timer_display.metric("経過時間 (停止)", f"{mins:02d}:{secs:02d}")


# --- サイドバー：レポート作成セクション ---
st.sidebar.divider()
st.sidebar.subheader("📄 レポート出力")

if st.sidebar.button("📋 カテレポート (PDF) を作成"):
    try:
        from fpdf import FPDF
        import base64
        import unicodedata

        # --- 【修正】全角を半角に直し、非ASCII文字を除去する安全装置 ---
        def safe_txt(s):
            if s is None or s == "": return "-"
    # 全角数字などを正規化するだけで、日本語（漢字）はそのまま残す
            import unicodedata
            return unicodedata.normalize('NFKC', str(s))

        # 1. PDFクラスの定義
        class PDF(FPDF):
            def header(self):
                self.set_font('Helvetica', 'B', 16)
                self.cell(0, 10, 'PCI PROCEDURE REPORT', 0, 1, 'C')
                self.ln(5)

# --- 2. PDFの初期化 ---
        pdf = PDF()
        f_n = "Courier" # デフォルト（失敗時の保険）
        
        try:
            # プロジェクトフォルダに置いた msgothic.ttc を読み込む
            # ※ fpdf2 を使用している場合、uni=True は不要です
            pdf.add_font("JP", "", "msgothic.ttc")
            f_n = "JP"
        except Exception as e:
            st.sidebar.warning(f"⚠️ 日本語フォント読み込み失敗: {e}")
            f_n = "Courier"

        pdf.add_page()
        
# --- 1. Patient Information (患者基本情報) ---
        # 'B'（太字）を削除し、サイズ指定のみにします
        pdf.set_font(f_n, size=12) 
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(0, 10, '[ 1. PATIENT INFORMATION ]', 0, 1, 'L', 1)
        
        pdf.set_font(f_n, size=10)
        pdf.cell(0, 7, f"Patient ID: {safe_txt(st.session_state.get('p_id'))}", 0, 1)
        pdf.cell(0, 7, f"Date: {safe_txt(st.session_state.get('p_date'))}", 0, 1)
        pdf.cell(0, 7, f"Height/Weight: {safe_txt(st.session_state.get('p_height'))}cm / {safe_txt(st.session_state.get('p_weight'))}kg", 0, 1)
        pdf.cell(0, 7, f"Cr: {safe_txt(st.session_state.get('p_cr'))} mg/dL / Hb: {safe_txt(st.session_state.get('p_hb'))} g/dL", 0, 1)
        pdf.ln(3)

        # --- 2. Time Course (タイムコース管理) ---
        pdf.set_font(f_n, size=12)
        pdf.cell(0, 10, '[ 2. TIME COURSE ]', 0, 1, 'L', 1)
        pdf.set_font(f_n, size=10)
        pdf.cell(0, 7, f"Onset: {safe_txt(st.session_state.get('t_onset'))}", 0, 1)
        pdf.cell(0, 7, f"Door : {safe_txt(st.session_state.get('t_door'))}", 0, 1)
        pdf.cell(0, 7, f"In   : {safe_txt(st.session_state.get('t_in'))}", 0, 1)
        pdf.cell(0, 7, f"Rep  : {safe_txt(st.session_state.get('t_rep'))}", 0, 1)
        pdf.cell(0, 7, f"Out  : {safe_txt(st.session_state.get('t_out'))}", 0, 1)
        pdf.ln(3)

        # --- 3. Radiation Info (放射線情報) ---
        pdf.set_font(f_n, size=12)
        pdf.cell(0, 10, '[ 3. RADIATION INFO ]', 0, 1, 'L', 1)
        pdf.set_font(f_n, size=10)
        pdf.cell(0, 7, f"Fluoroscopy F: {safe_txt(st.session_state.get('f_min'))} min / {safe_txt(st.session_state.get('f_gy'))} Gy", 0, 1)
        pdf.cell(0, 7, f"Fluoroscopy L: {safe_txt(st.session_state.get('l_min'))} min / {safe_txt(st.session_state.get('l_gy'))} Gy", 0, 1)
        pdf.ln(3)

        # --- 4. Used Devices (使用デバイス一覧) ---
        pdf.set_font(f_n, size=12)
        pdf.cell(0, 10, '[ 4. USED DEVICES ]', 0, 1, 'L', 1)
        pdf.set_font(f_n, size=10)

        for i in range(1, 5):
            gc_name = st.session_state.get(f"v31_hold_gc_s_{i}", "なし")
            if gc_name != "なし":
                pdf.cell(0, 6, f"GC {i}: {safe_txt(gc_name)}", 0, 1)
        
        for j in range(1, 5):
            gw_name = st.session_state.get(f"v31_hold_w_s_{j}", "なし")
            if gw_name != "なし":
                pdf.cell(0, 6, f"GW {j}: {safe_txt(gw_name)}", 0, 1)

        for k in range(1, 11):
            dev_type = st.session_state.get(f"v31_hold_t_{k}", "なし")
            dev_name = st.session_state.get(f"v31_hold_n_{k}", "なし")
            if dev_name != "なし":
                d_dia = st.session_state.get(f"d_dia_v31_{k}", "")
                d_len = st.session_state.get(f"d_len_v31_{k}", "")
                size_str = f" ({d_dia}x{d_len}mm)" if d_dia and d_len else ""
                pdf.cell(0, 6, f"Dev {k}: [{safe_txt(dev_type)}] {safe_txt(dev_name)}{safe_txt(size_str)}", 0, 1)
        pdf.ln(3)

        # --- 5. Dilatation Log (拡張履歴) ---
        pdf.set_font(f_n, size=12)
        pdf.cell(0, 10, '[ 5. DILATATION LOG ]', 0, 1, 'L', 1)
        
        report_active_keys = [
            k for k in range(1, 11) 
            if st.session_state.get(f"v31_hold_n_{k}", "なし") != "なし" and 
            st.session_state.get(f"v31_hold_t_{k}") in ["バルーン", "ステント"]
        ]

        for k in report_active_keys:
            d_id = f"d_{k}"
            base_name = st.session_state.get(f"v31_hold_n_{k}", "Unknown")
            d_dia = st.session_state.get(f"d_dia_v31_{k}", "")
            d_len = st.session_state.get(f"d_len_v31_{k}", "")
            
            rows_content = []
            num_rows = st.session_state.get('log_row_counts_final', {}).get(d_id, 0)
            for i in range(num_rows):
                vt = safe_txt(st.session_state.get('log_permanent_storage', {}).get(f"LOG_FINAL_T_{d_id}_{i}", ""))
                vp = safe_txt(st.session_state.get('log_permanent_storage', {}).get(f"LOG_FINAL_P_{d_id}_{i}", ""))
                vs = safe_txt(st.session_state.get('log_permanent_storage', {}).get(f"LOG_FINAL_S_{d_id}_{i}", ""))
                if vt != "-" or vp != "-" or vs != "-":
                    rows_content.append(f"  #{i+1}: Target[{vt}] {vp}atm / {vs}sec")

            if rows_content:
                pdf.set_font(f_n, size=10) # 'B'を削除
                size_info = f" ({d_dia}x{d_len}mm)" if d_dia and d_len else ""
                pdf.cell(0, 7, f"Device: {safe_txt(base_name)}{safe_txt(size_info)}", 0, 1)
                pdf.set_font(f_n, size=9)
                for line in rows_content:
                    pdf.cell(0, 6, line, 0, 1)
                pdf.ln(2)

        pdf.ln(5)
        
# 3. PDFバイナリの生成（この「if」の中で完結させる）
        raw_output = pdf.output()
        pdf_output = bytes(raw_output) if isinstance(raw_output, (bytearray, str)) else raw_output

        # ダウンロードボタンの表示
        st.sidebar.download_button(
            label="📥 PDFをダウンロード",
            data=pdf_output,
            file_name=f"PCI_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )

        # 4. 【重要】メインエリアへの日本語プレビュー表示
        # ボタンを押した直後にだけ実行されるよう、このif文の中に書きます
        st.divider()
        with st.expander("📄 レポートプレビュー（日本語表示）", expanded=True):
            st.subheader("📋 患者基本情報")
            st.write(f"**患者ID:** {st.session_state.get('p_id', '-')}")
            st.write(f"**実施日:** {st.session_state.get('p_date', '-')}")
            
            st.subheader("📏 拡張履歴 (Dilatation Log)")
            storage = st.session_state.get('log_permanent_storage', {})
            # バルーン・ステントのみ抽出
            active_keys = [k for k in range(1, 11) if st.session_state.get(f"v31_hold_on_{k}") and st.session_state.get(f"v31_hold_t_{k}") in ["バルーン", "ステント"]]
            
            for k in active_keys:
                dev_name = st.session_state.get(f"v31_hold_n_{k}", "Unknown")
                st.markdown(f"**📦 {dev_name}**")
                
                rows = []
                d_id = f"d_{k}"
                for i in range(st.session_state.get('log_row_counts_final', {}).get(d_id, 1)):
                    vt = storage.get(f"LOG_FINAL_T_{d_id}_{i}", "")
                    vp = storage.get(f"LOG_FINAL_P_{d_id}_{i}", "")
                    vs = storage.get(f"LOG_FINAL_S_{d_id}_{i}", "")
                    if vt or vp or vs:
                        rows.append({"回数": i+1, "対象病変": vt, "気圧": vp, "秒数": vs})
                if rows: st.table(rows)
                else: st.caption("ログなし")

        st.sidebar.success("レポートを生成しました。")

    except Exception as e:
        st.sidebar.error(f"作成エラー: {str(e)}")

# --- 共通関数 ---
def convert_units(inch_val):
    if not inch_val: return "-"
    mm = inch_val * 25.4
    return f"{inch_val:.3f}\" / {mm:.2f}mm / {mm*3:.1f}Fr"

def get_pmda_url():
    # 検索トップページへの固定リンク
    return "https://www.pmda.go.jp/PmdaSearch/kikiSearch/"

# --- 3. 各ページの実装 ---
if page == "1. 患者基本情報":
    st.header("👤 患者基本情報")
    with st.container(border=True):
        r1_c1, r1_c2, r1_c3, r1_c4, r1_c5 = st.columns([1.5, 1.5, 1, 1, 1])
        p_id = r1_c1.text_input("患者ID")
        p_date = r1_c2.date_input("施行日", datetime.now())
        height = r1_c3.number_input("身長 (cm)", value=165.0)
        weight = r1_c4.number_input("体重 (kg)", value=60.0)
        bsa = 0.007184 * (height**0.725) * (weight**0.425)
        r1_c5.metric("BSA (m²)", f"{bsa:.2f}")

        r2_c1, r2_c2 = st.columns([1, 1])
        cr = r2_c1.number_input("Cr (mg/dL)", format="%.2f")
        hb = r2_c2.number_input("Hb (g/dL)", format="%.1f")

        st.divider()
        st.write("**【タイムコース管理】**")
        t_cols = st.columns(5)
        t_onset = t_cols[0].time_input("発症時間", value=None)
        t_door = t_cols[1].time_input("到着時間", value=None)
        t_in = t_cols[2].time_input("入室時間", value=None)
        t_rep = t_cols[3].time_input("再灌流時間", value=None)
        t_out = t_cols[4].time_input("退室時間", value=None)

        def calc_min(s, e):
            if s and e:
                return int((datetime.combine(datetime.today(), e) - datetime.combine(datetime.today(), s)).total_seconds() / 60)
            return None

        m_cols = st.columns(3)
        m_cols[0].metric("Onset to Rep", f"{calc_min(t_onset, t_rep) or '--'} min")
        m_cols[1].metric("D2B (Door to Rep)", f"{calc_min(t_door, t_rep) or '--'} min")
        m_cols[2].metric("Room to Out", f"{calc_min(t_in, t_out) or '--'} min")

        st.divider()
        st.write("**【放射線情報】**")
        f_cols = st.columns(3)
        f_cols[0].number_input("透視時間 F (min)", step=0.1)
        f_cols[1].number_input("透視量 F (mGy/cm²)", step=1)
        f_cols[2].number_input("透視量 F (Gy)", step=0.01)
        l_cols = st.columns(3)
        l_cols[0].number_input("透視時間 L (min)", step=0.1)
        l_cols[1].number_input("透視量 L (mGy/cm²)", step=1)
        l_cols[2].number_input("透視量 L (Gy)", step=0.01)

        st.divider()
        med_c1, med_c2 = st.columns(2)
        selected_dapt = med_c1.multiselect("DAPT選択", ["バイアスピリン", "プラビックス", "エフィエント", "ブリリンタ"])
        selected_lipid = med_c2.multiselect("脂質低下薬選択", ["リピトール", "クレストール", "リバロ", "ローゼット"])
        st.text_input("その他備考")


elif page == "2. 📏使用デバイス、干渉計算":
    st.header("🛠️ デバイス干渉・コンパチ計算機")

    # --- 消失対策：セッション状態をウィジェットに強制適用するための関数 ---
    def sync_state(key, default_val):
        if key not in st.session_state:
            st.session_state[key] = default_val
        return st.session_state[key]

    active_devices = []
    active_gc_in = 0

# ① ガイドカテーテル (GC)
    with st.expander("① ガイドカテーテル (GC) - 最大4つ", expanded=True):
        # 【改良】「ガイディング」または「ガイド」という文字を含むシートを自動検索
        gc_sheet_name = next((s for s in st.session_state.MASTER_DATA.keys() 
                             if "ガイディング" in s or "ガイド" in s or "GC" in s), None)
        
        # 該当するシートがあればその製品リストを、なければ空リストを取得
        if gc_sheet_name:
            gc_opts = ["なし"] + list(st.session_state.MASTER_DATA[gc_sheet_name].keys())
        else:
            gc_opts = ["なし"]
            st.warning("⚠️ Excelに「ガイディングカテーテル」または「ガイドカテーテル」という名前のシートが見つかりません。")

        for i in range(1, 5):
            c1, c2, c3 = st.columns([1, 3, 5])
            
            # --- キー設定と復元ロジック (既存のまま) ---
            on_k = f"gc_on_v31_{i}"
            sel_k = f"gc_s_v31_{i}"
            hold_on_k = f"v31_hold_gc_on_{i}"
            hold_sel_k = f"v31_hold_gc_s_{i}"

            if hold_on_k in st.session_state and on_k not in st.session_state:
                st.session_state[on_k] = st.session_state[hold_on_k]
            if hold_sel_k in st.session_state and sel_k not in st.session_state:
                st.session_state[sel_k] = st.session_state[hold_sel_k]

            is_on = c1.checkbox(f"使用", key=on_k)
            st.session_state[hold_on_k] = is_on
            
            # 選択肢を表示
            sel = c2.selectbox(f"GC {i}", gc_opts, key=sel_k)
            st.session_state[hold_sel_k] = sel
            
            if sel != "なし":
                # 指定したシートから内径データを取得
                val = st.session_state.MASTER_DATA[gc_sheet_name].get(sel, 0.0)
                # --- 【追加】マスターから長さを取得 ---
                length = st.session_state.MASTER_LEN.get(sel, 0)
                
                c2.caption(f"🔍 [PMDA検索]({get_pmda_url()}) で「**{sel}**」を検索")
                val = st.session_state.MASTER_DATA[gc_sheet_name].get(sel, 0.0)

                # 表示内容に長さを追加
                c3.write(f"{val*76.2:.1f}Fr / {val*25.4:.2f}mm / {val:.3f}\" / {length}cm")
                if is_on:
                    active_gc_in = val

# ② ガイドワイヤー (GW) - 最大4本
    with st.expander("② ガイドワイヤー (GW) - 最大4本", expanded=True):
        # 【改良】「ワイヤー」または「Wire」または「GW」という文字を含むシートを自動検索
        gw_sheet_name = next((s for s in st.session_state.MASTER_DATA.keys() 
                             if "ワイヤー" in s or "Wire" in s or "GW" in s), None)
        
        if gw_sheet_name:
            w_opts = ["なし"] + list(st.session_state.MASTER_DATA[gw_sheet_name].keys())
        else:
            w_opts = ["なし"]
            st.warning("⚠️ Excelに「ガイドワイヤー」や「Wire」という名前のシートが見つかりません。")

        for j in range(1, 5):
            c1, c2, c3 = st.columns([1, 3, 5])
            
            # --- キー設定と復元ロジック (既存のまま) ---
            on_k = f"w_on_v31_{j}"
            sel_k = f"w_s_v31_{j}"
            hold_on_k = f"v31_hold_w_on_{j}"
            hold_sel_k = f"v31_hold_w_s_{j}"

            if hold_on_k in st.session_state and on_k not in st.session_state:
                st.session_state[on_k] = st.session_state[hold_on_k]
            if hold_sel_k in st.session_state and sel_k not in st.session_state:
                st.session_state[sel_k] = st.session_state[hold_sel_k]

            is_on = c1.checkbox(f"使用 ", key=on_k)
            st.session_state[hold_on_k] = is_on
            
            # 選択肢を表示
            sel = c2.selectbox(f"GW {j}", w_opts, key=sel_k)
            st.session_state[hold_sel_k] = sel
            
            if sel != "なし":
                # 見つかったシートから外径データを取得
                val = st.session_state.MASTER_DATA[gw_sheet_name].get(sel, 0.0)
                # --- 【追加】マスターから長さを取得 ---
                length = st.session_state.MASTER_LEN.get(sel, 0)

                c2.caption(f"🔍 [PMDA検索]({get_pmda_url()}) で「**{sel}**」を検索")
                val = st.session_state.MASTER_DATA[gw_sheet_name].get(sel, 0.0)
                
                # mmからFrを計算 (mm * 3)
                val_mm = val * 25.4
                val_fr = val_mm * 3
                
                # --- 【修正】Frと長さを表示に追加 ---
                c3.write(f"{val_mm:.2f}mm / {val:.3f}\" / {val_fr:.1f}Fr / {length}cm")
                if is_on:
                    active_devices.append(val)

# ② 挿入デバイス (10個まで)
    with st.expander("② 挿入デバイス (10個まで)", expanded=True):
        # --- 【修正】GCとWire系以外の全シート名を「種別」の選択肢にする ---
        ignore_sheets = ["ガイドカテーテル", "ガイディングカテーテル", "ガイドワイヤー", "ワイヤー","Wire", "GW", "元シート"]
        other_sheets = [s for s in st.session_state.MASTER_DATA.keys() if s not in ignore_sheets]
        cat_list = ["なし"] + other_sheets
        
        for k in range(1, 11):
            c1, c2, c3, c4 = st.columns([0.5, 2, 3, 4])
            
            # --- 各項目ごとのキー設定 ---
            on_k = f"d_on_v31_{k}"
            t_k = f"t_s_v31_{k}"
            n_k = f"n_s_v31_{k}"
            
            # 各値を退避させるための特別なキー
            hold_on_k = f"v31_hold_on_{k}"
            hold_t_k = f"v31_hold_t_{k}"
            hold_n_k = f"v31_hold_n_{k}"

            # 【消失阻止ロジック：復元】
            if page == "2. 📏使用デバイス、干渉計算":
                if hold_on_k in st.session_state and on_k not in st.session_state:
                    st.session_state[on_k] = st.session_state[hold_on_k]
                if hold_t_k in st.session_state and t_k not in st.session_state:
                    st.session_state[t_k] = st.session_state[hold_t_k]
                if hold_n_k in st.session_state and n_k not in st.session_state:
                    st.session_state[n_k] = st.session_state[hold_n_k]

            # ① チェックボックス・② 種別選択（ウィジェット配置）
            is_active = c1.checkbox(" ", key=on_k)
            type_sel = c2.selectbox(f"種別 {k}", cat_list, key=t_k)

            # 【消失阻止ロジック：退避】
            if page == "2. 📏使用デバイス、干渉計算":
                st.session_state[hold_on_k] = is_active
                st.session_state[hold_t_k] = type_sel

            if type_sel != "なし":
                d_list = ["なし"] + list(st.session_state.MASTER_DATA.get(type_sel, {}).keys())
                name_sel = c3.selectbox(f"製品名 {k}", d_list, key=n_k)

                if page == "2. 📏使用デバイス、干渉計算":
                    st.session_state[hold_n_k] = name_sel

                if type_sel in ["バルーン", "ステント"]:
                    # 新しい入力用のキーを設定
                    size_dia_k = f"d_dia_v31_{k}"
                    size_len_k = f"d_len_v31_{k}"
                    
                    # 2列に分けて「径」と「長さ」の入力欄を作成
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        d_dia = st.text_input("径(mm)", key=size_dia_k, placeholder="3.0")
                    with col_s2:
                        d_len = st.text_input("長(mm)", key=size_len_k, placeholder="15")
                
                if name_sel != "なし":
                    # インチ値を取得
                    val_inch = st.session_state.MASTER_DATA[type_sel].get(name_sel, 0.0)
                    length = st.session_state.MASTER_LEN.get(name_sel, 0)
                    c3.caption(f"🔍 [PMDA検索]({get_pmda_url()}) で「**{name_sel}**」を検索")
                    
                    # --- 【修正】全単位への換算表示 ---
                    val_mm = val_inch * 25.4
                    val_fr = val_mm * 3
                    
                    # 表示（mm / inch / Fr / 長さ）
                    c4.write(f"{val_mm:.2f}mm / {val_inch:.3f}\" / {val_fr:.1f}Fr / {length}cm")

            if k < 10:
                st.divider()

# --- ④ シミュレーション描画（リアルタイム再計算版） ---
    st.divider()
    st.subheader("📏 デバイス干渉・可視化シミュレーション")

    active_device_vals = []
    active_gc_in = 0

    # 1. GCの内径取得（シート名を自動検索）
    # 「ガイディング」または「ガイド」または「GC」を含むシートを探す
    gc_sheet_name = next((s for s in st.session_state.MASTER_DATA.keys() 
                         if "ガイディング" in s or "ガイド" in s or "GC" in s), None)

    if gc_sheet_name:
        for i in range(1, 5):
            if st.session_state.get(f"gc_on_v31_{i}"):
                sel_gc = st.session_state.get(f"gc_s_v31_{i}")
                if sel_gc and sel_gc != "なし":
                    # --- 【修正】2階層辞書から内径を取得 ---
                    active_gc_in = st.session_state.MASTER_DATA[gc_sheet_name].get(sel_gc, 0.0)

    # 2. ワイヤーの外径取得（シート名を自動検索）
    # 「ワイヤー」または「Wire」または「GW」を含むシートを探す
    gw_sheet_name = next((s for s in st.session_state.MASTER_DATA.keys() 
                         if "ワイヤー" in s or "Wire" in s or "GW" in s), None)

    if gw_sheet_name:
        for j in range(1, 5):
            if st.session_state.get(f"w_on_v31_{j}"):
                sel_w = st.session_state.get(f"w_s_v31_{j}")
                if sel_w and sel_w != "なし":
                    # --- 【修正】2階層辞書から外径を取得 ---
                    val = st.session_state.MASTER_DATA[gw_sheet_name].get(sel_w, 0.0)
                    if val > 0:
                        active_device_vals.append(val)

    # 3. 挿入デバイスの外径取得
    for k in range(1, 11):
        if st.session_state.get(f"d_on_v31_{k}"):
            t_sel = st.session_state.get(f"t_s_v31_{k}") # これがシート名（種別）
            n_sel = st.session_state.get(f"n_s_v31_{k}") # これが製品名
            
            if t_sel and n_sel and n_sel != "なし":
                # すでに t_sel にシート名が入っているので、そのまま辞書を引く
                if t_sel in st.session_state.MASTER_DATA:
                    # --- 【修正】シート名(t_sel)と製品名(n_sel)から外径を取得 ---
                    val = st.session_state.MASTER_DATA[t_sel].get(n_sel, 0.0)
                    if val > 0:
                        active_device_vals.append(val)

    # --- 描画判定以降（重心補正ロジックなどはそのまま維持） ---

    # --- 描画判定 ---
    if not active_device_vals or active_gc_in == 0:
        st.info("💡 GCとデバイスを選択し、両方の『使用』にチェックを入れるとシミュレーションが即座に更新されます。")
    else:
        # ここからパッキング計算（以前の重心補正ロジックを維持）
        total_d = sum(active_device_vals)
        diff = active_gc_in - total_d
        
        # 通過不可時のGC縮小アルゴリズム
        if diff < 0:
            gc_r = (total_d * 0.8) / 2 
        else:
            gc_r = active_gc_in / 2

        # (以下、placed計算、重心補正、描画処理... インデントを揃えて継続)
        
# --- 1. デバイス群のパッキング配置 (placed作成) ---
        sorted_v = sorted(active_device_vals, reverse=True)
        placed = [] # (x, y, r)
        for d_val in sorted_v:
            r = d_val / 2
            if not placed: 
                pos = (0.0, 0.0)
            elif len(placed) == 1: 
                pos = (placed[0][2] + r, 0.0)
            else:
                best_p = (placed[-1][0] + r * 2, 0.0)
                min_dist = float('inf')
                for i in range(len(placed)):
                    for j in range(i + 1, len(placed)):
                        c1, c2 = placed[i], placed[j]
                        d_cc = math.sqrt((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2)
                        r1, r2 = c1[2] + r, c2[2] + r
                        if d_cc <= r1 + r2:
                            a = (r1**2 - r2**2 + d_cc**2) / (2 * d_cc)
                            h = math.sqrt(max(0, r1**2 - a**2))
                            x2 = c1[0] + a*(c2[0]-c1[0])/d_cc
                            y2 = c1[1] + a*(c2[1]-c1[1])/d_cc
                            for s in [-1, 1]:
                                tx = x2 + s*h*(c2[1]-c1[1])/d_cc
                                ty = y2 - s*h*(c2[0]-c1[0])/d_cc
                                if not any(math.sqrt((tx-p[0])**2 + (ty-p[1])**2) < (r+p[2])-0.0001 for p in placed):
                                    d_from_origin = math.sqrt(tx**2 + ty**2)
                                    if d_from_origin < min_dist:
                                        min_dist, best_p = d_from_origin, (tx, ty)
                pos = best_p
            placed.append((pos[0], pos[1], r))

        # --- 2. 重心補正と「真の広がり」の計算 ---
        all_x_min = [p[0] - p[2] for p in placed]
        all_x_max = [p[0] + p[2] for p in placed]
        all_y_min = [p[1] - p[2] for p in placed]
        all_y_max = [p[1] + p[2] for p in placed]
        
        ox = (min(all_x_min) + max(all_x_max)) / 2
        oy = (min(all_y_min) + max(all_y_max)) / 2
        
        # デバイス群の重心から最も遠い端までの距離（現在のデバイス群の半径）
        current_devices_r = max([math.sqrt((p[0]-ox)**2 + (p[1]-oy)**2) + p[2] for p in placed])

        # --- 3. 【核心】GC表示半径(gc_r)の動的再計算 ---
        if diff < 0:
            # 通過不可なら、GCの円を「デバイスの広がりよりもさらに小さく」設定する
            # これにより、ワイヤーを追加して群が大きくなっても、GCがそれより内側に描かれます
            gc_r = current_devices_r * 0.85
        else:
            gc_r = active_gc_in / 2

        # 描画範囲は常にデバイスの広がりかGCの大きい方に合わせる
        draw_limit = max(current_devices_r, gc_r) * 1.1

        # --- 4. 描画処理 ---
        fig, ax = plt.subplots(figsize=(4, 4))
        fig.patch.set_alpha(0)
        
        gc_ec = '#FF3333' if diff < 0 else 'white'
        gc_lw = 4.0 if diff < 0 else 3.0

        # ガイディングカテを描画
        ax.add_patch(plt.Circle((0, 0), gc_r, color='#111111', alpha=0.8, ec=gc_ec, lw=gc_lw, zorder=1))
        
        clrs = ['#FF99CC', '#99CCFF', '#CC99FF', '#FFCC99', '#FFFF99', '#99FFCC', '#FF9999', '#9999FF', '#E0E0E0', '#BDBDBD']
        for idx, p in enumerate(placed):
            pos_x = p[0] - ox
            pos_y = p[1] - oy
            dist_from_center = math.sqrt(pos_x**2 + pos_y**2) + p[2]
            
            # 判定は本来の内径で行う
            if dist_from_center > (active_gc_in / 2) + 0.0001:
                d_ec, d_lw = '#FF3333', 3.5
            else:
                d_ec, d_lw = 'white', 1.5
                
            ax.add_patch(plt.Circle((pos_x, pos_y), p[2], color=clrs[idx % 10], ec=d_ec, lw=d_lw, zorder=10, alpha=0.9))
        
        ax.set_xlim(-draw_limit, draw_limit)
        ax.set_ylim(-draw_limit, draw_limit)
        ax.set_aspect('equal')
        ax.axis('off')
        
        # --- 結果表示 ---
        col_res1, col_res2 = st.columns([1.2, 1])
        with col_res1:
            st.metric("有効デバイス合計外径", f"{total_d:.3f}\"")
            if diff > 0.002:
                st.success("### ✅ 通過可能")
            elif 0 <= diff <= 0.002:
                st.warning("### ⚠️ 余裕僅少")
            else:
                st.error("### ❌ 通過不可")
            st.markdown(f"**【差分詳細】**\n* **{abs(diff)*25.4*3:.2f} Fr**\n* **{abs(diff)*25.4:.2f} mm**")
        with col_res2:
            st.pyplot(fig)

elif page == "3. 📝治療記録ログ":
    st.header("📝 治療記録・拡張ログ")

    # 1. ページ2のデバイス情報を「参照のみ」で行う
    active_keys = [k for k in range(1, 11) 
    if st.session_state.get(f"v31_hold_on_{k}") and 
    st.session_state.get(f"v31_hold_t_{k}") in ["バルーン", "ステント"]
] 

    if 'log_permanent_storage' not in st.session_state:
        st.session_state.log_permanent_storage = {}
    if 'log_row_counts_final' not in st.session_state:
        st.session_state.log_row_counts_final = {}

    all_logs_for_export = []

    if not active_keys:
        st.warning("⚠️ デバイス干渉計算ページで『使用』にチェックが入ったデバイスがありません。")
    else:
        for k in active_keys:
            d_id = f"d_{k}"
            base_name = st.session_state.get(f"v31_hold_n_{k}", "Unknown")
            dev_type = st.session_state.get(f"v31_hold_t_{k}", "Device")

# --- 2. 【追加】径と長さを取得して名前を構成 ---
            d_dia = st.session_state.get(f"d_dia_v31_{k}", "")
            d_len = st.session_state.get(f"d_len_v31_{k}", "")
            
            if d_dia and d_len:
                dev_name = f"{base_name} ({d_dia} x {d_len} mm)"
            elif d_dia:
                dev_name = f"{base_name} ({d_dia} mm)"
            else:
                dev_name = base_name
            
            if d_id not in st.session_state.log_row_counts_final:
                st.session_state.log_row_counts_final[d_id] = 1
            
            with st.container(border=True):
                st.markdown(f"### 📦 {dev_type}: {dev_name}")
                
                # PMDA検索ガイドの表示
                pmda_top = get_pmda_url()
                st.info(f"""
                🔍 **PMDA製品情報検索ガイド**
                1. [PMDA 医療機器検索サイト]({pmda_top}) を開く
                2. 「ブランド名（販売名）」欄に **{base_name}** を入力して検索
                """)

                h1, h2, h3, _ = st.columns([2, 2, 2, 1])
                h1.caption("対象病変 (#)")
                h2.caption("気圧 (atm)")
                h3.caption("時間 (sec)")

                for i in range(st.session_state.log_row_counts_final[d_id]):
                    c1, c2, c3, _ = st.columns([2, 2, 2, 1])
                    
                    # keyを完全に独立させ、かつvalueを書かない
                    k_t = f"LOG_FINAL_T_{d_id}_{i}"
                    k_p = f"LOG_FINAL_P_{d_id}_{i}"
                    k_s = f"LOG_FINAL_S_{d_id}_{i}"

# --- 【ここから追加：復元】 ---
                    for k_key in [k_t, k_p, k_s]:
                        if k_key in st.session_state.log_permanent_storage:
                            st.session_state[k_key] = st.session_state.log_permanent_storage[k_key]
                    # --- ここまで ---

                    vt = c1.text_input("T", key=k_t, label_visibility="collapsed")
                    vp = c2.text_input("P", key=k_p, label_visibility="collapsed")
                    vs = c3.text_input("S", key=k_s, label_visibility="collapsed")

                    if vt: st.session_state.log_permanent_storage[k_t] = vt
                    if vp: st.session_state.log_permanent_storage[k_p] = vp
                    if vs: st.session_state.log_permanent_storage[k_s] = vs
                    # --- ここまで ---

                    if vt or vp or vs:
                        all_logs_for_export.append({
                            "病変": vt, "製品名": dev_name, "回数": i+1, "気圧": vp, "秒数": vs
                        })

                if st.button(f"➕ 行を追加 ({dev_name})", key=f"ADD_B_FINAL_{d_id}"):
                    st.session_state.log_row_counts_final[d_id] += 1
                    st.rerun()

        if all_logs_for_export:
            st.divider()
            df = pd.DataFrame(all_logs_for_export)
            st.download_button("📥 CSVで保存", df.to_csv(index=False).encode('utf_8_sig'), f"PCI_Log_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")

elif page == "📖 資料":
    st.header("📖 学術資料・製品マニュアル")

    import os
    pdf_dir = "manuals" 
    if not os.path.exists(pdf_dir):
        os.makedirs(pdf_dir)

    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]

    if not pdf_files:
        st.info("📂 manuals フォルダにPDFを入れてください。")
    else:
        # --- 1. セッション状態の初期化 ---
        if 'pdf_page' not in st.session_state:
            st.session_state.pdf_page = 1

        with st.sidebar:
            st.divider()
            st.subheader("資料コントロール")
            selected_pdf = st.selectbox("閲覧資料を選択", pdf_files, key="pdf_sel")
            path_to_pdf = os.path.join(pdf_dir, selected_pdf)

            # --- ページめくりボタン ---
            st.write(f"現在のページ: **{st.session_state.pdf_page}**")
            col1, col2 = st.columns(2)
            if col1.button("⬅️ 前へ"):
                st.session_state.pdf_page = max(1, st.session_state.pdf_page - 1)
            if col2.button("次へ ➡️"):
                 st.session_state.pdf_page += 1
            
            # 任意のページジャンプ
            jump_p = st.number_input("ページ指定", min_value=1, value=st.session_state.pdf_page)
            if jump_p != st.session_state.pdf_page:
                st.session_state.pdf_page = jump_p

            st.divider()
            # 回転（表示幅の切り替え）
            # ライブラリが回転に対応していないため、表示幅を広げることで横向き資料に対応します
            orient = st.radio("表示の向き", ["縦（標準）", "横（ワイド）"], horizontal=True)
            view_width = 1000 if orient == "横（ワイド）" else 700

            # ダウンロード
            with open(path_to_pdf, "rb") as f:
                st.download_button("💾 PDFを開く/保存", f, file_name=selected_pdf)

        # --- 2. PDF表示エリア ---
        st.caption(f"表示中: {selected_pdf} ( Page: {st.session_state.pdf_page} )")
        
        try:
            from streamlit_pdf_viewer import pdf_viewer
            
            # 1ページだけを確実に描画
            pdf_viewer(
                input=path_to_pdf,
                width=view_width,
                pages_to_render=[st.session_state.pdf_page]
            )
        except Exception as e:
            st.error(f"表示エラー: {e}")
            st.info("ページが存在しないか、ファイルが重すぎる可能性があります。")

elif page == "🔍 Tips検索":
    st.header("🔍 過去の症例Tips検索")
    st.caption("ファイルメーカーから出力された過去の知恵（Tips）を検索します。")

    import pandas as pd
    import os

    # --- CSV自動読み込み設定 ---
    # リポジトリ内の data フォルダにある CSV を指定
    csv_path = "data/fm_export.csv" 
    
    df = None

    # ファイルが存在するか確認して自動読み込み
    if os.path.exists(csv_path):
        try:
            # まずは標準のUTF-8で試行
            df = pd.read_csv(csv_path, encoding='utf-8')
        except:
            try:
                # 失敗したらShift-JIS(cp932)で試行
                df = pd.read_csv(csv_path, encoding='cp932')
            except Exception as e:
                st.error(f"CSVの読み込みに失敗しました。文字コードを確認してください: {e}")
    else:
        st.warning(f"⚠️ CSVファイルが見つかりません。パスを確認してください: {csv_path}")
        st.info("Streamlit Cloudの場合、GitHubの data フォルダに fm_export.csv を配置して下さい。")

    # --- 検索インターフェース ---
    if df is not None:
        search_query = st.text_input("キーワードを入力（例：通過困難、屈曲、ガイドライナー、SLENDER）", "")

        if search_query:
            # 全ての列を対象に、キーワードが含まれる行を抽出（大文字小文字を区別しない）
            mask = df.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)
            result_df = df[mask]

            st.subheader(f"検索結果: {len(result_df)} 件")

            if len(result_df) > 0:
                for i, row in result_df.iterrows():
                    # 症例日や診断名をタイトルにして展開パネルを作成
                    date_info = row.get('症例日', '日付不明')
                    diag_info = row.get('診断名', '症例')
                    
                    with st.expander(f"📅 {date_info} | {diag_info}"):
                        st.markdown("---")
                        # メインのコメント（Tips）を表示
                        st.info(f"**💡 手技のコメント・Tips**\n\n{row.get('コメント', '内容なし')}")
                        
                        # サブ情報の表示
                        col1, col2 = st.columns(2)
                        if '使用デバイス' in row:
                            col1.caption(f"🛠 **使用デバイス**\n{row['used_devices']}")
                        if '術者' in row:
                            col2.caption(f"👨‍⚕️ **術者**: {row['doctor']}")
            else:
                st.write("該当する症例は見つかりませんでした。別の単語を試してください。")
        else:
            st.info("キーワードを入力すると、蓄積された過去のデータから関連するTipsを表示します。")
