import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Amâncio Obras - Portal",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializa Carrinhos (Listas Temporárias)
if "carrinho_entrada" not in st.session_state: st.session_state["carrinho_entrada"] = []
if "carrinho_saida" not in st.session_state: st.session_state["carrinho_saida"] = []
if "carrinho_ajuste" not in st.session_state: st.session_state["carrinho_ajuste"] = [] # NOVO!
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False

# -----------------------------------------------------------------------------
# 2. CONEXÃO BLINDADA
# -----------------------------------------------------------------------------
def run_query(query, params=None, fetch_data=True):
    conn = None
    try:
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
        if fetch_data: return pd.DataFrame()
        return False
    finally:
        if conn: conn.close()

# -----------------------------------------------------------------------------
# 3. CARREGAMENTO DE DADOS (GLOBAL)
# -----------------------------------------------------------------------------
df_prods = run_query("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
df_movs = run_query("SELECT * FROM movimentacoes ORDER BY data DESC, id DESC")

# Cálculo de Saldo
saldo_atual = pd.DataFrame(columns=['Cod', 'Produto', 'Unid', 'Saldo', 'CustoMedio', 'ValorTotal'])

if not df_prods.empty:
    if not df_movs.empty:
        df_calc = df_movs.copy()
        # Entradas e Ajustes(+) somam. Saídas e Ajustes(-) subtraem.
        df_calc['fator'] = df_calc['tipo'].apply(lambda x: 1 if x in ['Entrada', 'Ajuste(+)'] else -1)
        df_calc['qtd_real'] = df_calc['quantidade'] * df_calc['fator']
        saldos = df_calc.groupby('codigo')['qtd_real'].sum().reset_index()

        # Custo Médio
        entradas = df_movs[df_movs['tipo'] == 'Entrada'].copy()
        if not entradas.empty:
            entradas['total_gasto'] = entradas['quantidade'] * entradas['custo_unitario']
            custos = entradas.groupby('codigo')[['quantidade', 'total_gasto']].sum().reset_index()
            custos['custo_medio'] = custos['total_gasto'] / custos['quantidade']
            saldos = pd.merge(saldos, custos[['codigo', 'custo_medio']], on='codigo', how='left')
        
        saldo_atual = pd.merge(df_prods, saldos, on='codigo', how='left').fillna(0)
        
        if 'custo_medio' not in saldo_atual.columns: saldo_atual['custo_medio'] = 0
        saldo_atual['valor_estoque'] = saldo_atual['qtd_real'] * saldo_atual['custo_medio']
    else:
        saldo_atual = df_prods.copy()
        saldo_atual['qtd_real'] = 0; saldo_atual['custo_medio'] = 0; saldo_atual['valor_estoque'] = 0

    saldo_atual.rename(columns={'qtd_real': 'Saldo', 'descricao': 'Produto', 'unidade': 'Unid', 'codigo': 'Cod'}, inplace=True)

# -----------------------------------------------------------------------------
# 4. BARRA LATERAL
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1063/1063196.png", width=60)
    st.markdown("### Amâncio Obras")
    
    if not st.session_state["authenticated"]:
        st.divider()
        st.markdown("🔒 **Acesso Restrito**")
        with st.form("login_sidebar"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Erro no login")
    else:
        st.success(f"👤 Admin: {st.secrets['auth']['username'].upper()}")
        st.divider()
        menu = st.radio("Menu:", 
                        ["📊 Dashboard Financeiro", 
                         "🔄 Movimentações (Lote)", 
                         "🗑️ Gerenciar / Excluir", 
                         "⚙️ Histórico Completo"])
        st.divider()
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

# -----------------------------------------------------------------------------
# 5. TELA PÚBLICA (VISITANTE)
# -----------------------------------------------------------------------------
if not st.session_state["authenticated"]:
    st.title("📋 Estoque Disponível")
    st.markdown("**Consulta Pública** - Atualização em Tempo Real")
    
    if not saldo_atual.empty:
        c_busca, c_kpi = st.columns([2, 1])
        with c_busca:
            busca_pub = st.text_input("🔍 Pesquisar:", placeholder="Ex: Cimento...")
        with c_kpi:
            st.metric("Itens Cadastrados", len(saldo_atual))

        df_publico = saldo_atual[['Cod', 'Produto', 'Unid', 'Saldo']].copy()
        if busca_pub:
            df_publico = df_publico[df_publico['Produto'].str.contains(busca_pub, case=False)]

        st.dataframe(
            df_publico,
            use_container_width=True,
            hide_index=True,
            height=600,
            column_config={
                "Saldo": st.column_config.NumberColumn("Estoque Físico", format="%.2f"),
                "Cod": st.column_config.TextColumn("Cód", width="small"),
            }
        )
    else:
        st.warning("Sem dados.")

# -----------------------------------------------------------------------------
# 6. ÁREA ADMIN
# -----------------------------------------------------------------------------
else:
    # --- DASHBOARD ---
    if menu == "📊 Dashboard Financeiro":
        st.title("📊 Painel Gerencial")
        if not saldo_atual.empty:
            total_money = saldo_atual['valor_estoque'].sum()
            zerados = len(saldo_atual[saldo_atual['Saldo'] <= 0])
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Itens", len(saldo_atual))
            c2.metric("Valor Estoque", f"R$ {total_money:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            c3.metric("Zerados", zerados, delta_color="inverse")
            
            st.divider()
            st.subheader("📦 Detalhe Financeiro")
            st.dataframe(
                saldo_atual[['Cod', 'Produto', 'Saldo', 'custo_medio', 'valor_estoque']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "custo_medio": st.column_config.NumberColumn("Custo Médio", format="R$ %.2f"),
                    "valor_estoque": st.column_config.NumberColumn("Total Investido", format="R$ %.2f")
                }
            )

    # --- OPERAÇÕES (LOTE) ---
    elif menu == "🔄 Movimentações (Lote)":
        st.title("🔄 Central de Operações")
        # ADICIONADA A NOVA ABA DE AJUSTE AQUI
        tab_ent, tab_sai, tab_aj, tab_cad = st.tabs(["📥 ENTRADA", "📤 SAÍDA", "🔧 AJUSTE (Inventário)", "🆕 NOVO ITEM"])
        
        opcoes = [f"{r['codigo']} - {r['descricao']}" for i, r in df_prods.iterrows()] if not df_prods.empty else []

        # 1. ENTRADA
        with tab_ent:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.info("Adicionar Item")
                with st.form("add_ent"):
                    ie = st.selectbox("Item", opcoes)
                    qe = st.number_input("Qtd", 0.01)
                    ve = st.number_input("R$ Unitário", 0.0)
                    if st.form_submit_button("⬇️ Incluir"):
                        if ie:
                            st.session_state["carrinho_entrada"].append({
                                "cod": ie.split(" - ")[0], "desc": ie.split(" - ")[1], 
                                "qtd": qe, "custo": ve, "total": qe*ve
                            })
                            st.rerun()
            with c2:
                st.success("Lista de Entrada")
                if st.session_state["carrinho_entrada"]:
                    df_c = pd.DataFrame(st.session_state["carrinho_entrada"])
                    st.dataframe(df_c, hide_index=True, use_container_width=True, 
                               column_config={"custo": st.column_config.NumberColumn("R$", format="%.2f")})
                    with st.form("save_ent"):
                        nf = st.text_input("NF / Fornecedor")
                        if st.form_submit_button("✅ FINALIZAR ENTRADA"):
                            if nf:
                                for i in st.session_state["carrinho_entrada"]:
                                    run_query("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", 
                                              ("Entrada", datetime.now().date(), "CENTRAL", i['cod'], i['desc'], i['qtd'], i['custo'], nf), False)
                                st.session_state["carrinho_entrada"] = []
                                st.success("Salvo!"); time.sleep(1); st.rerun()
                    if st.button("Limpar", key="cls_ent"): st.session_state["carrinho_entrada"] = []; st.rerun()

        # 2. SAÍDA
        with tab_sai:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.info("Adicionar Item")
                with st.form("add_sai"):
                    is_ = st.selectbox("Item", opcoes, key="s_i")
                    qs = st.number_input("Qtd", 0.01, key="s_q")
                    if st.form_submit_button("⬇️ Incluir"):
                        if is_:
                            st.session_state["carrinho_saida"].append({
                                "cod": is_.split(" - ")[0], "desc": is_.split(" - ")[1], "qtd": qs
                            })
                            st.rerun()
            with c2:
                st.warning("Lista de Saída")
                if st.session_state["carrinho_saida"]:
                    st.dataframe(pd.DataFrame(st.session_state["carrinho_saida"]), hide_index=True, use_container_width=True)
                    with st.form("save_sai"):
                        ob = st.text_input("Destino / Obra")
                        if st.form_submit_button("📤 FINALIZAR SAÍDA"):
                            if ob:
                                for i in st.session_state["carrinho_saida"]:
                                    run_query("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                                              ("Saída", datetime.now().date(), ob, i['cod'], i['desc'], i['qtd'], 0), False)
                                st.session_state["carrinho_saida"] = []
                                st.success("Baixado!"); time.sleep(1); st.rerun()
                    if st.button("Limpar", key="cls_sai"): st.session_state["carrinho_saida"] = []; st.rerun()

        # 3. AJUSTE (NOVA ABA)
        with tab_aj:
            st.markdown("Use para **Inventário Semanal** ou correção de diferenças.")
            c1, c2 = st.columns([1, 2])
            with c1:
                st.info("Adicionar Diferença")
                with st.form("add_aj"):
                    ia = st.selectbox("Item", opcoes, key="a_i")
                    # Dica visual para o usuário
                    st.caption("Use valor **Positivo** para adicionar e **Negativo** para remover.")
                    qa = st.number_input("Diferença (Qtd)", step=1.0, key="a_q")
                    mot = st.text_input("Motivo (Ex: Contagem)", key="a_m")
                    
                    if st.form_submit_button("⬇️ Incluir no Balanço"):
                        if ia and qa != 0:
                            st.session_state["carrinho_ajuste"].append({
                                "cod": ia.split(" - ")[0], "desc": ia.split(" - ")[1], 
                                "qtd": qa, "motivo": mot
                            })
                            st.rerun()
            with c2:
                st.warning("Lista de Ajustes (Balanço)")
                if st.session_state["carrinho_ajuste"]:
                    st.dataframe(pd.DataFrame(st.session_state["carrinho_ajuste"]), hide_index=True, use_container_width=True)
                    
                    if st.button("⚖️ PROCESSAR AJUSTES"):
                        for i in st.session_state["carrinho_ajuste"]:
                            tipo = "Ajuste(+)" if i['qtd'] > 0 else "Ajuste(-)"
                            run_query("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", 
                                      (tipo, datetime.now().date(), "BALANÇO", i['cod'], i['desc'], abs(i['qtd']), 0, i['motivo']), False)
                        st.session_state["carrinho_ajuste"] = []
                        st.success("Estoque Corrigido!"); time.sleep(1); st.rerun()

                    if st.button("Limpar", key="cls_aj"): st.session_state["carrinho_ajuste"] = []; st.rerun()
                else:
                    st.info("Nenhum ajuste pendente.")

        # 4. CADASTRO
        with tab_cad:
            with st.form("cad_new"):
                c1,c2,c3 = st.columns([1,2,1])
                cod = c1.text_input("Código").upper()
                des = c2.text_input("Descrição").upper()
                und = c3.selectbox("Und", ["UNID", "KG", "M", "M2", "M3", "SC", "CX"])
                if st.form_submit_button("Salvar"):
                    run_query("INSERT INTO produtos (codigo, descricao, unidade) VALUES (%s,%s,%s) ON CONFLICT (codigo) DO NOTHING", (cod, des, und), False)
                    st.success("Cadastrado!"); time.sleep(1); st.rerun()

    # --- GERENCIAR / EXCLUIR ---
    elif menu == "🗑️ Gerenciar / Excluir":
        st.title("🗑️ Histórico e Correções")
        st.warning("A exclusão é permanente.")
        
        if not df_movs.empty:
            filtro = st.text_input("Filtrar:", placeholder="Ex: Cimento, Entrada...")
            df_del = df_movs.copy()
            if filtro:
                df_del = df_del[
                    df_del['descricao'].str.contains(filtro, case=False) | 
                    df_del['tipo'].str.contains(filtro, case=False)
                ]
            
            st.dataframe(df_del, use_container_width=True, hide_index=True)
            
            st.divider()
            c_del1, c_del2 = st.columns([1, 2])
            with c_del1:
                id_to_del = st.number_input("ID para excluir:", min_value=0, step=1)
                if st.button("❌ APAGAR REGISTRO", type="primary"):
                    if id_to_del > 0:
                        run_query("DELETE FROM movimentacoes WHERE id = %s", (id_to_del,), False)
                        st.success("Apagado!"); time.sleep(1); st.rerun()
        else:
            st.info("Vazio.")

    # --- HISTÓRICO ---
    elif menu == "⚙️ Histórico Completo":
        st.title("📜 Histórico Geral")
        st.dataframe(df_movs, use_container_width=True)
