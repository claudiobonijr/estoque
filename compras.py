import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO
st.set_page_config(page_title="Gestão Amâncio Pro", page_icon="🏗️", layout="wide")

# Estilos Visuais
st.markdown("""
    <style>
    div[data-testid="metric-container"] { background-color: rgba(151, 166, 195, 0.1); padding: 15px; border-radius: 10px; border: 1px solid #3b82f6; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; text-align: center; padding: 5px; font-size: 12px; color: #888; background: white; }
    </style>
    """, unsafe_allow_html=True)

def get_connection():
    return psycopg2.connect(st.secrets["db_url"])

# 2. LOGIN
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# 3. SIDEBAR
with st.sidebar:
    st.title("Sistema de Obras")
    if not st.session_state["authenticated"]:
        with st.expander("🔐 Login"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.button("Acessar"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
        menu = st.radio("Menu", ["📊 Dashboard", "📋 Inventário Geral"])
    else:
        st.success(f"Admin: {st.secrets['auth']['username']}")
        menu = st.radio("Menu", ["📊 Dashboard", "📋 Inventário Geral", "🔧 Ajuste de Balanço", "📦 Cadastro", "📥 Entrada", "📤 Saída"])
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

# 4. DASHBOARD (VISÃO GERAL)
if menu == "📊 Dashboard":
    st.title("📊 Painel de Controle")
    conn = get_connection()
    df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
    conn.close()
    
    if not df_mov.empty:
        df_mov['val'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] in ['Entrada', 'Ajuste(+)'] else -x['quantidade'], axis=1)
        saldo = df_mov.groupby(['codigo', 'descricao'])['val'].sum().reset_index()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Itens no Sistema", len(saldo))
        c2.metric("Movimentações totais", len(df_mov))
        criticos = len(saldo[saldo['val'] < 5])
        c3.metric("Alertas Críticos", criticos, delta=-criticos, delta_color="inverse")
        
        st.subheader("📦 Saldo Rápido")
        st.dataframe(saldo, use_container_width=True, hide_index=True)
    else:
        st.info("Aguardando lançamentos.")

# 5. INVENTÁRIO GERAL (CONFERÊNCIA)
elif menu == "📋 Inventário Geral":
    st.title("📋 Inventário de Materiais")
    st.markdown("Lista completa para conferência e auditoria física.")
    conn = get_connection()
    df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
    conn.close()
    
    if not df_mov.empty:
        df_mov['val'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] in ['Entrada', 'Ajuste(+)'] else -x['quantidade'], axis=1)
        inv = df_mov.groupby(['codigo', 'descricao']).agg(Saldo=('val', 'sum'), Ultima=('data', 'max')).reset_index()
        
        # Filtro de busca
        busca = st.text_input("Pesquisar Item...")
        if busca:
            inv = inv[inv['descricao'].str.contains(busca, case=False)]
            
        st.table(inv) # Tabela simples e limpa para impressão
        csv = inv.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Lista de Conferência", csv, "inventario.csv")

# 6. AJUSTE DE BALANÇO (A OPÇÃO QUE FALTAVA)
elif menu == "🔧 Ajuste de Balanço":
    st.title("🔧 Ajuste de Inventário (Balanço)")
    st.warning("Use esta função apenas para corrigir o estoque após uma contagem física.")
    
    conn = get_connection()
    prods = pd.read_sql("SELECT * FROM produtos", conn)
    df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
    conn.close()
    
    with st.form("balanco"):
        item = st.selectbox("Selecione o Item para ajustar", prods['codigo'] + " - " + prods['descricao'])
        # Calcular saldo atual para mostrar ao usuário
        cod_sel = item.split(" - ")[0]
        hist = df_mov[df_mov['codigo'] == cod_sel]
        hist['val'] = hist.apply(lambda x: x['quantidade'] if x['tipo'] in ['Entrada', 'Ajuste(+)'] else -x['quantidade'], axis=1)
        saldo_atual = hist['val'].sum()
        
        st.write(f"**Saldo atual no sistema:** {saldo_atual}")
        contagem = st.number_input("Quantidade real encontrada na prateleira:", min_value=0.0)
        motivo = st.text_input("Motivo do ajuste (Ex: Perda, Erro de lançamento, Sobra)")
        
        if st.form_submit_button("Confirmar Ajuste"):
            diferenca = contagem - saldo_atual
            tipo_ajuste = 'Ajuste(+)' if diferenca > 0 else 'Ajuste(-)'
            
            conn = get_connection(); cur = conn.cursor()
            cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       (tipo_ajuste, datetime.now().date(), "Balanço/Inventário", cod_sel, item.split(" - ")[1], abs(diferenca), motivo))
            conn.commit(); cur.close(); conn.close()
            st.success(f"Estoque ajustado de {saldo_atual} para {contagem}!")

# 7. CADASTRO / ENTRADA / SAÍDA (Manter lógica v2.2)
elif menu == "📦 Cadastro":
    st.title("📦 Cadastro")
    with st.form("cad"):
        c1 = st.text_input("Código"); c2 = st.text_input("Descrição")
        if st.form_submit_button("Cadastrar"):
            conn = get_connection(); cur = conn.cursor()
            cur.execute("INSERT INTO produtos (codigo, descricao) VALUES (%s, %s) ON CONFLICT (codigo) DO NOTHING", (c1, c2))
            conn.commit(); cur.close(); conn.close(); st.success("OK!")

elif menu == "📥 Entrada":
    st.title("📥 Entrada")
    # ... (mesma lógica de entrada anterior)

elif menu == "📤 Saída":
    st.title("📤 Saída")
    # ... (mesma lógica de saída anterior)

st.markdown('<div class="footer">Desenvolvido por Claudio Boni Junior</div>', unsafe_allow_html=True)
