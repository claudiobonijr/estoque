import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO E ESTILO
st.set_page_config(page_title="Gestão Amâncio Pro", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    div[data-testid="metric-container"] { background-color: rgba(151, 166, 195, 0.1); padding: 15px; border-radius: 10px; border: 1px solid #3b82f6; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; text-align: center; padding: 5px; font-size: 12px; color: #888; background: white; z-index: 100; }
    section[data-testid="stSidebar"] { background-color: #1e293b; }
    section[data-testid="stSidebar"] * { color: white !important; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #3b82f6; color: white; }
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

# 3. SIDEBAR
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
    st.caption("Versão 4.0 | Amâncio Gestão")

# 4. DASHBOARD PÚBLICO
if menu == "📊 Painel de Controle":
    st.title("📊 Painel de Controle (Saldo Geral)")
    conn = get_connection()
    if conn:
        df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
        conn.close()
        if not df_mov.empty:
            df_mov['val'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] in ['Entrada', 'Ajuste(+)'] else -x['quantidade'], axis=1)
            saldo = df_mov.groupby(['codigo', 'descricao'])['val'].sum().reset_index()
            saldo.columns = ['Cód', 'Descrição', 'Saldo Atual']
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Itens Ativos", len(saldo))
            c2.metric("Total Movimentações", len(df_mov))
            criticos = len(saldo[saldo['Saldo Atual'] < 5])
            c3.metric("Alertas de Estoque", criticos, delta_color="inverse")

            st.markdown("---")
            busca = st.text_input("🔍 Pesquisar material no estoque:")
            if busca:
                saldo = saldo[saldo['Descrição'].str.contains(busca, case=False) | saldo['Cód'].str.contains(busca)]
            st.dataframe(saldo, use_container_width=True, hide_index=True)

# 5. INVENTÁRIO GERAL (LOGADO)
elif menu == "📋 Inventário Geral":
    st.title("📋 Inventário Detalhado")
    conn = get_connection()
    if conn:
        df_mov = pd.read_sql("SELECT * FROM movimentacoes ORDER BY data DESC", conn)
        conn.close()
        st.write("Histórico completo de todas as movimentações:")
        st.dataframe(df_mov, use_container_width=True)

# 6. ENTRADA (MÁXIMO DE INFORMAÇÃO)
elif menu == "📥 Entrada":
    st.title("📥 Registro de Entrada (NF / Compra)")
    conn = get_connection()
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    conn.close()

    if prods.empty:
        st.warning("Nenhum produto cadastrado. Vá em '📦 Cadastro' primeiro.")
    else:
        with st.form("form_entrada", clear_on_submit=True):
            col1, col2 = st.columns(2)
            item = col1.selectbox("Material", prods['codigo'] + " - " + prods['descricao'])
            qtd = col2.number_input("Quantidade Recebida", min_value=0.01, step=0.01)
            
            col3, col4 = st.columns(2)
            nf = col3.text_input("Número da Nota Fiscal (NF)")
            forn = col4.text_input("Fornecedor / Loja")
            
            obra = st.text_input("Obra de Destino (Onde o material vai ficar guardado)")
            obs = st.text_area("Observações Adicionais (Ex: Material chegou com atraso, marca tal...)")
            
            data_ent = st.date_input("Data do Recebimento", datetime.now())

            if st.form_submit_button("✅ SALVAR ENTRADA"):
                cod_sel, des_sel = item.split(" - ")[0], item.split(" - ")[1]
                ref_completa = f"NF: {nf} | Forn: {forn} | Obs: {obs}"
                
                conn = get_connection(); cur = conn.cursor()
                cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                           ("Entrada", data_ent, obra, cod_sel, des_sel, qtd, ref_completa))
                conn.commit(); cur.close(); conn.close()
                st.success(f"Entrada de {qtd} un de {des_sel} registrada com sucesso!")

# 7. SAÍDA (RASTRREABILIDADE TOTAL)
elif menu == "📤 Saída":
    st.title("📤 Registro de Saída (Requisição)")
    conn = get_connection()
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    conn.close()

    with st.form("form_saida", clear_on_submit=True):
        col1, col2 = st.columns(2)
        item = col1.selectbox("Material Retirado", prods['codigo'] + " - " + prods['descricao'])
        qtd = col2.number_input("Quantidade Retirada", min_value=0.01, step=0.01)
        
        col3, col4 = st.columns(2)
        responsavel = col3.text_input("Quem retirou? (Nome do Colaborador)")
        destino = col4.text_input("Frente de Serviço / Setor / Apartamento")
        
        obra_origem = st.text_input("Obra / Almoxarifado de Origem")
        obs_saida = st.text_area("Motivo da Saída ou Observações")
        
        data_sai = st.date_input("Data da Retirada", datetime.now())

        if st.form_submit_button("🚨 CONFIRMAR SAÍDA"):
            cod_sel, des_sel = item.split(" - ")[0], item.split(" - ")[1]
            ref_saida = f"Resp: {responsavel} | Destino: {destino} | Obs: {obs_saida}"
            
            conn = get_connection(); cur = conn.cursor()
            cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       ("Saída", data_sai, obra_origem, cod_sel, des_sel, qtd, ref_saida))
            conn.commit(); cur.close(); conn.close()
            st.warning(f"Baixa de {qtd} un de {des_sel} concluída!")

# 8. CADASTRO E AJUSTE (MANTIDOS)
elif menu == "📦 Cadastro":
    st.title("📦 Cadastro de Materiais")
    with st.form("cad_materiais"):
        c1, c2 = st.columns(2)
        cod = c1.text_input("Código Único (Ex: CIMENT-01)")
        des = c2.text_input("Descrição (Ex: Cimento CP-II 50kg)")
        if st.form_submit_button("💾 Salvar Novo Item"):
            if cod and des:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("INSERT INTO produtos (codigo, descricao) VALUES (%s, %s) ON CONFLICT (codigo) DO NOTHING", (cod.upper(), des.upper()))
                conn.commit(); cur.close(); conn.close(); st.success("Item cadastrado!")

elif menu == "🔧 Ajuste de Balanço":
    st.title("🔧 Ajuste de Inventário")
    st.info("Use para correções após contagem física.")
    # (Lógica de ajuste simplificada aqui...)

st.markdown(f'<div class="footer">Desenvolvido por Claudio Boni Junior - {datetime.now().year}</div>', unsafe_allow_html=True)
