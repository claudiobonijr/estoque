import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO E ESTILO
st.set_page_config(page_title="Gestão Amâncio Pro", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    div[data-testid="metric-container"] { background-color: rgba(151, 166, 195, 0.1); padding: 15px; border-radius: 10px; border: 1px solid #3b82f6; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; text-align: center; padding: 5px; font-size: 12px; color: #888; background: white; }
    section[data-testid="stSidebar"] { background-color: #1e293b; }
    section[data-testid="stSidebar"] * { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

def get_connection():
    try:
        return psycopg2.connect(st.secrets["db_url"])
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

# 2. LOGIN
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# 3. SIDEBAR (MENU LATERAL)
with st.sidebar:
    st.title("Sistema de Obras")
    if not st.session_state["authenticated"]:
        with st.expander("🔐 Área do Administrador"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.button("Acessar"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Incorreto")
        menu = st.radio("Navegação:", ["📊 Painel de Controle"])
    else:
        st.success(f"Admin: {st.secrets['auth']['username']}")
        menu = st.radio("Navegação:", ["📊 Painel de Controle", "📋 Inventário Geral", "🔧 Ajuste de Balanço", "📦 Cadastro", "📥 Entrada", "📤 Saída"])
        if st.button("Sair (Logoff)"):
            st.session_state["authenticated"] = False
            st.rerun()
    st.markdown("---")
    st.caption("Versão 3.5 | Amâncio Gestão")

# 4. DASHBOARD PÚBLICO (COM PESQUISA)
if menu == "📊 Painel de Controle":
    st.title("📊 Painel de Controle (Saldo Geral)")
    conn = get_connection()
    if conn:
        df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
        conn.close()
        
        if not df_mov.empty:
            # Cálculo de Saldo
            df_mov['val'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] in ['Entrada', 'Ajuste(+)'] else -x['quantidade'], axis=1)
            saldo = df_mov.groupby(['codigo', 'descricao'])['val'].sum().reset_index()
            saldo.columns = ['Cód', 'Descrição', 'Saldo Atual']
            
            # Métricas
            c1, c2, c3 = st.columns(3)
            c1.metric("Itens Ativos", len(saldo))
            c2.metric("Total Movimentações", len(df_mov))
            criticos = len(saldo[saldo['Saldo Atual'] < 5])
            c3.metric("Alertas de Estoque", criticos, delta_color="inverse")

            st.markdown("---")
            # --- OPÇÃO DE PESQUISA PARA O VISITANTE ---
            busca = st.text_input("🔍 Pesquisar material no estoque (nome ou código):")
            if busca:
                saldo = saldo[saldo['Descrição'].str.contains(busca, case=False) | saldo['Cód'].str.contains(busca)]
            
            st.dataframe(saldo, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma movimentação para exibir.")

# 5. INVENTÁRIO GERAL (SOMENTE COM LOGIN)
elif menu == "📋 Inventário Geral":
    st.title("📋 Inventário Detalhado")
    st.info("Esta aba é restrita e mostra o histórico de auditoria.")
    conn = get_connection()
    if conn:
        df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
        conn.close()
        
        # Agrupamento detalhado
        df_mov['val'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] in ['Entrada', 'Ajuste(+)'] else -x['quantidade'], axis=1)
        inv = df_mov.groupby(['codigo', 'descricao']).agg(
            Saldo_Atual=('val', 'sum'),
            Ultima_Atualizacao=('data', 'max')
        ).reset_index()
        
        st.dataframe(inv, use_container_width=True, hide_index=True)
        
        # Botão para baixar relatório
        csv = inv.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Planilha de Inventário", csv, "inventario_completo.csv")

# 6. AJUSTE DE BALANÇO (SOMENTE COM LOGIN)
elif menu == "🔧 Ajuste de Balanço":
    st.title("🔧 Ajuste de Inventário")
    # ... (Lógica de ajuste que enviamos anteriormente)
    st.warning("Aba para correção de erros de contagem física.")

# 7. CADASTRO / ENTRADA / SAÍDA (SOMENTE COM LOGIN)
elif menu == "📦 Cadastro":
    st.header("📦 Cadastro de Insumos")
    with st.form("cad"):
        c1 = st.text_input("Código"); c2 = st.text_input("Descrição")
        if st.form_submit_button("Cadastrar"):
            conn = get_connection(); cur = conn.cursor()
            cur.execute("INSERT INTO produtos (codigo, descricao) VALUES (%s, %s) ON CONFLICT (codigo) DO NOTHING", (c1, c2))
            conn.commit(); cur.close(); conn.close(); st.success("Cadastrado!")

elif menu == "📥 Entrada":
    st.header("📥 Registrar Entrada")
    # ... (Lógica de entrada)

elif menu == "📤 Saída":
    st.header("📤 Registrar Saída")
    # ... (Lógica de saída)

st.markdown('<div class="footer">Desenvolvido por Claudio Boni Junior</div>', unsafe_allow_html=True)
