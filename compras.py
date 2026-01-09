import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import plotly.express as px

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Amâncio Gestão Pro", page_icon="🏗️", layout="wide")

# 2. DESIGN ADAPTATIVO (CSS)
st.markdown("""
    <style>
    :root {
        --primary-bg: #ffffff; --text-main: #1e293b; --accent: #2563eb; --danger: #ef4444;
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --primary-bg: #0e1117; --text-main: #f0f6fc; --accent: #58a6ff; --danger: #f85149;
        }
    }
    .stApp { background-color: var(--primary-bg); }
    h1, h2, h3, p, label { color: var(--text-main) !important; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; background: var(--accent); color: white !important; font-weight: bold; border: none; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; text-align: center; padding: 10px; font-size: 12px; color: #8b949e; background: var(--primary-bg); border-top: 1px solid #30363d; z-index: 100; }
    
    /* Ajuste para Mobile */
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. FUNÇÕES DE BANCO DE DADOS
def get_connection():
    try:
        return psycopg2.connect(st.secrets["db_url"])
    except Exception as e:
        st.error(f"Erro crítico de conexão: {e}")
        return None

# 4. CONTROLE DE ACESSO
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# 5. SIDEBAR
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1063/1063196.png", width=80)
    st.title("Amâncio Obras")
    
    if not st.session_state["authenticated"]:
        with st.expander("🔐 Login Admin"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.button("Entrar"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos")
        menu = st.radio("Navegação:", ["📊 Saldo Geral"])
    else:
        st.success(f"Logado: {st.secrets['auth']['username']}")
        menu = st.radio("Navegação:", [
            "📊 Saldo Geral", 
            "📋 Histórico e Inventário", 
            "📥 Entrada de Material", 
            "📤 Saída de Material", 
            "🔧 Ajuste de Balanço",
            "🗑️ Gerenciar Lançamentos",
            "📦 Cadastrar Material"
        ])
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

# 6. LOGICA DAS TELAS
conn = get_connection()

if conn:
    # --- TELA: SALDO GERAL ---
    if menu == "📊 Saldo Geral":
        st.title("📊 Saldo em Estoque")
        
        df_produtos = pd.read_sql("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao", conn)
        df_mov = pd.read_sql("SELECT codigo, tipo, quantidade FROM movimentacoes", conn)
        
        if not df_produtos.empty:
            if not df_mov.empty:
                df_mov['val'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] in ['Entrada', 'Ajuste(+)'] else -x['quantidade'], axis=1)
                saldos_calc = df_mov.groupby('codigo')['val'].sum().reset_index()
                resultado = pd.merge(df_produtos, saldos_calc, on='codigo', how='left')
                resultado['val'] = resultado['val'].fillna(0)
            else:
                resultado = df_produtos.copy()
                resultado['val'] = 0
            
            resultado.columns = ['Cód', 'Descrição', 'Und', 'Saldo Atual']
            
            busca = st.text_input("🔍 Pesquisar material:", placeholder="Nome ou Código...")
            if busca:
                resultado = resultado[resultado['Descrição'].str.contains(busca, case=False) | resultado['Cód'].str.contains(busca, case=False)]
            
            st.dataframe(resultado, use_container_width=True, hide_index=True,
                         column_config={"Saldo Atual": st.column_config.NumberColumn(format="%.2f")})
        else:
            st.info("Nenhum material cadastrado.")

    # --- TELA: CADASTRO ---
    elif menu == "📦 Cadastrar Material":
        st.title("📦 Novo Produto")
        with st.form("form_cad", clear_on_submit=True):
            c1 = st.text_input("Código (Ex: CIMENT-01)")
            c2 = st.text_input("Descrição (Ex: Cimento CP-II)")
            c3 = st.selectbox("Unidade de Medida", ["Unidade", "Kg", "Metro", "M2", "M3", "Litro", "Saco", "Barra", "Par"])
            if st.form_submit_button("Salvar Cadastro"):
                if c1 and c2:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO produtos (codigo, descricao, unidade) VALUES (%s, %s, %s) ON CONFLICT (codigo) DO NOTHING", 
                               (c1.upper(), c2.upper(), c3))
                    conn.commit()
                    st.success(f"Material {c2} cadastrado!")
                else:
                    st.warning("Preencha Código e Descrição.")

    # --- TELA: ENTRADA ---
    elif menu == "📥 Entrada de Material":
        st.title("📥 Entrada Detalhada")
        prods = pd.read_sql("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao", conn)
        if not prods.empty:
            with st.form("form_ent", clear_on_submit=True):
                # Mostra código, descrição e unidade no seletor
                item_label = prods['codigo'] + " - " + prods['descricao'] + " (" + prods['unidade'] + ")"
                item = st.selectbox("Selecione o Material", item_label)
                qtd = st.number_input("Quantidade", min_value=0.01, step=0.01)
                nf = st.text_input("NF / Documento")
                forn = st.text_input("Fornecedor")
                obra = st.text_input("Obra de Destino")
                if st.form_submit_button("Confirmar Entrada"):
                    cod_sel = item.split(" - ")[0]
                    des_sel = item.split(" - ")[1].split(" (")[0]
                    cur = conn.cursor()
                    cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                               ("Entrada", datetime.now().date(), obra, cod_sel, des_sel, qtd, f"NF: {nf} | Forn: {forn}"))
                    conn.commit()
                    st.success("Entrada registrada!")
        else:
            st.warning("Cadastre um material primeiro.")

    # --- TELA: SAÍDA ---
    elif menu == "📤 Saída de Material":
        st.title("📤 Registro de Saída")
        prods = pd.read_sql("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao", conn)
        if not prods.empty:
            with st.form("form_sai", clear_on_submit=True):
                item_label = prods['codigo'] + " - " + prods['descricao'] + " (" + prods['unidade'] + ")"
                item = st.selectbox("Selecione o Material", item_label)
                qtd = st.number_input("Quantidade", min_value=0.01, step=0.01)
                resp = st.text_input("Responsável")
                dest = st.text_input("Local de Uso")
                if st.form_submit_button("Confirmar Saída"):
                    cod_sel = item.split(" - ")[0]
                    des_sel = item.split(" - ")[1].split(" (")[0]
                    cur = conn.cursor()
                    cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                               ("Saída", datetime.now().date(), "Estoque", cod_sel, des_sel, qtd, f"Resp: {resp} | Dest: {dest}"))
                    conn.commit()
                    st.warning("Saída registrada!")

    # --- TELA: GERENCIAR (EXCLUIR) ---
    elif menu == "🗑️ Gerenciar Lançamentos":
        st.title("🗑️ Histórico e Exclusão")
        df_lista = pd.read_sql("SELECT * FROM movimentacoes ORDER BY id DESC LIMIT 50", conn)
        if not df_lista.empty:
            for idx, row in df_lista.iterrows():
                with st.expander(f"#{row['id']} - {row['tipo']} - {row['descricao']} ({row['quantidade']})"):
                    st.write(f"Data: {row['data']} | Ref: {row['referencia']}")
                    if st.button("❌ Excluir", key=f"btn_{row['id']}"):
                        cur = conn.cursor()
                        cur.execute("DELETE FROM movimentacoes WHERE id = %s", (row['id'],))
                        conn.commit()
                        st.error("Excluído!")
                        st.rerun()

    # --- TELA: HISTÓRICO ---
    elif menu == "📋 Histórico e Inventário":
        st.title("📋 Histórico Completo")
        df_hist = pd.read_sql("SELECT * FROM movimentacoes ORDER BY data DESC, id DESC", conn)
        if not df_hist.empty:
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
            st.download_button("📥 Baixar CSV", df_hist.to_csv(index=False).encode('utf-8'), "historico.csv")

    # --- TELA: AJUSTE ---
    elif menu == "🔧 Ajuste de Balanço":
        st.title("🔧 Ajuste de Balanço")
        df_p = pd.read_sql("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao", conn)
        if not df_p.empty:
            with st.form("f_ajuste"):
                item = st.selectbox("Material", df_p['codigo'] + " - " + df_p['descricao'])
                cod_aj = item.split(" - ")[0]
                # Cálculo de saldo atual para referência
                df_c = pd.read_sql(f"SELECT tipo, quantidade FROM movimentacoes WHERE codigo = '{cod_aj}'", conn)
                saldo_at = 0
                if not df_c.empty:
                    df_c['v'] = df_c.apply(lambda x: x['quantidade'] if x['tipo'] in ['Entrada', 'Ajuste(+)'] else -x['quantidade'], axis=1)
                    saldo_at = df_c['v'].sum()
                
                st.write(f"Saldo Atual: {saldo_at:.2f}")
                nova_q = st.number_input("Quantidade Real Física", min_value=0.0)
                motivo = st.text_input("Motivo")
                if st.form_submit_button("Ajustar"):
                    diff = nova_q - saldo_at
                    if diff != 0:
                        tipo = "Ajuste(+)" if diff > 0 else "Ajuste(-)"
                        cur = conn.cursor()
                        cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                   (tipo, datetime.now().date(), "BALANÇO", cod_aj, item.split(" - ")[1], abs(diff), motivo))
                        conn.commit()
                        st.success("Ajustado!")
                        st.rerun()

    conn.close()

st.markdown('<div class="footer">Claudio Boni Junior - Gestão de Obras</div>', unsafe_allow_html=True)
