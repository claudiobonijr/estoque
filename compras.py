import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Configuração e Estilo
st.set_page_config(page_title="Controle de Estoque Obras", layout="wide")

conn = sqlite3.connect('estoque_obras.db', check_same_thread=False)
c = conn.cursor()

# Criar tabelas necessárias
c.execute('''CREATE TABLE IF NOT EXISTS produtos 
             (codigo TEXT PRIMARY KEY, descricao TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS movimentacoes 
             (id INTEGER PRIMARY KEY, tipo TEXT, data TEXT, obra TEXT, sc TEXT, 
              mapa TEXT, oc TEXT, codigo TEXT, descricao TEXT, quantidade REAL)''')
conn.commit()

st.sidebar.title("🏗️ Menu Principal")
escolha = st.sidebar.radio("Ir para:", ["📊 Dashboard", "📝 Cadastrar Produto", "📥 Entrada", "📤 Saída", "📜 Histórico"])

# --- LÓGICA DE DADOS ---
df_mov = pd.read_sql_query("SELECT * FROM movimentacoes", conn)
df_prod = pd.read_sql_query("SELECT * FROM produtos", conn)

# --- ABA: DASHBOARD ---
if escolha == "📊 Dashboard":
    st.title("📊 Dashboard de Estoque")
    if not df_mov.empty:
        df_mov['qtd_ajustada'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] == 'Entrada' else -x['quantidade'], axis=1)
        saldo_df = df_mov.groupby(['codigo', 'descricao']).agg({'qtd_ajustada': 'sum'}).reset_index()
        saldo_df.columns = ['Código', 'Descrição', 'Saldo Atual']
        
        c1, c2 = st.columns(2)
        c1.metric("Produtos Cadastrados", len(df_prod))
        c2.metric("Movimentações Realizadas", len(df_mov))
        
        st.subheader("📦 Saldo em Tempo Real")
        st.dataframe(saldo_df, use_container_width=True)
        st.bar_chart(data=saldo_df, x='Descrição', y='Saldo Atual')
    else:
        st.info("Nenhuma movimentação registrada ainda.")

# --- ABA: CADASTRO DE PRODUTOS ---
elif escolha == "📝 Cadastrar Produto":
    st.subheader("📝 Cadastro de Novos Materiais")
    with st.form("form_prod"):
        cod = st.text_input("Código do Produto (Ex: MAT-001)")
        desc = st.text_input("Descrição completa (Ex: Cimento CP-II 50kg)")
        if st.form_submit_button("Salvar Produto"):
            try:
                c.execute("INSERT INTO produtos VALUES (?,?)", (cod, desc))
                conn.commit()
                st.success("Produto cadastrado com sucesso!")
                st.rerun()
            except:
                st.error("Este código já está cadastrado!")

# --- ABA: ENTRADA ---
elif escolha == "📥 Entrada":
    st.subheader("📥 Registro de Entrada")
    if df_prod.empty:
        st.warning("Cadastre um produto primeiro na aba 'Cadastrar Produto'.")
    else:
        with st.form("entrada"):
            col1, col2 = st.columns(2)
            with col1:
                data = st.date_input("Data", datetime.now())
                obra = st.text_input("Obra Destino")
                sc = st.text_input("SC (Solicitação)")
                # Seleção automática de produto
                lista_prods = df_prod['codigo'] + " - " + df_prod['descricao']
                prod_sel = st.selectbox("Selecione o Produto", lista_prods)
            with col2:
                mapa = st.text_input("Mapa de Cotação")
                oc = st.text_input("OC (Ordem de Compra)")
                qtd = st.number_input("Quantidade", min_value=0.1)
            
            if st.form_submit_button("Confirmar Entrada"):
                cod_final = prod_sel.split(" - ")[0]
                desc_final = prod_sel.split(" - ")[1]
                c.execute("INSERT INTO movimentacoes VALUES (NULL,?,?,?,?,?,?,?,?,?)", 
                          ('Entrada', str(data), obra, sc, mapa, oc, cod_final, desc_final, qtd))
                conn.commit()
                st.success(f"Entrada de {desc_final} realizada!")

# --- ABA: SAÍDA ---
elif escolha == "📤 Saída":
    st.subheader("📤 Registro de Saída")
    if df_prod.empty:
        st.warning("Nenhum produto cadastrado.")
    else:
        with st.form("saida"):
            col1, col2 = st.columns(2)
            with col1:
                data = st.date_input("Data", datetime.now())
                obra = st.text_input("Obra Aplicada")
                lista_prods = df_prod['codigo'] + " - " + df_prod['descricao']
                prod_sel = st.selectbox("Selecione o Produto", lista_prods)
            with col2:
                qtd = st.number_input("Quantidade Saída", min_value=0.1)
                ref = st.text_input("Ref. OC/SC de Origem")
                
            if st.form_submit_button("Confirmar Saída"):
                cod_final = prod_sel.split(" - ")[0]
                desc_final = prod_sel.split(" - ")[1]
                c.execute("INSERT INTO movimentacoes VALUES (NULL,?,?,?,?,?,?,?,?,?)", 
                          ('Saída', str(data), obra, "", "", ref, cod_final, desc_final, qtd))
                conn.commit()
                st.warning(f"Saída de {desc_final} registrada!")

# --- ABA: HISTÓRICO ---
elif escolha == "📜 Histórico":
    st.subheader("📜 Histórico de Movimentações")
    st.dataframe(df_mov, use_container_width=True)