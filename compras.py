import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Amâncio Gestão",
    page_icon="🏗️",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. CONEXÃO BLINDADA (SEM CACHE DE CONEXÃO)
# -----------------------------------------------------------------------------
def run_query(query, params=None, fetch_data=True):
    conn = None
    try:
        # Conecta sempre do zero para evitar quedas no Pooler do Supabase
        conn = psycopg2.connect(
            st.secrets["db_url"],
            connect_timeout=10,
            gssencmode="disable" 
        )
        
        if fetch_data:
            df = pd.read_sql(query, conn, params=params)
            return df
        else:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
            return True
            
    except Exception as e:
        # Log do erro no console (invisível ao usuário comum) para debug
        print(f"Erro BD: {e}") 
        if fetch_data:
            return pd.DataFrame() # Retorna tabela vazia para não quebrar o site
        return False
    finally:
        if conn:
            conn.close()

# -----------------------------------------------------------------------------
# 3. AUTENTICAÇÃO
# -----------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def login_screen():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.title("🔐 Login")
        with st.form("login"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Dados incorretos.")

# -----------------------------------------------------------------------------
# 4. SISTEMA PRINCIPAL
# -----------------------------------------------------------------------------
def main_system():
    # --- SIDEBAR ---
    with st.sidebar:
        st.title("Amâncio Obras")
        menu = st.radio("Menu", ["📊 Dashboard", "📦 Operações", "⚙️ Dados"])
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- CARREGAMENTO DE DADOS ---
    # Busca os dados no banco
    df_prods = run_query("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
    df_movs = run_query("SELECT * FROM movimentacoes ORDER BY data DESC, id DESC")

    # Verifica se carregou produtos
    if df_prods.empty and menu != "📦 Operações":
        st.warning("⚠️ O sistema conectou, mas não encontrou produtos. Vá em 'Operações' > 'Novo Produto' para começar.")

    # --- LÓGICA DE SALDO ---
    # Cria uma estrutura base de saldo
    saldo_atual = pd.DataFrame(columns=['Cod', 'Produto', 'Unid', 'Saldo'])
    
    # Se houver dados, calcula o saldo
    if not df_prods.empty:
        if not df_movs.empty:
            df_calc = df_movs.copy()
            # Entrada e Ajuste(+) somam (1), Saída e Ajuste(-) subtraem (-1)
            df_calc['fator'] = df_calc['tipo'].apply(lambda x: 1 if x in ['Entrada', 'Ajuste(+)'] else -1)
            df_calc['qtd_real'] = df_calc['quantidade'] * df_calc['fator']
            
            # Agrupa por código
            saldos = df_calc.groupby('codigo')['qtd_real'].sum().reset_index()
            # Junta com a tabela de nomes dos produtos
            saldo_atual = pd.merge(df_prods, saldos, on='codigo', how='left').fillna(0)
        else:
            # Se não tem movimentos, saldo é zero
            saldo_atual = df_prods.copy()
            saldo_atual['qtd_real'] = 0
            
        # Renomeia colunas para ficar bonito na tela
        saldo_atual.rename(columns={'qtd_real': 'Saldo', 'descricao': 'Produto', 'unidade': 'Unid', 'codigo': 'Cod'}, inplace=True)

    # --- TELAS DO SISTEMA ---
    
    # 1. DASHBOARD
    if menu == "📊 Dashboard":
        st.header("📊 Visão Geral")
        
        # Foi AQUI que o código anterior cortou. Abaixo está a correção:
        if not saldo_atual.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total de Itens", len(saldo_atual))
            c2.metric("Movimentações", len(df_movs) if not df_movs.empty else 0)
            
            # Conta quantos itens estão com saldo zero ou negativo
            zerados = len(saldo_atual[saldo_atual['Saldo'] <= 0])
            c3.metric("Estoque Zerado", zerados, delta_color="inverse")
            
            st.divider()
            
            # Gráfico de Barras (Top 10 Itens com mais saldo)
            if saldo_atual['Saldo'].sum() > 0:
                top_itens = saldo_atual.nlargest(10, 'Saldo')
                st.subheader("Top Itens em Estoque")
                st.bar_chart(top_itens.set_index('Produto')['Saldo'])
            else:
                st.info("O estoque está zerado.")
        else:
            st.info("Cadastre materiais na aba 'Operações' para ver os indicadores.")

    # 2. OPERAÇÕES (Entrada, Saída, Cadastro)
    elif menu == "📦 Operações":
        st.header("📦 Gerenciar Estoque")
        
        tab1, tab2, tab3 = st.tabs(["Entrada (Compra)", "Saída (Uso)", "Novo Produto"])
        
        # Cria lista de opções para os selects (combobox)
        lista_opcoes = []
        if not df_prods.empty:
            lista_opcoes = [f"{row['codigo']} - {row['descricao']}" for i, row in df_prods.iterrows()]

        # -- ABA ENTRADA --
        with tab1:
            with st.form("form_ent"):
                item_e = st.selectbox("Material", lista_opcoes)
                qtd_e = st.number_input("Quantidade", min_value=0.01, step=1.0)
                obs_e = st.text_input("Origem / Nota Fiscal")
                if st.form_submit_button("Registrar Entrada"):
                    if item_e:
                        cod = item_e.split(" - ")[0]
                        desc = item_e.split(" - ")[1]
                        # Insere no banco
                        run_query(
                            "INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            params=("Entrada", datetime.now().date(), "CENTRAL", cod, desc, qtd_e, obs_e), 
                            fetch_data=False
                        )
                        st.success("Entrada salva com sucesso!")
                        time.sleep(1)
                        st.rerun()

        # -- ABA SAÍDA --
        with tab2:
            with st.form("form_sai"):
                item_s = st.selectbox("Material", lista_opcoes, key="s_item")
                qtd_s = st.number_input("Quantidade", min_value=0.01, step=1.0, key="s_qtd")
                obra_s = st.text_input("Qual Obra / Destino?")
                
                if st.form_submit_button("Registrar Saída"):
                    if item_s and obra_s:
                        cod = item_s.split(" - ")[0]
                        desc = item_s.split(" - ")[1]
                        
                        # Verifica saldo disponível antes de deixar sair
                        saldo_disp = 0
                        if not saldo_atual.empty:
                            linha_prod = saldo_atual[saldo_atual['Cod'] == cod]
                            if not linha_prod.empty:
                                saldo_disp = linha_prod['Saldo'].values[0]
                        
                        if saldo_disp >= qtd_s:
                            run_query(
                                "INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade) VALUES (%s,%s,%s,%s,%s,%s)",
                                params=("Saída", datetime.now().date(), obra_s, cod, desc, qtd_s), 
                                fetch_data=False
                            )
                            st.success("Saída registrada!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Saldo insuficiente! Você tem apenas {saldo_disp} disponível.")
                    else:
                        st.warning("Preencha a Obra de destino.")

        # -- ABA CADASTRO --
        with tab3:
            with st.form("form_new"):
                c_new = st.text_input("Código (Ex: CIM-01)").upper()
                d_new = st.text_input("Nome (Ex: CIMENTO CP-II)").upper()
                u_new = st.selectbox("Unidade", ["UNID", "KG", "M", "M2", "M3", "SC", "CX", "L"])
                
                if st.form_submit_button("Cadastrar"):
                    if c_new and d_new:
                        res = run_query(
                            "INSERT INTO produtos (codigo, descricao, unidade) VALUES (%s, %s, %s) ON CONFLICT (codigo) DO NOTHING",
                            params=(c_new, d_new, u_new), 
                            fetch_data=False
                        )
                        if res:
                            st.success("Produto cadastrado!")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.warning("Preencha Código e Nome.")

    # 3. TABELA DE DADOS (HISTÓRICO)
    elif menu == "⚙️ Dados":
        st.header("Histórico Completo")
        st.dataframe(df_movs, use_container_width=True)

# -----------------------------------------------------------------------------
# 5. EXECUÇÃO
# -----------------------------------------------------------------------------
if st.session_state["authenticated"]:
    main_system()
else:
    login_screen()
